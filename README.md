# goose-fs

Small, bounded filesystem operations for the
[Goose programming language](https://github.com/aardappel/goose). Apache-2.0.
Experimental interface; no release yet. 64-bit Linux is the current target.

Read regular files with byte limits, list directories with structured byte-preserving
names, inspect metadata, exclusively create files/directories, and remove individual entries. Retained Files add bounded streaming/positioned I/O, seek, truncate, sync and independent duplication.
Every directory component rejects symlinks during traversal. Goose owns validation
and returned storage; a private C kernel owns filesystem descriptors with explicit cleanup.

```goose
import fs from "../goose-fs";
import std;

fn main() {
    var bytes: u8[>..] = [];
    let result = fs::read("/tmp/settings.toml", 65536, bytes);
    if result.error == fs::Error.None { print("read ", bytes.len, " bytes"); }
    else { print("read failed; errno ", result.os_error); }
}
```

Declare the package in the application's root source. The example assumes a sibling
checkout named goose-fs. Public source: [carabistouflette/goose-fs](https://github.com/carabistouflette/goose-fs).
For Git dependencies, pin a reviewed full commit rather than a moving branch. See [the runnable example](examples/read.goose).

## Interface

| Function | Behavior |
| --- | --- |
| `read(path, limit, out)` | Replace caller-owned bytes with a bounded regular-file read |
| `list(path, byte_limit, entry_limit, out)` | Replace caller-owned entries with owned names and kind hints |
| `create_file(path, data)` | Exclusive creation, mode 0600 subject to umask |
| `create_dir(path)` | Exclusive creation, mode 0700 subject to umask |
| `remove_file(path)` | Unlink a non-directory entry, including a final symlink |
| `remove_empty_dir(path)` | Remove an empty directory |
| `metadata(path, out)` | Inspect final-entry type, identity, size, permissions and timestamps without following links |
| `exists(path)`, `is_dir(path)` | Error-preserving, no-follow entry predicates |
| `list_sorted(path, byte_limit, entry_limit, out)` | Bytewise sorted owned entries |
| `rename(from, to, options)`, `rename_at(root, from, to, options)` | Move entries with replace/no-replace, explicit outcomes and optional checked parent sync |
| Root APIs | Held-directory relative reads/listings/metadata/create/remove and child Roots; see [Root contract](docs/ROOTS.md) |
| Context/File APIs | Explicit resource ownership, bounded streaming/positioned I/O, duplicate/seek/truncate/sync and held-file metadata; see [File contract](docs/HANDLES.md) |

Operations return `Status { error, os_error }`; predicates return `(bool, Status)`.
Errors distinguish invalid input,
limits, nonregular reads, and OS failures. Read/list outputs are empty on any
reported failure. Paths and file contents are bytes, without UTF-8 conversion.

The absolute-path APIs require absolute paths, with no NUL, repeated separators, trailing separator,
`.` or `..` components. `/` is accepted by read/list/metadata and predicates; reading it reports NotRegular.
Listing also accepts `ListOptions { byte_limit, entry_limit, adaptive }` in place
of the two limits. Full staging is the default and uses one enumeration. Opting
into `adaptive: true` reduces initialization for small results with oversized
budgets, while large results require a second pass.

Fixed limits: 4095 path bytes, 1 MiB read/write/list payload, 4096 entries.
Root methods accept strict relative paths with a separate 4095-byte argument limit;
see [directory-relative rules](docs/ROOTS.md).
Listing payload counts each name plus two bytes of internal framing. Ordinary listing
order is unspecified and kinds are hints; use metadata for precise type information.
Sorted listing adds a bounded heap sort and extra owned-name/reference storage.
Variable-size Entry values support iteration:

```goose
var entries: fs::Entry[>..] = [];
let result = fs::list("/tmp", 65536, 256, entries);
if result.error == fs::Error.None {
    for entry in entries { print("name length: ", entry.name.len); }
}
```

Do not borrow an input path from output storage that the same call clears; Goose
rejects that lifetime conflict. Names own their bytes and survive later calls
when copied to separate storage. The one-shot API retains no native pointers or descriptors. Retained Files use a synchronized process-wide registry; see the [ownership and I/O contract](docs/HANDLES.md). Metadata predicates describe the
entry itself: dangling links exist, directory links are not directories, and
permission errors are not reported as absence. Creation time is optional; changed
time means inode status change.

This library provides a symlink-resolution policy, not confinement or snapshots.
Hard links, mounts, and concurrent renames remain possible. Failed creation may
leave a partial newly created file; no rollback or durability guarantee. Regular
filesystem I/O has no deadline. Final read targets are opened before their type
is checked; device-open side effects remain possible. See the full
[interface and security contract](docs/API.md).

## Development

```sh
git clone https://github.com/carabistouflette/goose-fs.git
cd goose-fs
make setup
make format check test CC=gcc
make test CC=clang
make sanitize SANITIZER_CC=gcc
make sanitize SANITIZER_CC=clang
make bench BENCH_ITERATIONS=100
.toolchain/goose/build/goose run examples/read.goose -- "$PWD/README.md"
```

Builds need Linux headers providing openat2 (5.6+); older runtime kernels use
the descriptor-walk fallback. NoReplace rename also needs runtime renameat2 and
filesystem support; unsupported requests return an error. The full rename tests
use a local filesystem supporting NoReplace and directory fsync.
ENOSYS/EPERM trigger the parent-lookup fallback without caching
global feature state. Setup requires Git, CMake 3.27+, C/C++20 compilers and Make. Tests require Python
3.11+, Linux `/proc`, GCC and Clang for the full matrix. The retained-handle capacity
test needs a hard descriptor limit of at least 5000. GOOSE_REVISION pins the
same compiler as goose-json. An existing matching binary can be selected with
`make GOOSE=/absolute/path/to/goose ...`. Compatibility with other revisions is
not guaranteed. Setup refuses modified compiler source and hidden index flags.
Run one Make invocation per checkout; Goose shares generated C output paths.

Validation includes JIT/native/debug public behavior, ownership and immutable-bound
compile rejections, consumer-overload isolation, an independent Python filesystem
oracle, binary names and contents, symlinks/FIFOs/devices, descriptor leaks, concurrent symlink swaps, exact maximum listing limits,
closed standard descriptors, actual descriptor exhaustion/recovery, fork/exec
noninheritance, forced syscall fallbacks, protected
buffer boundaries, malformed private ABI inputs, and injected short I/O, EINTR,
zero progress, disk-full and close failures. GCC/Clang ASan/UBSan exercise the public
interface and native kernel. Goose uses mmap-backed data stacks; sanitizers do not
independently cover every logical array lifetime or bound, so debug checks and
independent oracles are also required. CI smoke-runs [benchmarks](bench/README.md)
without timing thresholds. See the [measured audit results](bench/results/2026-11-04/README.md)
for all workloads, raw samples and reproduction commands. No universal performance
claim is made.

Rust `std::fs`, Go `os`, and Goose's standard library define the feature and
performance comparison targets. See the [Linux coverage record](docs/feature-coverage.md)
and [versioned comparison research](docs/comparison-research.md). Full Linux
coverage comes first, followed by macOS and Windows. Current APIs cover a subset;
cross-library speed claims require measured results and matching safety policies.
The [native API task measurements](bench/results/2026-11-04-native-api/README.md)
retain every comparator cell and policy difference; the
[read-reuse measurement](bench/results/2026-11-04-read-reuse/README.md) isolates
the initialized-buffer optimization.
Shared/exclusive locks support immediate attempts and polling waits; see the
[locking contract](docs/LOCKS.md).
The [uncontended lock comparison](bench/results/2026-11-04-locks/README.md)
records current overhead against Rust and leaves unsupported APIs visible.
The [retained File measurements](bench/results/2026-11-04-retained/README.md)
add positioned reads with open/close outside timing and disclose lifetime-check
costs, unsupported stdlib operations and remaining comparison limits.
The [Root task comparison](bench/results/2026-11-04-roots/README.md) includes Go
os.Root with names-only enumeration and retains its faster metadata/listing cells.
The [explicit staging comparison](bench/results/2026-11-04-listing-staging/README.md)
keeps full and adaptive strategies separate, including every long-name regression.
The [adaptive four-library profile](bench/results/2026-11-04-adaptive-native-api/README.md)
records the selected option, unsupported cells, and mixed Rust/Go/Goose results.

[Rename outcomes](docs/RENAME.md) distinguish an unattempted operation, confirmed
application (including no-ops), and an uncertain error. Parent synchronization
is optional and reports late errors without implying rollback.

The current version excludes recursive operations, temp-directory lifecycle,
path normalization, byte publication/installation helpers, streaming directory
cursors and Windows support.
See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

[Apache-2.0](LICENSE). Copyright 2026 goose-fs contributors.
