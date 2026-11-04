# goose-fs

Small, bounded filesystem operations for the
[Goose programming language](https://github.com/aardappel/goose). Apache-2.0.
Experimental interface; no release yet. Linux is the initial target.

Read regular files with byte limits, list directories with structured byte-preserving
names, exclusively create files/directories, and remove individual entries.
Every directory component rejects symlinks during traversal. Goose owns validation
and returned storage; a private C kernel owns short-lived filesystem descriptors.

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

Functions return `Status { error, os_error }`. Errors distinguish invalid input,
limits, nonregular reads, and OS failures. Read/list outputs are empty on any
reported failure. Paths and file contents are bytes, without UTF-8 conversion.

Paths must be absolute, with no NUL, repeated separators, trailing separator,
`.` or `..` components. `/` is accepted by read/list; reading it reports NotRegular.
Fixed limits: 4095 path bytes, 1 MiB read/write/list payload, 4096 entries.
Listing payload counts each name plus two bytes of internal framing. Listing
order is unspecified; Kind {Unknown, File, Directory, Symlink, Other} is a hint.
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
when copied to separate storage. No retained native pointers or global state.

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
the descriptor-walk fallback. ENOSYS/EPERM trigger that fallback without caching
global feature state. Setup requires Git, CMake 3.27+, C/C++20 compilers and Make. Tests require Python
3.11+, Linux `/proc`, GCC and Clang for the full matrix. GOOSE_REVISION pins the
same compiler as goose-json. An existing matching binary can be selected with
`make GOOSE=/absolute/path/to/goose ...`. Compatibility with other revisions is
not guaranteed. Setup refuses modified compiler source and hidden index flags.
Run one Make invocation per checkout; Goose shares generated C output paths.

Validation includes JIT/native/debug public behavior, ownership and immutable-bound
compile rejections, consumer-overload isolation, an independent Python filesystem
oracle, binary names and contents, symlinks/FIFOs/devices, descriptor leaks, concurrent symlink swaps, exact maximum listing limits,
closed standard descriptors, forced syscall fallbacks, protected
buffer boundaries, malformed private ABI inputs, and injected short I/O, EINTR,
zero progress, disk-full and close failures. GCC/Clang ASan/UBSan exercise the public
interface and native kernel. Goose uses mmap-backed data stacks; sanitizers do not
independently cover every logical array lifetime or bound, so debug checks and
independent oracles are also required. CI smoke-runs [benchmarks](bench/README.md)
without timing thresholds. No universal performance claim is made.

The first version excludes recursive operations, locks, temp-directory lifecycle,
path normalization, atomic publication, streaming and Windows support.
See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

[Apache-2.0](LICENSE). Copyright 2026 goose-fs contributors.
