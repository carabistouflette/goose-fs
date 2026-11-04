# Retained File contract

Experimental 64-bit Linux API. The pathname and no-follow policy in [API.md](API.md)
also applies to `open_file`. Retained I/O does not reopen a pathname.

```goose
let context, created = fs::create_context();
assert(created.error == fs::Error.None);
defer fs::close_context(context);
let file, opened = fs::open_file(context, "/tmp/input", fs::OpenOptions { .. });
assert(opened.error == fs::Error.None);
var bytes: u8[>..] = [];
let result = fs::read_some(file, 65536, bytes);
```

Use `defer` after successful context creation. Check explicit `close_context` if
close errors matter; a defer can intentionally discard its status. A File token
is a pair of opaque native registry identities, not a raw OS descriptor. Its
fields are implementation details. Copying a token aliases the same lifetime and
cursor: `close_file` through one copy invalidates all copies. `duplicate_file`
creates an independently closable close-on-exec descriptor in the same Context;
it shares the OS file cursor, append state and underlying inode with its source.
Both forms are safe to pass to compiled Goose workers. Tokens are not an access
control boundary against deliberately forged values or trusted native FFI code.
Keep the Context alive when returning a File or Root to a caller; closing that
Context in the producing scope would return an already-invalid token.

`close_context` waits for all of its active opens/I/O/closes, invalidates the
Context and every owned File/Root, attempts every close, and returns the first close
error. Context and File identities are never reused within a loaded registry lifetime. A stale or wrong-context
token returns `SystemError`/EBADF; it cannot close a newly reused descriptor slot.
Linux close is never retried after EINTR, and tokens remain invalid after a close
error. There is no fsync implied by closing either resource.

The process-wide registry holds at most 64 Contexts and 4096 combined Files/Roots, including
duplicates; capacities are shared across compiled workers. Registry capacity or
identity-space exhaustion reports `LimitExceeded` with zero OS error before
creation/truncation/duplication effects. Actual kernel descriptor exhaustion
reports `SystemError` with its errno. Closing resources recovers registry capacity;
identity exhaustion never wraps or recovers. The registry retains no Goose-memory
pointers and never destroys or relocates locks. Independently loaded native library
copies have independent registries; tokens cannot be transferred between them.

## Opening

`open_file(context, path, options) -> (File, Status)` returns a zero File on error.
`OpenOptions` contains:

| Field | Values and default |
| --- | --- |
| access | `Access.Read` (default), `Write` (O_WRONLY), `ReadWrite` |
| creation | `Creation.Existing` (default), `CreateNew` (exclusive), `OpenOrCreate` |
| append | false; writes use kernel O_APPEND when true |
| truncate | false; truncate to zero only after fstat confirms a regular file |
| permissions | 0600 (decimal 384); creation-only mode 0000..0777, reduced by process umask |

Read-only append/truncate and invalid values are rejected before filesystem work.
Append and truncate together are allowed: truncate once at open, then append.
The permissions option is used only when creating a new entry. Existing modes
are not explicitly reset by open_file; normal kernel mutation rules apply,
including possible clearing of setuid/setgid bits on truncate or write.
Native registry space is reserved before
opening. Final and parent symlinks are rejected. Only regular files are accepted;
nonregular targets report `NotRegular` when opening/fstat succeeds. An inaccessible
or write-opened directory can instead fail with an OS error. Device-open callbacks
may run before fstat; O_NONBLOCK/O_NOCTTY reduce FIFO/terminal hazards but do not
provide deadlines or eliminate device effects. A failed open/create can leave a
newly created entry. There is no rollback, snapshot or confinement guarantee.

## I/O and metadata

