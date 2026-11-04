# Explicit listing staging costs — 2026-11-04

Measured clean source: `070a899ad7491596f7dc743fe386cf58ffbf8517`; published baseline: `caf5fc3e9d86e9963393781115027cf2a75774d1`. [All raw samples and build provenance](raw.json) · [Interactive chart](comparison.html).

Existing list/list_sorted/list_at/list_sorted_at signatures retain full-budget staging and one enumeration. ListOptions also defaults to adaptive=false. Explicit adaptive=true starts at min(byte_limit, 64 KiB), counts the full accepted directory on spill, closes all native resources, then grows/retries. Stable large directories need two passes. This is an explicit cost tradeoff, with identical limits, owned results, sorting and clear-on-error contracts.

Five shuffled process rounds, seven sample means per process, 20 calls per sample: 7,140 checked samples across 68 workloads and three variants. Nine fixtures cover empty, singleton, 4096 short names, and packed payloads around 64 KiB through 1 MiB, using legal names up to 255 bytes. Both exact and maximum budgets are included, with the 1 MiB case shared. Values below are median sample means in ns/call; Full/adaptive above 1 means adaptive was faster in this run.

For empty/singleton calls with a 1 MiB budget, current Full takes about 6.16–8.48× as long as Adaptive. Conversely, accepted 1 MiB long-name results take about 1.44–1.66× as long with adaptive staging as with Full. Native profiling isolated the extra enumeration cost; adaptive staging is opt-in to preserve one-pass behavior for existing callers. The boundary and slower cells remain in the table.

This shared Intel Core Ultra7 258V Linux/tmpfs run used CPU6 affinity without exclusive-core or frequency isolation. Baseline-versus-Full medians ranged from about 39% less to 44% more time despite the same one-pass strategy; that variation limits precise attribution of smaller differences. Do not interpret this table as proof of regression-free default timings, a confidence interval, or a universal speed claim. Raw samples and load snapshots are retained.

