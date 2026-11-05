# goose-fs

Filesystem operations for [Goose](https://github.com/aardappel/goose): bounded
reads, directory listings, metadata, streaming files, locks and atomic entry
rename. Paths and contents are bytes, including non-UTF-8 names.

**Support:** experimental API on 64-bit Linux; the test matrix uses x86-64/glibc.
Other Linux libcs/architectures are not fully validated. There are no tags or GitHub
releases as of this documentation audit. These docs describe `main`; pin a full
commit for use in an application. macOS and Windows are not supported.

## Try it

You need Git, Make, CMake 3.27+, C/C++20 compilers and Linux headers with openat2.
Setup builds the Goose revision in [GOOSE_REVISION](GOOSE_REVISION).

```sh
git clone https://github.com/carabistouflette/goose-fs.git
cd goose-fs
make setup
mkdir -p .build
printf 'hello\n' > .build/hello.txt
.toolchain/goose/build/goose run examples/read.goose -- "$PWD/.build/hello.txt"
```

Expected output: `read 6 bytes`. To stream larger files or list a directory:

```sh
.toolchain/goose/build/goose run examples/stream.goose -- "$PWD/.build/hello.txt"
.toolchain/goose/build/goose run examples/root.goose -- "$PWD/examples"
```

An application next to the checkout can import `fs from "../goose-fs"` in its
root source. [examples/read.goose](examples/read.goose) is a complete program.

## What it provides

| Task | API and guide |
|---|---|
| Whole-file reads and owned directory entries | `read`, `list`, `list_sorted`; [API](docs/API.md) |
| Entry metadata and existence | `metadata`, `exists`, `is_dir`; [API](docs/API.md) |
| Exclusive creation and individual removal | `create_file`, `create_dir`, `remove_file`, `remove_empty_dir` |
| Streaming and positioned I/O | Context/File open, read, write, seek, truncate, sync, duplicate and close; [File guide](docs/HANDLES.md) |
| Directory-relative operations | Root/child Root and `_at` operations; [Root guide](docs/ROOTS.md) |
| Symlink target bytes | `read_link`, `read_link_at`; [link guide](docs/READ-LINK.md) |
| File permissions, ownership and times | `set_permissions`, `set_owner`, `set_times`; [metadata guide](docs/FILE-METADATA.md) |
| Cooperative file locks | `try_lock_file`, `lock_file`, `unlock_file`; [lock guide](docs/LOCKS.md) |
| Entry rename | `rename`, `rename_at`, replace/no-replace and optional parent sync; [rename guide](docs/RENAME.md) |

Calls return explicit status; `os_error` is meaningful only for `SystemError`.
Read/list outputs are empty on error. Close every Context; copied File/Root tokens
share lifetime unless explicitly duplicated.

Absolute APIs reject symlink ancestors and require absolute paths without NUL,
empty, `.` or `..` components or trailing `/`. Root APIs use strict relative paths.
Limits are 4095 input path bytes, 1 MiB per I/O request or listing payload, and
4096 listing entries. Listing payload includes each name plus two framing bytes.
Streaming can process larger files in bounded chunks.

These rules do not provide a sandbox or snapshot: mounts, hard links and
concurrent renames remain possible. I/O has no deadline. Creation errors can
leave partial files; rename errors need the [outcome rules](docs/RENAME.md).
See [API limits](docs/API.md), [platform/feature coverage](docs/feature-coverage.md)
and [security reporting](SECURITY.md). Recursive operations, copy/install helpers,
streaming directory cursors and link creation remain unavailable.

## Tests and measurements

```sh
make check test CC=gcc
make sanitize SANITIZER_CC=gcc
make test CC=clang
make sanitize SANITIZER_CC=clang
```

Tests also need Python 3.11+, `/proc`, GCC/Clang, and a filesystem supporting the
operations under test. Run one Make invocation per checkout. Further test and
filesystem requirements are in [CONTRIBUTING.md](CONTRIBUTING.md).

[Performance results and their scope](docs/PERFORMANCE.md) distinguish measurements
of the current implementation from historical experiments. Costs depend on the
operation and comparison policy; the library is not fastest in every workload.
[Benchmark commands](bench/README.md) and raw data are provided separately.

[Apache-2.0](LICENSE). Copyright 2026 goose-fs contributors.
