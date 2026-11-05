# Bounded symbolic-link inspection — Linux

`read_link(absolute_path, limit, out)` and
`read_link_at(root, relative_path, limit, out)` replace caller-owned bytes with
one complete final symlink target. Targets are returned verbatim: relative paths,
`..`, absolute/outside paths, dangling/cyclic targets, newlines and non-UTF-8 bytes
are data. They are never followed, normalized or treated as authorization.
Existing strict path grammar and no-follow ancestor resolution remain in force.
Root retains its directory identity and existing Context/lifetime/locking rules.
This is inspection, not canonicalization, a snapshot or a sandbox.

Limits are 0..MAX_BYTES (1MiB), independently of the existing 4095-byte input
pathname limit. Invalid limits/paths return InvalidInput. A target longer than
limit returns LimitExceeded with os_error=0; zero budget still inspects the entry
using one byte of staging. Every error clears public output, including a failure
on a later sizing pass. Non-links normally report SystemError/EINVAL; missing,
access, lookup and descriptor errors retain their errno and can occur first.
No NUL terminator is appended. Pathnames borrowed from out remain valid through
native reads; the output is replaced only after staging completes.

Staging begins at min(limit+1,256) initialized bytes. A full readlinkat buffer is
ambiguous and is never exposed as success. When capacity<=limit, the call closes
its parent descriptor then doubles/clips staging to limit+1 and repeats lookup.
Filling limit+1 is terminal overflow. Exact-capacity targets require another
pass; a maximum budget takes at most 14 sizing passes (EINTR retries are separate
and have no deadline). This avoids initializing 1MiB for short targets but adds
syscalls, allocations and copies for longer ones; no speed advantage is assumed.
One completed syscall supplies all returned bytes; prefixes are never combined.

Each pass resolves/owns a parent descriptor and consumes it with one close.
Close errors override successful reads or private sizing requests, stopping
retries. A readlinkat error takes precedence over close failure; LimitExceeded
also takes precedence over close failure. Error precedence does not imply close
succeeded. Linux close is never retried, including EINTR. Parent-walk close errors
stop resolution under the existing contract. No retained resource slot is added.
Root read locks cover native lookup/read/close and are released before Goose
staging growth; Root/Context closure between passes can fail the operation.

Concurrent replacement can change which entry a later pass observes. Parent
renames, mounts and dynamic procfs magic-link text can change results; repeated
reads may have access-time effects. The API promises no stable target identity,
filesystem snapshot or confinement. Returned bytes can become stale immediately.
Root invalidation, abnormal worker cleanup and descriptor limits retain the
[Root](ROOTS.md) and [File/Context](HANDLES.md) contracts.

[Rust std::fs::read_link](https://doc.rust-lang.org/std/fs/fn.read_link.html) and
[Go os.Readlink/Root.Readlink](https://pkg.go.dev/os#Readlink) are useful feature
references, but their native allocation, bounds and ancestor-following policies
differ. The pinned Goose standard library has no readlink operation. Those
policies must remain visible in task-cost comparisons; unsupported rows are not
substituted with file reads or canonicalization.

[Three-record native-API task costs and reproducible evidence](../bench/results/2026-11-05-read-link/README.md)
retain different policies, unsupported APIs and slower cases without a SOTA claim.
