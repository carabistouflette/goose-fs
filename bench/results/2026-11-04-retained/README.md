# Retained File and native task measurements — 2026-11-04

Recorded experiment, with the source and toolchain identities stated below.
These tables are not automatically measurements of current main. See
[the currentness inventory](../../../docs/PERFORMANCE.md) before applying them.
To rebuild an experiment, use its measured source revision in a separate checkout.
For the retained raw artifacts and original replay scripts, use publication
`60cec1e1956962772fff6091b4c7ff1876533f9e`. Historical raw artifacts are unchanged.

Measured source: `ddaaf8de8cd06dfa836f1ca14298e579e84a12a9` (clean source/build). File implementation: `bf763fd89a291ce0108059e473b226c34b81a74c`. [Raw data](raw.json) include the verified build manifest, source/binary/fixture hashes and toolchain versions/settings (including the Goose compiler hash), compiler flags, inherited settings, affinity/load and every sample. [Interactive chart](comparison.html).

Five shuffled process rounds; seven sample means per workload/runner/round; 200 calls per sample. 2,940 rows, including 210 unsupported rows (Goose stdlib lacks general metadata and retained Files). Median sample means below are nanoseconds per call, not individual-call latency. Warm tmpfs on shared Intel Core Ultra 7 258V Linux host, CPU6 affinity; no exclusive-core/frequency isolation.

Retained cases open once before timing and use offset-zero positioned reads into initialized reusable storage. Context initialization and open/close are excluded; token validation, Context/entry locks and I/O remain timed. Exact-size stable fixtures are intended to permit one successful pread for nonempty data, but syscall counts are not measured. Go ReadAt has a general fill/EOF contract; Rust FileExt::read_at and goose-fs read_at may return short reads. Zero-size calls can avoid syscalls. This is a sequential API task comparison, not a concurrent-I/O, cold-storage or lifecycle-cost result.

The small nonempty retained goose-fs cases cost more than Rust and are near Go in this run; its two-lock lifetime checks remain a performance cost. Larger retained reads are dominated by data movement. These numbers do not establish universal speed superiority. The other rows retain all slower paths and policy differences: goose-fs has strict bounded/no-follow paths; comparator native APIs retain their own contracts. Small goose-fs listings still initialize an oversized 1 MiB staging budget.

| Workload | goose-fs ns | Goose stdlib ns | Rust ns | Go ns |
| --- | ---: | ---: | ---: | ---: |
| read-fresh-0 | 3,581 | 2,572 | 2,409 | 6,419 |
| read-reuse-0 | 3,487 | 2,541 | 2,605 | 4,146 |
| read-retained-0 | 106 | unsupported | 257 | 10 |
| read-fresh-64 | 3,826 | 3,117 | 2,873 | 6,584 |
| read-reuse-64 | 3,848 | 3,201 | 2,977 | 4,807 |
| read-retained-64 | 465 | unsupported | 373 | 454 |
| read-fresh-4096 | 4,159 | 3,649 | 3,094 | 8,607 |
| read-reuse-4096 | 3,945 | 3,596 | 3,039 | 5,273 |
| read-retained-4096 | 626 | unsupported | 535 | 608 |
| read-fresh-65536 | 11,745 | 11,362 | 8,853 | 29,203 |
| read-reuse-65536 | 8,985 | 10,987 | 8,669 | 11,153 |
| read-retained-65536 | 5,707 | unsupported | 5,747 | 5,967 |
| read-fresh-1048576 | 199,306 | 232,602 | 156,668 | 380,374 |
| read-reuse-1048576 | 128,263 | 240,777 | 152,820 | 153,257 |
| read-retained-1048576 | 122,981 | unsupported | 141,502 | 122,119 |
| list-sorted-0 | 45,127 | 2,770 | 2,895 | 3,254 |
| list-sorted-1 | 47,226 | 3,005 | 3,210 | 3,153 |
| list-sorted-128 | 87,429 | 28,891 | 46,145 | 44,317 |
| list-sorted-4096 | 3,628,714 | 3,066,219 | 2,949,919 | 4,715,628 |
| metadata-file | 1,962 | unsupported | 843 | 1,171 |
| is-dir | 1,936 | 720 | 831 | 1,057 |

Full-pattern/ordered-name preflight checks run outside timers. Timed checksums consume length/endpoints, and fresh timed results do not receive a full-content postcheck. VmHWM is whole-suite process context including validation, registry initialization, allocators/GC and retained sinks; it is not per-operation memory or allocation count. Listing output representations and metadata materialization differ. See [all policies](../../compare/README.md) and the [File ownership/limits contract](../../../docs/HANDLES.md). A hardened-adapter profile and concurrent retained-I/O measurements remain required before corresponding claims.

## Reproduce

Check out measured source `ddaaf8de8cd06dfa836f1ca14298e579e84a12a9`, install the pinned Goose compiler, Rust 1.99.1 and the recorded Go toolchain, then:

```sh
python3 bench/compare/build.py --goose .toolchain/goose/build/goose --cc gcc
python3 bench/compare/run.py --goose .toolchain/goose/build/goose --cc gcc \
  --iterations 200 --rounds 5 --seed 20261104 --output .build/compare/retained.json
```

The recorded run used `taskset -c 6`; choose an available core on your host if pinning. Avoid overlapping your own timing series. The runner verifies source/binary/toolchain provenance before and after timing. All expected checksums and supported/unsupported states must match.

## Validation

Two independent implementation/security reviews and a separate benchmark-method review completed; concrete findings were fixed. GCC and Clang passed full public/JIT/debug behavior, native/OS oracles, forced openat2/statx fallbacks, concurrent stale-token reuse, process-wide caps, actual kernel descriptor exhaustion/recovery, exec noninheritance, partial/EINTR/zero-progress I/O, injected close continuation, unrelated blocked-I/O isolation and seeded generation saturation. Compiled workers passed cross-worker reads and parent-owned cleanup after contained abort. Both compilers passed ASan/UBSan; GCC fortified reads passed; static analysis reported no findings. These checks do not prove absence of bugs.
