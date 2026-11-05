# Adaptive listing and native task costs — 2026-11-04

Recorded experiment, with the source and toolchain identities stated below.
These tables are not automatically measurements of current main. See
[the currentness inventory](../../../docs/PERFORMANCE.md) before applying them.
To rebuild an experiment, use its measured source revision in a separate checkout.
For the retained raw artifacts and original replay scripts, use publication
`60cec1e1956962772fff6091b4c7ff1876533f9e`. Historical raw artifacts are unchanged.

Measured clean source: `070a899ad7491596f7dc743fe386cf58ffbf8517`. [All raw samples and verified provenance](raw.json) · [Interactive chart](comparison.html). This profile explicitly opts goose-fs sorted absolute/Root listings into ListOptions.adaptive=true; existing/default full staging is unchanged. [The three-variant long-name profile](../2026-11-04-listing-staging/README.md) retains adaptive regressions and refactor controls.

Five shuffled process rounds, seven sample means per workload/runner/round, 200 calls per sample. All 3,500 rows, including 490 unsupported, are retained. Values are median sample means in ns/call. Warm tmpfs, shared Intel Core Ultra7 258V Linux host, CPU6 affinity, without exclusive-core/frequency isolation.

Results remain mixed. Sorted 128-name absolute listings take 41,121 ns for goose-fs, 29,462 ns for Goose stdlib, 44,221 ns for Rust and 52,803 ns for Go. Root 128-name sorted listings take 40,500 ns versus Go 41,076 ns, a difference too small for a strong conclusion here. Empty/singleton listing remains slower than the alternatives. All slower cells remain visible, and these differing native API task costs do not establish equal-security performance or universal superiority.

| Workload | goose-fs adaptive ns | Goose stdlib ns | Rust ns | Go ns |
| --- | ---: | ---: | ---: | ---: |
| read-fresh-0 | 3,246 | 2,314 | 2,238 | 5,464 |
| read-reuse-0 | 3,309 | 2,299 | 2,351 | 3,901 |
| read-retained-0 | 102 | unsupported | 232 | 9 |
| read-fresh-64 | 3,770 | 3,098 | 2,701 | 5,979 |
| read-reuse-64 | 3,751 | 3,109 | 2,926 | 4,393 |
| read-retained-64 | 452 | unsupported | 353 | 416 |
| read-fresh-4096 | 4,003 | 3,333 | 2,852 | 8,188 |
| read-reuse-4096 | 3,903 | 3,340 | 2,909 | 5,097 |
| read-retained-4096 | 628 | unsupported | 501 | 581 |
| read-fresh-65536 | 11,841 | 10,506 | 7,750 | 26,984 |
| read-reuse-65536 | 8,937 | 10,455 | 8,090 | 9,578 |
| read-retained-65536 | 5,317 | unsupported | 5,188 | 5,345 |
| read-fresh-1048576 | 195,214 | 215,018 | 116,130 | 368,614 |
| read-reuse-1048576 | 141,405 | 202,861 | 128,211 | 136,686 |
| read-retained-1048576 | 132,025 | unsupported | 123,789 | 117,327 |
| list-sorted-0 | 6,961 | 2,757 | 2,827 | 3,648 |
| list-sorted-1 | 7,054 | 2,993 | 2,914 | 4,040 |
| list-sorted-128 | 41,121 | 29,462 | 44,221 | 52,803 |
| list-sorted-4096 | 3,228,354 | 2,841,917 | 2,743,704 | 4,487,506 |
| metadata-file | 1,877 | unsupported | 745 | 1,078 |
| lock-exclusive-pair | 751 | unsupported | 580 | unsupported |
| is-dir | 1,805 | 658 | 717 | 1,130 |
| root-read-fresh-64 | 2,969 | unsupported | unsupported | 6,928 |
| root-metadata-file | 1,128 | unsupported | unsupported | 1,033 |
| root-list-sorted-128 | 40,500 | unsupported | unsupported | 41,076 |


Absolute goose-fs listing returns sorted owned names plus kind hints with 1 MiB/4096-entry hard bounds. Adaptive staging starts at 64 KiB; all short-name fixtures in this profile fit one pass. Longer accepted names can need two passes and become slower. Rust uses read_dir+owned OsString sort; Go uses sorted os.ReadDir; Goose stdlib uses newline-packed names. Root Go uses Root.Open+File.Readdirnames(-1)+slices.Sort, avoiding unused eager DirEntry metadata. Go Root permits in-tree links; goose-fs rejects them and uses strict relative components. Rust std and pinned Goose stdlib lack matching Root APIs and remain unsupported.

Fresh/reused/retained reads, no-follow metadata demand, retained token/lock checks and uncontended lock-pair tasks are unchanged. Full pattern/name checks run outside timers; timed checksums consume lengths/endpoints. Fresh timed reads have no full-content postcheck. Whole-process VmHWM includes registry initialization, validation, allocator/GC history and retained sinks; it is not per-operation memory or allocations. No polling/fairness/cold-storage/concurrency claim. See [all policies](../../compare/README.md), [Root contract](../../../docs/ROOTS.md), and [remaining coverage](../../../docs/feature-coverage.md). A separately labelled hardened-adapter profile and broader Linux feature work remain outstanding.

## Reproduce

Check out measured source, install the pinned Goose compiler and recorded Rust/Go toolchains, then:

```sh
python3 bench/compare/build.py --goose .toolchain/goose/build/goose --cc gcc --adaptive-listing
python3 bench/compare/run.py --goose .toolchain/goose/build/goose --cc gcc --adaptive-listing \
  --iterations 200 --rounds 5 --seed 20261104 --output .build/compare/adaptive-final.json
```

The recorded run used `taskset -c 6`. Every source/binary/toolchain input was verified before/after measurement. The build manifest binds the adaptive choice; a mismatched default run was tested and rejected before timing. Compiler executable hash, toolchain versions/settings, fixture hashes, raw batches and process peak RSS are retained. No other heavy goose-fs job ran during timing; other projects' shared-host activity was not excluded.

## Validation

Independent implementation/security and quality/performance reviews passed; both GCC and Clang full test and ASan/UBSan matrices passed. Native static analysis passed. [Boundary/fault validation and every staging cost](../2026-11-04-listing-staging/README.md) cover both full and adaptive choices. Source and executable provenance were clean and stable throughout these measurements. Full Linux parity, other platforms, and universal speed superiority have not been achieved.
