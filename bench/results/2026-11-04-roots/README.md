# Directory Root and native task costs — 2026-11-04

Recorded experiment, with the source and toolchain identities stated below.
These tables are not automatically measurements of current main. See
[the currentness inventory](../../../docs/PERFORMANCE.md) before applying them.
To rebuild an experiment, use its measured source revision in a separate checkout.
For the retained raw artifacts and original replay scripts, use publication
`60cec1e1956962772fff6091b4c7ff1876533f9e`. Historical raw artifacts are unchanged.

Measured clean source: `599604a6fecc66915c47944f9779b4e34f8a61db`; Root implementation `6b4807960f9869c10be2741bdf4074d385a9aecc`. [All raw samples and verified provenance](raw.json) · [Interactive chart](comparison.html). Source/binary/fixture hashes and toolchain versions/settings are retained, including the Goose compiler hash.

Five shuffled process rounds, seven sample means per workload/runner/round, 200 calls per sample. 3,500 rows including 490 unsupported; table values are median sample means in ns/call. Warm tmpfs, shared Intel Core Ultra7 258V Linux host, CPU6 affinity. No exclusive-core/frequency isolation; small differences may be noise.

Root cases retain a directory opened before timing. Fresh 64-byte reads, final-entry metadata and sorted 128-name enumeration include per-operation lookup/open/read/close where applicable. The Go names task uses Root.Open+File.Readdirnames(-1)+slices.Sort, avoiding the unused eager metadata work performed by Root DirEntry enumeration. Goose-fs additionally returns kind hints and initializes a 1 MiB staging budget. Rust std and the pinned Goose stdlib lack an equivalent Root API and receive unsupported cells. Root/context setup/close are excluded.

In this run goose-fs Root fresh 64-byte reads take 2,895 ns versus Go 5,993 ns (about 2.07x as fast). Metadata takes 1,078 ns versus 909 ns (about 19% more), and sorted names take 63,679 ns versus 34,852 ns (about 83% more). The oversized listing buffer remains a measured optimization target. These are differing native API task costs, not equal-security or universal speed conclusions. Go Root permits in-tree symlinks; goose-fs rejects them and uses a narrower relative grammar.

| Workload | goose-fs ns | Goose stdlib ns | Rust ns | Go ns |
| --- | ---: | ---: | ---: | ---: |
| read-fresh-0 | 2,945 | 2,071 | 1,842 | 4,475 |
| read-reuse-0 | 2,743 | 2,005 | 1,996 | 3,129 |
| read-retained-0 | 90 | unsupported | 185 | 8 |
| read-fresh-64 | 3,110 | 2,663 | 2,174 | 4,646 |
| read-reuse-64 | 3,018 | 2,603 | 2,268 | 3,558 |
| read-retained-64 | 374 | unsupported | 272 | 340 |
| read-fresh-4096 | 3,199 | 2,815 | 2,108 | 6,709 |
| read-reuse-4096 | 2,935 | 2,766 | 2,117 | 4,058 |
| read-retained-4096 | 483 | unsupported | 376 | 452 |
| read-fresh-65536 | 8,564 | 8,399 | 5,606 | 18,484 |
| read-reuse-65536 | 6,263 | 8,146 | 5,435 | 7,206 |
| read-retained-65536 | 3,904 | unsupported | 3,938 | 3,888 |
| read-fresh-1048576 | 107,006 | 147,552 | 87,319 | 362,503 |
| read-reuse-1048576 | 83,798 | 138,913 | 77,823 | 113,710 |
| read-retained-1048576 | 63,688 | unsupported | 72,701 | 92,558 |
| list-sorted-0 | 29,983 | 2,197 | 2,127 | 2,931 |
| list-sorted-1 | 29,573 | 2,387 | 2,300 | 3,185 |
| list-sorted-128 | 53,030 | 22,226 | 34,243 | 41,474 |
| list-sorted-4096 | 3,308,200 | 2,735,861 | 2,087,429 | 4,337,448 |
| metadata-file | 1,843 | unsupported | 554 | 939 |
| lock-exclusive-pair | 722 | unsupported | 426 | unsupported |
| is-dir | 1,769 | 590 | 537 | 1,043 |
| root-read-fresh-64 | 2,895 | unsupported | unsupported | 5,993 |
| root-metadata-file | 1,078 | unsupported | unsupported | 909 |
| root-list-sorted-128 | 63,679 | unsupported | unsupported | 34,852 |

All previous workloads and slower cells remain visible. Metadata materialization, output representations, lookup/error/EOF policies and allocation ownership differ. Whole-process VmHWM includes validation, registry initialization, allocator/GC history and retained sinks; it is not per-operation memory or allocations. Full-pattern/name preflights run outside timers; fresh timed reads receive length/endpoints checks, not a full-content postcheck. Root staging uses 1 MiB/4096 entries. The lock pair is uncontended; no polling/fairness/concurrency conclusions. See [all policies](../../compare/README.md), [Root contract](../../../docs/ROOTS.md), and [remaining coverage](../../../docs/feature-coverage.md).

## Reproduce

Check out measured source `599604a6fecc66915c47944f9779b4e34f8a61db`, install the pinned compiler and recorded Rust/Go toolchains, then:

```sh
python3 bench/compare/build.py --goose .toolchain/goose/build/goose --cc gcc
python3 bench/compare/run.py --goose .toolchain/goose/build/goose --cc gcc \
  --iterations 200 --rounds 5 --seed 20261104 --output .build/compare/roots.json
```

The recorded run used `taskset -c 6`. Select an available core and avoid overlapping your own timing jobs. Source/binary/toolchain inputs are verified before/after measurement. Every checksum and supported/unsupported state must match. A hardened-adapter profile is still needed before equal-policy comparisons.

## Validation

Independent implementation/security and quality reviews completed; documentation inconsistencies were corrected. Both GCC and Clang passed full public/JIT/debug/native/OS/fault/fallback/worker suites and ASan/UBSan. Native Root checks cover parent-only fallback flags and errno preservation, wrong-kind/stale tokens, mixed 4096-slot capacity before mutation, live children after parent closure, renamed/replaced Root identity, independent concurrent cursors, binary names, cumulative paths beyond 4095 bytes, FD cleanup/CLOEXEC, and 20,000 ancestor-symlink race probes per Root oracle backend. All 97,665 grammar cases agree across Python, C and optimized/debug Goose. Tests cannot prove absence of bugs.
