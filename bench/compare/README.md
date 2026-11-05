# Native API comparison

This harness compares goose-fs with stable Rust std::fs (1.99.1), Go os (the
installed toolchain, recorded), and the pinned Goose standard library.
It is a **task-cost comparison with different safety contracts**, not an
equal-security ranking. See docs/comparison-research.md for the hardened-adapter
profile still required before equal-security performance conclusions.

```sh
python3 bench/compare/build.py --goose /absolute/path/to/goose --cc gcc
python3 bench/compare/run.py --goose /absolute/path/to/goose --cc gcc \
  --iterations 100 --rounds 3 --output .build/compare/native-api.json
```

All binaries use the same private fixtures, with full byte-pattern and sorted-name
validation outside timers. Seven samples per workload per process use fresh or
reused read outputs; sizes 0/64/4096/65536/1048576 bytes. Listings have
0/1/128/4096 ASCII names. General metadata is explicitly unsupported for Goose
stdlib; is-directory is a separate workload. Each batch retains its language's
normal allocator/GC behavior. Whole batches are shuffled with a recorded seed.
Retained-read cases open once before timing, then read at offset zero into reused
storage through goose-fs read_at, Rust FileExt::read_at and Go File.ReadAt. Open,
Context initialization and close are outside those timings; the pinned Goose
stdlib has no retained File API and receives unsupported rows. Exact-sized stable
fixtures are intended to permit one successful pread for nonempty inputs, despite
Go ReadAt's more general fill/EOF contract. Short reads/EINTR remain possible;
syscall counts are not measured. Zero-sized retained reads may avoid
syscalls. Context+entry lock and error checks remain in goose-fs timings; these
are sequential retained calls, not a concurrency or lifecycle-cost measurement.
The uncontended lock case times an exclusive try-acquire/unlock pair through
goose-fs and Rust File. Both use Linux flock on this host; Go os and the pinned
Goose stdlib have no portable File locking API and receive unsupported rows.
It excludes open/close and does not measure contention or polling wakeup costs.
Root cases open a directory once, then time fresh 64-byte reads, final-entry
metadata and sorted 128-entry listings through goose-fs Root and Go os.Root.
Go listings use Root.Open+File.Readdirnames(-1)+slices.Sort; goose-fs retains the
1 MiB/4096-entry budget and structured entries with kind hints. Names alone are
consumed. Go Root DirEntry enumeration eagerly loads metadata, so using Readdirnames
avoids charging unused full metadata work to this names task. The Go result is
owned sorted strings, while goose-fs also returns kind hints.
Rust std and the pinned Goose stdlib have no equivalent Root API and receive
unsupported rows. Root creation/close are outside timing. Go permits in-tree links;
goose-fs rejects them. These common stable fixtures do not exercise that difference,
so the results remain task costs with different lookup/ownership policies.

Results record native-API policies, source/executable/fixture hashes, versions,
flags, affinity, filesystem, shared-host load, all raw samples, and per-process
VmHWM sampled after the workload suite. Reads consume length and endpoint bytes;
listing checksums include every name's length and endpoint bytes. Rust black_box
and retained Go sinks prevent owned-result dead-store elimination; Goose's
separately compiled native sidecar remains opaque to the program optimizer.
The builder saves source/toolchain/flag/binary provenance only after all builds
succeed; the runner rejects changed inputs or a mismatched compiler selection.
Go build settings and selected inherited runtime/allocator settings are retained.
Full-content preflight checks are separate from timed endpoint/length checks;
fresh timed results do not receive a full-content postcheck.

Fresh Rust/Go convenience calls return newly owned data; reused variants use
File.read_to_end/File.Read and retain storage. Goose stdlib appends into a cleared
caller builder; goose-fs replaces caller data and enforces regular-file, path,
symlink and byte bounds that ordinary comparator APIs do not. Goose stdlib uses
newline framing and omits newline filenames; these common fixtures contain none.
Sorted outputs differ in representation and kind-hint work. They are not identical
ownership/error/lookup interfaces. Unsupported cells never receive a timing score.
goose-fs listings use a 1 MiB byte budget and 4096-entry limit for every size,
including empty directories; oversized staging initialization is a caller cost.
Metadata callers test regular kind and size. Rust/Go also retain full metadata
objects, while Goose may elide unused wrapper-field materialization. VmHWM covers
the whole suite, validation, allocators/GC and retained Go sinks; it is neither
per-operation memory nor an allocation count.

Do not infer portable parity, durability, cold-I/O, equal-security or universal
language performance from this harness. Publish regressions and unsupported cases.


`build.py --adaptive-listing` and matching `run.py --adaptive-listing` explicitly
select goose-fs ListOptions.adaptive=true for absolute and Root sorted listings.
The build manifest and raw listing_limits retain that choice; mismatched profiles
are rejected. The default remains full one-pass staging. Comparator APIs and all
other workloads are unchanged. Adaptive mode trades lower small-result buffer
initialization for a second pass when accepted packed names exceed 64 KiB; use the
paired long-name profile in [the benchmark guide](../README.md) to see that cost.