| Fixture | Budget | API | Baseline ns | Full ns | Adaptive ns | Full/adaptive |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| empty | 0 | absolute | 4,569 | 4,708 | 4,803 | 0.98x |
| empty | 0 | absolute-sorted | 4,637 | 5,023 | 4,749 | 1.06x |
| empty | 0 | root | 3,826 | 3,638 | 3,807 | 0.96x |
| empty | 0 | root-sorted | 3,800 | 3,896 | 3,716 | 1.05x |
| empty | 1,048,576 | absolute | 55,804 | 48,210 | 7,201 | 6.69x |
| empty | 1,048,576 | absolute-sorted | 56,414 | 48,402 | 7,628 | 6.35x |
| empty | 1,048,576 | root | 52,702 | 56,436 | 6,652 | 8.48x |
| empty | 1,048,576 | root-sorted | 61,674 | 49,445 | 5,943 | 8.32x |
| one | 12 | absolute | 4,821 | 5,114 | 4,553 | 1.12x |
| one | 12 | absolute-sorted | 4,955 | 4,637 | 4,677 | 0.99x |
| one | 12 | root | 4,003 | 3,825 | 4,282 | 0.89x |
| one | 12 | root-sorted | 4,124 | 3,798 | 4,069 | 0.93x |
| one | 1,048,576 | absolute | 44,601 | 63,275 | 8,328 | 7.60x |
| one | 1,048,576 | absolute-sorted | 45,194 | 49,217 | 7,989 | 6.16x |
| one | 1,048,576 | root | 47,661 | 57,743 | 7,429 | 7.77x |
| one | 1,048,576 | root-sorted | 54,353 | 47,651 | 6,465 | 7.37x |
| short4096 | 49,152 | absolute | 1,540,921 | 1,321,460 | 1,468,322 | 0.90x |
| short4096 | 49,152 | absolute-sorted | 2,854,230 | 2,959,687 | 3,041,801 | 0.97x |
| short4096 | 49,152 | root | 1,470,417 | 1,397,021 | 1,363,649 | 1.02x |
| short4096 | 49,152 | root-sorted | 2,956,479 | 2,894,577 | 2,863,333 | 1.01x |
| short4096 | 1,048,576 | absolute | 1,768,835 | 1,766,311 | 1,350,325 | 1.31x |
| short4096 | 1,048,576 | absolute-sorted | 3,126,469 | 3,060,665 | 3,094,436 | 0.99x |
| short4096 | 1,048,576 | root | 1,689,452 | 1,639,748 | 1,612,533 | 1.02x |
| short4096 | 1,048,576 | root-sorted | 3,169,274 | 3,044,874 | 2,897,749 | 1.05x |
| below64k | 65,535 | absolute | 157,086 | 151,948 | 157,418 | 0.97x |
| below64k | 65,535 | absolute-sorted | 184,815 | 187,348 | 220,116 | 0.85x |
| below64k | 65,535 | root | 161,074 | 163,775 | 145,873 | 1.12x |
| below64k | 65,535 | root-sorted | 156,274 | 195,151 | 200,095 | 0.98x |
| below64k | 1,048,576 | absolute | 235,172 | 229,904 | 165,866 | 1.39x |
| below64k | 1,048,576 | absolute-sorted | 346,373 | 294,364 | 206,392 | 1.43x |
| below64k | 1,048,576 | root | 228,345 | 228,443 | 162,362 | 1.41x |
| below64k | 1,048,576 | root-sorted | 290,889 | 246,755 | 199,396 | 1.24x |
| at64k | 65,536 | absolute | 165,851 | 150,323 | 159,084 | 0.94x |
| at64k | 65,536 | absolute-sorted | 195,689 | 169,675 | 210,740 | 0.81x |
| at64k | 65,536 | root | 136,047 | 157,400 | 172,307 | 0.91x |
| at64k | 65,536 | root-sorted | 206,814 | 195,776 | 202,113 | 0.97x |
| at64k | 1,048,576 | absolute | 226,009 | 243,747 | 152,922 | 1.59x |
| at64k | 1,048,576 | absolute-sorted | 210,675 | 302,360 | 199,065 | 1.52x |
| at64k | 1,048,576 | root | 267,309 | 227,418 | 159,785 | 1.42x |
| at64k | 1,048,576 | root-sorted | 263,974 | 265,766 | 189,019 | 1.41x |
| above64k | 65,537 | absolute | 161,382 | 153,874 | 255,829 | 0.60x |
| above64k | 65,537 | absolute-sorted | 205,902 | 212,517 | 312,694 | 0.68x |
| above64k | 65,537 | root | 167,521 | 148,268 | 235,041 | 0.63x |
| above64k | 65,537 | root-sorted | 201,774 | 188,446 | 335,820 | 0.56x |
| above64k | 1,048,576 | absolute | 204,151 | 207,220 | 232,508 | 0.89x |
| above64k | 1,048,576 | absolute-sorted | 285,175 | 230,541 | 263,458 | 0.88x |
| above64k | 1,048,576 | root | 181,905 | 237,498 | 256,910 | 0.92x |
| above64k | 1,048,576 | root-sorted | 280,303 | 273,287 | 228,779 | 1.19x |
| above128k | 131,073 | absolute | 300,709 | 305,817 | 539,607 | 0.57x |
| above128k | 131,073 | absolute-sorted | 476,081 | 413,450 | 617,353 | 0.67x |
| above128k | 131,073 | root | 334,265 | 332,513 | 544,471 | 0.61x |
| above128k | 131,073 | root-sorted | 435,417 | 411,955 | 706,886 | 0.58x |
| above128k | 1,048,576 | absolute | 453,452 | 299,083 | 569,060 | 0.53x |
| above128k | 1,048,576 | absolute-sorted | 550,919 | 523,008 | 617,735 | 0.85x |
| above128k | 1,048,576 | root | 429,105 | 261,502 | 464,835 | 0.56x |
| above128k | 1,048,576 | root-sorted | 560,328 | 543,508 | 714,253 | 0.76x |
| above512k | 524,289 | absolute | 1,706,541 | 1,667,914 | 2,808,961 | 0.59x |
| above512k | 524,289 | absolute-sorted | 2,461,565 | 2,384,591 | 3,549,352 | 0.67x |
| above512k | 524,289 | root | 1,890,338 | 1,728,072 | 2,884,605 | 0.60x |
| above512k | 524,289 | root-sorted | 2,404,827 | 2,419,384 | 3,758,970 | 0.64x |
| above512k | 1,048,576 | absolute | 1,806,288 | 1,792,962 | 2,952,547 | 0.61x |
| above512k | 1,048,576 | absolute-sorted | 2,460,569 | 2,568,156 | 3,514,077 | 0.73x |
| above512k | 1,048,576 | root | 1,545,317 | 1,755,926 | 2,835,396 | 0.62x |
| above512k | 1,048,576 | root-sorted | 2,486,823 | 2,498,780 | 3,605,367 | 0.69x |
| max1m | 1,048,576 | absolute | 3,945,740 | 3,938,297 | 6,372,050 | 0.62x |
| max1m | 1,048,576 | absolute-sorted | 5,371,108 | 5,651,630 | 8,136,323 | 0.69x |
| max1m | 1,048,576 | root | 3,737,754 | 3,843,515 | 6,367,494 | 0.60x |
| max1m | 1,048,576 | root-sorted | 5,499,898 | 5,418,796 | 8,116,528 | 0.67x |


