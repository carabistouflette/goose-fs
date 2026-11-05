# Uncontended locks and native task measurements — 2026-11-04

Recorded experiment, with the source and toolchain identities stated below.
These tables are not automatically measurements of current main. See
[the currentness inventory](../../../docs/PERFORMANCE.md) before applying them.
To rebuild an experiment, use its measured source revision in a separate checkout.
For the retained raw artifacts and original replay scripts, use publication
`60cec1e1956962772fff6091b4c7ff1876533f9e`. Historical raw artifacts are unchanged.

Measured clean source: `42db4b6abca3cad711146bce83419ca2387a4ca6`. Lock implementation: `ea82d8f` (full implementation is an ancestor of the measured commit). [All raw samples and verified build provenance](raw.json) · [Interactive chart](comparison.html). Source/binary/fixture hashes and toolchain versions/settings are retained, including the Goose compiler executable hash.

Five shuffled process rounds, seven sample means per workload/runner/round, 200 calls per sample. 3,080 rows, including 280 unsupported rows. Values below are median sample means in ns/call. Warm tmpfs, GCC16.2.1/O2, Rust1.99.1/O2, recorded Go toolchain; shared Intel Core Ultra7 258V Linux host, CPU6 affinity. No exclusive core or CPU-frequency isolation; small changes may be noise.

The lock case measures an uncontended exclusive try-acquire/unlock pair through a retained readonly File. Initialization/open/close are excluded, while token validation and Context/entry locks remain timed. Both implementations perform an untimed warm pair. Go os and the pinned Goose stdlib have no portable File locking API, so those cells are unsupported; an OS adapter would be a separate profile.

goose-fs measured 746 ns per pair versus Rust 583 ns in this run, about 28% more time. Its explicit lifetime checks and wrapper costs remain performance work; this is not a speed-superiority result. No contention, polling wakeup, fairness or concurrent-I/O performance is inferred. The polling cleanup/sleep-error behavior is covered by correctness tests rather than these timings.

| Workload | goose-fs ns | Goose stdlib ns | Rust ns | Go ns |
| --- | ---: | ---: | ---: | ---: |
| read-fresh-0 | 3,722 | 2,466 | 2,153 | 5,594 |
| read-reuse-0 | 3,613 | 2,503 | 2,343 | 3,932 |
| read-retained-0 | 106 | unsupported | 227 | 10 |
| read-fresh-64 | 4,174 | 3,275 | 2,677 | 6,131 |
| read-reuse-64 | 4,093 | 3,296 | 2,827 | 4,772 |
| read-retained-64 | 468 | unsupported | 342 | 457 |
| read-fresh-4096 | 4,392 | 3,601 | 2,823 | 8,597 |
| read-reuse-4096 | 4,099 | 3,715 | 2,843 | 5,319 |
| read-retained-4096 | 632 | unsupported | 496 | 617 |
| read-fresh-65536 | 12,461 | 11,697 | 7,574 | 27,741 |
| read-reuse-65536 | 9,751 | 11,177 | 7,539 | 10,393 |
| read-retained-65536 | 5,589 | unsupported | 5,367 | 5,495 |
| read-fresh-1048576 | 202,303 | 191,826 | 134,897 | 384,727 |
| read-reuse-1048576 | 141,850 | 190,061 | 142,917 | 151,874 |
| read-retained-1048576 | 146,332 | unsupported | 151,563 | 137,974 |
| list-sorted-0 | 51,261 | 2,731 | 2,730 | 3,769 |
| list-sorted-1 | 47,804 | 2,917 | 2,953 | 3,624 |
| list-sorted-128 | 91,404 | 26,971 | 41,561 | 50,074 |
| list-sorted-4096 | 3,483,061 | 2,754,767 | 2,741,567 | 4,639,198 |
| metadata-file | 1,910 | unsupported | 743 | 1,171 |
| lock-exclusive-pair | 746 | unsupported | 583 | unsupported |
| is-dir | 1,884 | 655 | 731 | 1,214 |

All other rows remain visible, including slow small listings and no-follow metadata costs. Native path/ownership/output contracts differ: this is not an equal-security ranking or full feature-parity claim. Listings initialize a 1 MiB budget in goose-fs even when empty; representations/kind hints and metadata field demand differ. Retained reads exclude open/close and can have different short-read/EOF/syscall behavior; zero-byte calls can avoid syscalls. See [comparison policies](../../compare/README.md), [File lifecycle](../../../docs/HANDLES.md) and [locking semantics](../../../docs/LOCKS.md).

Full-pattern/name preflight checks occur outside timers. Timed checksums consume read length/endpoints or listing names; fresh timed reads have no full-content postcheck. Whole-process VmHWM includes validation, registry initialization, allocator/GC history and retained Go sinks, not per-operation memory or allocation counts. A hardened-adapter profile and contended/concurrent measurements remain required before corresponding performance claims.

## Reproduce

Check out measured source `42db4b6abca3cad711146bce83419ca2387a4ca6` and install the recorded toolchains/pinned Goose compiler, then:

```sh
python3 bench/compare/build.py --goose .toolchain/goose/build/goose --cc gcc
python3 bench/compare/run.py --goose .toolchain/goose/build/goose --cc gcc \
  --iterations 200 --rounds 5 --seed 20261104 --output .build/compare/locks.json
```

The recorded run used `taskset -c 6`. Use an available core and avoid overlapping your own timing jobs. All checksums and supported/unsupported states must match. The runner rejects changed build inputs/binaries/toolchains before and after timing.

## Validation

Independent security and quality/performance reviews identified and fixed a denied-sleep busy-spin before publication. The wait now resumes EINTR remainder and propagates other sleep errors. A test-only native observer deterministically verifies the public wrapper enters its pause, returns denied-sleep EPERM after one attempt, and permits ContextClose during an observed pause. Cross-process shared/exclusive contention, independent-open vs duplicate state, conversion, last-close release and parent-owned cleanup after contained abort pass. Full GCC/Clang public/JIT/debug/oracle/fault/fallback suites and both ASan/UBSan matrices pass; retained/lock OS oracles also passed on two CPU cores. No production test observer is installed. Tests do not prove absence of bugs.