| Function | Result/behavior |
| --- | --- |
| `read_some(file, limit, out)` | One read, retrying EINTR; replace out with up to limit bytes |
| `read_at(file, offset, limit, out)` | Same through pread; preserve shared cursor |
| `write_some(file, data)` | One write, retrying EINTR; report possibly short progress |
| `write_at(file, offset, data)` | One pwrite; preserve cursor; reject append descriptors with EINVAL |
| `write_all(file, data)` | Loop until all bytes written or failure; retain partial byte count |
| `seek(file, offset, SeekOrigin)` | Return `(position, Status)`; origins Start/Current/End |
| `truncate_file(file, size)` | ftruncate; cursor is unchanged; extending may create a sparse hole |
| `sync_file(file, data_only)` | fdatasync when true, fsync when false; retry EINTR |
| `file_metadata(file, out)` | Same Metadata fields/reset semantics, using the held descriptor; works after rename/unlink |
| `close_file(file)` | Invalidate aliases and close, independently of any duplicate's lifetime |

`IOResult { status, bytes, eof }` counts successful progress, not requested bytes.
Every read output is empty on error. Positive short reads are successful progress,
not an EOF guarantee. EOF is true only for a successful zero-byte read with a
positive request. A zero-length request still validates token, access and offset,
then succeeds with zero bytes and eof false. Positive-length writes returning zero
report EIO rather than looping. `write_all` preserves a partial count on failure;
those bytes may already be visible and the cursor may have advanced.

Each read/write request is bounded to 1 MiB, including `write_all`; applications
can loop for larger files without imposing a whole-file size cap. Positioned
offsets and truncate sizes are signed nonnegative 64-bit values; offset plus
request length must not exceed INT64_MAX. Seek allows negative Current/End offsets
when the resulting OS position is valid. Access errors retain EBADF even for
empty requests. Sync success reflects filesystem/kernel guarantees, not an
independent power-loss guarantee; parent-directory publication requires separate
operations not provided in this stage.

Calls on one File entry coordinate through a lock. Cursor operations, truncation,
sync and writes hold an exclusive entry lock; positioned reads and metadata may
run concurrently. `write_all` holds its entry lock for the entire loop. Duplicates
have independent locks despite sharing the OS cursor, so seek/write through a
duplicate can interleave between those short writes. There is no atomic-record
or cross-descriptor transaction guarantee. Disjoint positioned writes on a single
token currently serialize. All calls also hold a shared Context lock; the global
allocator mutex is used only for allocation/close bookkeeping. Initialization
creates 4160 locks, allocation scans up to 4096 slots, and context closure scans
those slots using a 16 KiB native stack index array. No retained-handle speed
superiority is claimed without separate sequential/concurrent measurements.

Directory-relative [Root operations](ROOTS.md) share the same Context and resource
capacity; Files and Roots use distinct native kind checks.

File locking is available through `try_lock_file`, `lock_file` and `unlock_file`;
see [the flock and waiting contract](LOCKS.md) for shared/duplicate state, conversion
and polling cleanup semantics.

## Abnormal exits and limits

The pinned runtime exposes no native lifecycle cleanup hook. Goose `defer` runs
on normal return/control flow, not on assert/abort/exit. For contained workers,
create and retain the Context in the surviving parent, pass it to the worker, then
close it after `thread_wait`, including a false (aborted) result. Published native
calls invoke no Goose callbacks while holding locks. A contained Goose abort
between calls therefore leaves no held native lock. Parent-owned cleanup is
validated by compiled worker tests; thread completion does not have to wait for
TLS destructors because this registry uses no TLS ownership.

A Context created inside an aborting worker or aborted JIT main is not reclaimed
automatically. The surviving parent/embedding host must retain and close its token;
otherwise descriptors remain until process exit. Close every Context before unloading
a native library; unloading it does not close those descriptors. External native
thread cancellation, async signal-handler calls and fork-child use before exec
are unsupported: cancellation/fork can leave inherited locks unusable. This API
is thread-safe but not async-signal-safe. ContextClose cannot cancel I/O and may
wait indefinitely. No deadline, global termination or lock-acquisition fairness
is guaranteed. glibc uses writer-preferred nonrecursive rwlocks; other Linux libcs
use their native default policy and have not received the full libc test matrix.


Held File permission, numeric owner/group and atime/mtime setters are documented
in [FILE-METADATA.md](FILE-METADATA.md). They use the held inode without another
pathname lookup, including after unlink, and do not implicitly synchronize.