## Method and reproduction

All three variants share the timing/checksum harness template. The builder renders legacy public calls for baseline and current Full, and ListOptions.adaptive=true calls for current Adaptive. Every complete filename set and sorted order is independently checked before timing. Timed calls consume entry count, name lengths and endpoints. Initialization, enumeration, retries, owned-name construction and checksum work are timed; Context/Root creation, warmup, formatting and full-name verification are excluded. No allocation or per-operation memory measurement is claimed.

The manifest binds baseline/current sources, template, rendered inputs, Goose compiler executable and binary hashes, compiler version and flags. Inputs are verified before/after timing. The source revision was clean throughout. The relative-output-directory CLI was also built successfully from another working directory.

Check out measured source and install its pinned compiler, then:

```sh
python3 bench/listing-build.py --goose .toolchain/goose/build/goose --cc gcc \
  --baseline-revision caf5fc3e9d86e9963393781115027cf2a75774d1
python3 bench/listing-measure.py --goose .toolchain/goose/build/goose --cc gcc \
  --baseline .build/listing-pair/baseline --full .build/listing-pair/full \
  --adaptive .build/listing-pair/adaptive \
  --baseline-revision caf5fc3e9d86e9963393781115027cf2a75774d1 \
  --build-manifest .build/listing-pair/build.json --rounds 5 --iterations 20 \
  --output .build/listing-pair/final.json
```

The recorded run used `taskset -c 6` (select an available core locally). No other heavy goose-fs job ran during timing. Shared-host overlap from other projects was not excluded. These warm-cache results do not measure remote/cold storage or concurrent throughput; a second complete pass can be especially costly on such filesystems. See the [API contract](../../../docs/API.md) and [four-library adaptive profile](../2026-11-04-adaptive-native-api/README.md).

## Validation

Independent security and quality/performance implementation reviews passed. Both GCC and Clang passed full public/JIT/optimized/debug/worker/native/OS/fault/fallback suites and ASan/UBSan; GCC and Clang native static analysis passed. Public boundary tests exercise all four listing APIs through legacy, full-options and adaptive signatures, invalid/byte/entry limits, exact 64 KiB..1 MiB thresholds, irregular budgets, full filename/order checks and empty-on-error outputs. Native tests cover permanent spill, required-size hints, metadata alias guards, stale Roots, descriptor balance and open/readdir/fdopendir/stream-close/parent-close failures. Existing race/ownership/resource tests remain enabled. No test suite proves absence of bugs.
