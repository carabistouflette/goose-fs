# Native filesystem task costs — 2026-11-04

Measured source: `81e304c7938373355ac3c20b9135ac4eeb9bc843` (clean source tree). The raw result embeds the build manifest, source/binary/fixture SHA256 values, exact toolchains, flags, selected inherited settings, process order and all samples. Later documentation does not change the measured implementation.

This compares public native APIs with different safety, ownership and output contracts. **It does not establish equal-security performance or full feature parity.** goose-fs rejects ancestor links and enforces strict absolute paths, regular reads and byte bounds; ordinary comparators follow links during traversal. All fixtures are trusted, stable and ASCII. See [policies and limitations](../../compare/README.md).

Host: Intel(R) Core(TM) Ultra 7 258V; Linux-7.2.11-arch1-1-x86_64-with-glibc2.44; filesystem `tmpfs`; affinity [6]. No exclusive core or CPU-frequency isolation. Five shuffled process rounds, seven samples per workload and runner per round, 200 calls per sample; 2,240 raw rows including unsupported rows. The table reports median per-sample means in nanoseconds, not individual-call latency. Warm-cache shared-host measurements; small differences can be noise.

[Interactive chart](comparison.html) · [All raw samples and provenance](raw.json)

| Workload | goose-fs ns | Goose stdlib ns | Rust ns | Go ns |
| --- | ---: | ---: | ---: | ---: |
| read-fresh-0 | 3,406 | 2,498 | 2,309 | 5,426 |
| read-reuse-0 | 3,412 | 2,510 | 2,467 | 4,322 |
| read-fresh-64 | 3,839 | 3,255 | 2,711 | 5,777 |
| read-reuse-64 | 3,825 | 3,258 | 2,914 | 4,753 |
| read-fresh-4096 | 4,187 | 3,678 | 2,963 | 7,878 |
| read-reuse-4096 | 3,970 | 3,726 | 3,013 | 5,299 |
| read-fresh-65536 | 12,955 | 12,176 | 8,087 | 27,400 |
| read-reuse-65536 | 9,795 | 12,084 | 8,184 | 11,151 |
| read-fresh-1048576 | 216,289 | 242,930 | 155,717 | 391,455 |
| read-reuse-1048576 | 153,851 | 240,107 | 166,772 | 160,730 |
| list-sorted-0 | 53,549 | 2,843 | 2,959 | 3,748 |
| list-sorted-1 | 55,635 | 3,190 | 3,124 | 4,058 |
| list-sorted-128 | 92,450 | 31,236 | 45,967 | 54,668 |
| list-sorted-4096 | 3,913,141 | 3,429,907 | 3,361,172 | 4,918,853 |
| metadata-file | 1,908 | unsupported | 741 | 1,072 |
| is-dir | 1,907 | 679 | 725 | 1,043 |

Large reused reads benefit from preserving initialized storage. goose-fs is slower in several cells: metadata/predicates retain the extra traversal policy, while its small sorted listings pay for initializing a 1 MiB staging budget. Listings also differ in owned representation and kind-hint work. Native metadata wrappers do not necessarily materialize the same unused fields. These are remaining performance targets, not omitted results.

VmHWM is sampled after the whole process suite and includes validation, previous workloads, allocator/GC state and retained Go sinks. It is not a per-operation memory or allocation measurement. Full pattern/name preflight checks occur outside timers; timed read checks consume length and endpoint bytes. Fresh timed results do not receive a full-content postcheck.

## Reproduce

Use source `81e304c7938373355ac3c20b9135ac4eeb9bc843` and install the pinned Goose compiler (`make setup`), stable Rust 1.99.1 and the recorded Go version. Then:

```sh
python3 bench/compare/build.py --goose .toolchain/goose/build/goose --cc gcc
python3 bench/compare/run.py --goose .toolchain/goose/build/goose --cc gcc \
  --iterations 200 --rounds 5 --seed 20261104 --output .build/compare/reproduced.json
```

The recorded run used `taskset -c 6`; optionally pin to an available core on your machine. Run one compilation per checkout and avoid overlapping your own measurement processes. The runner rejects stale source, binary or toolchain provenance. A hardened-adapter profile is still required before an equal-policy comparison.