Rename rows report nanoseconds per **pair**, meaning left→right and right→left
(two namespace operations). Each leg starts with its destination absent. Replace
is the policy name; these rows do not measure overwriting an existing inode.
Complete preflight checks observe the intermediate move/content/source absence;
postflight verifies the restored entry/content and absent destination. Fixture
creation, validation, Root/Context setup and formatting are outside timing.

`rename-replace-pair` uses each native API. Pinned Goose rename_file always makes
a best-effort destination-parent sync after each rename; Rust/Go/fs basic calls
request no sync. That differing durability work is intentionally disclosed, not
ranked as equal behavior. `rename-parents-sync-pair` composes two readable-parent
opens before each rename, both checked sync calls and cleanup for Rust/Go; fs uses
RenameOptions.sync_parents=true. Rust File::Drop cannot report close errors.
Goose's API cannot report checked parent sync and is unsupported in that row.
Root checked-sync uses two readable Root.Open(".") handles for Go. Root lifecycle
is excluded from all Root rows. NoReplace is unsupported outside fs in this native
API profile; link+unlink is not substituted for atomic generic entry rename.
The build/run profile retains every existing workload and unsupported cell. These
warm local fixtures do not measure crash recovery, remote filesystems, existing-
target overwrite latency or equal-security performance.

Absolute Rust/Go checked compositions re-resolve pathname parents in the rename
call; their preopened sync handles are not a concurrent-parent identity promise.
The fixtures stay stable. goose-fs renames through the exact held parent FDs.
This difference is another reason the rows are not an equal-security ranking.

Held-file metadata rows time one setter per iteration, on a read-only-open File:
mode 0640, the fixture's captured current numeric UID/GID, or exact access time
1000.123456789 and modification time 2200000000.987654321 seconds since the Epoch.
Repeated same-value requests still invoke the OS mutation; they are not harmless
no-ops (chown can clear privilege attributes). No implicit sync is requested.
Open/close, Context lifecycle, identity capture, cursor setup and metadata/content
checks are outside timers. Timers include status checks and one checksum increment
per successful setter. The fixture must support the requested nanosecond times.

Rust uses File::set_permissions, Unix std::os::unix::fs::fchown and File::set_times;
Go uses File.Chmod and File.Chown. The syscall.Stat_t assertion in Go extracts
fixture UID/GID outside timing, without adding a non-os mutation adapter. Go os
has no held-File time setter in the recorded toolchain; path Chtimes is not
substituted. Pinned Goose stdlib lacks retained File setters. Those cells remain
unsupported. Public API contracts, locking, runtime and error behavior differ;
these sequential task costs do not establish equal-security performance.

API references: [Rust File](https://doc.rust-lang.org/std/fs/struct.File.html),
[Rust fchown](https://doc.rust-lang.org/std/os/unix/fs/fn.fchown.html),
[Go os](https://pkg.go.dev/os).

Build/run provenance also hashes the selected complete Goose standard library's
sources and forces that directory during builds. This binds these harnesses' std/os
imports; it is not a general compiler import-resolution manifest. Source edits,
including standard-library edits, require a rebuild before measurement.

## Bounded symlink inspection checkpoint

The six readlink rows use stable 64-, 256- and 4095-byte targets and a 1MiB
consumer budget. FS calls the public bounded absolute/Root API with reusable
caller output and fresh adaptive staging. Rust std::fs::read_link and Go
os.Readlink/Root.Readlink allocate native PathBuf/string results, then check the
consumer bound. Their ordinary ancestor-following/Root policies differ from
FS strict no-follow lookup. Root lifecycle is outside timing. Goose stdlib has
no readlink; Rust stdlib has no Root interface. Unsupported rows stay explicit.
Full target bytes are checked before and after timing; status, exact length and
endpoint checksum remain inside. These are descriptive native-API task costs,
not policy-matched security or allocation comparisons.

Finite initial publication schedule: exactly three separately launched recordings,
three shuffled rounds each, seven means per workload/runner, 100 calls per mean;
seeds 65811,65812,65813. All existing suite workloads remain retained and labelled;
report the new readlink rows without discarding slower cases. Warmup count1 and
build qualification are ineligible. Record on CPU6 after owned heavy jobs finish;
no exclusive-core/cache/frequency claim. Retain all raw outputs, provenance and
external completion statuses; no replacements, normalization, throughput/SOTA or
small-difference claims. The earlier failed matched read controls do not become
qualified through this separate descriptive profile. Freeze clean reviewed source
before the first recording; no adaptive threshold sweep is authorized here.

Recorder outputs and journals are reserved with exclusive creation and remain
reserved after failure. Completed child streams are flushed losslessly before
parsing; timeout and caught interruption tails are drained/reaped and retained.
Summaries are written through the originally reserved descriptor, never reopened
through a pathname. Python -O is rejected. No supervisor is added to this native
API profile: default SIGTERM, hard kills, power loss or repeated interruption can
prevent cleanup/final markers. Such incomplete records and any nonzero/unknown
external completion status are ineligible and cannot be replaced. Private output
parents and no concurrent writers remain required. No guarantee of recovering
bytes after an uncatchable termination is made.
