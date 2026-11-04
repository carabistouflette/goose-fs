# Filesystem performance and security audit — 2026-11-04

Library baseline: `6b8c079ba0414115713b16ae216327197fceb27d`. Measured candidate: `3c863ca2171a347d878b4708f189597eb2244e2d` (clean tree). Later result-documentation commits do not change measured production code. Both use the identical current benchmark harness; its SHA256 and both executable SHA256 values are in the raw data.

Host: Intel(R) Core(TM) Ultra 7 258V; Linux-7.2.11-arch1-1-x86_64-with-glibc2.44; temporary filesystem `tmpfs`. Compiler source pin: `eadca409f68210893f366e60d0c2f0dc29a339be`. Native compiler versions:

- gcc: gcc (GCC) 16.2.1 20260810
- clang: clang version 23.1.4

All builds use `-O2`. Each compiler ran three alternating baseline/candidate rounds, seven samples per workload per variant per round, 2,000 iterations per sample: 630 raw samples per compiler. The table reports the median of 21 per-sample means in nanoseconds. Mutation rows measure a create/remove pair (two public calls). Results are warm-cache; the host is shared and CPU frequency is not isolated. Load averages and affinity are recorded. Small changes may be scheduling/cache/compiler-layout noise.

The candidate resolves parent paths with one `openat2` lookup under `RESOLVE_NO_SYMLINKS`, retaining the descriptor walker on ENOSYS/EPERM. Owned filename copying uses the array append builtin. Deep traversal and small operations benefit most; 1-MiB reads remain dominated by initialization/data movement and are slightly slower in the GCC run. No cross-language ranking, cold-storage, durability or universal throughput claim is made.

[Standalone chart](comparison.html) · [GCC raw samples](gcc.json) · [Clang raw samples](clang.json)

| Workload | GCC baseline ns | GCC candidate ns | GCC change | Clang baseline ns | Clang candidate ns | Clang change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| read-empty | 5,818 | 3,432 | -41.0% | 5,011 | 3,070 | -38.7% |
| read-empty-max-buffer | 47,989 | 46,618 | -2.9% | 47,306 | 44,307 | -6.3% |
| read-small | 4,926 | 3,293 | -33.2% | 4,833 | 3,306 | -31.6% |
| read-small-max-buffer | 46,078 | 44,504 | -3.4% | 45,942 | 44,527 | -3.1% |
| read-missing | 4,315 | 2,662 | -38.3% | 4,314 | 2,654 | -38.5% |
| read-64k | 12,192 | 10,428 | -14.5% | 12,065 | 10,373 | -14.0% |
| read-1m | 140,763 | 142,448 | +1.2% | 140,850 | 139,621 | -0.9% |
| read-overflow | 5,174 | 3,461 | -33.1% | 5,019 | 3,432 | -31.6% |
| read-deep | 16,441 | 3,922 | -76.1% | 16,055 | 3,860 | -76.0% |
| list-one | 5,958 | 4,220 | -29.2% | 5,861 | 4,171 | -28.8% |
| list-one-max-buffer | 47,338 | 45,404 | -4.1% | 48,071 | 45,799 | -4.7% |
| create-remove-file | 13,405 | 9,693 | -27.7% | 13,417 | 9,914 | -26.1% |
| create-remove-dir | 9,842 | 6,373 | -35.2% | 10,024 | 6,420 | -36.0% |
| list-1000 | 179,891 | 176,551 | -1.9% | 176,507 | 172,638 | -2.2% |
| list-1000-max-buffer | 224,693 | 219,301 | -2.4% | 231,177 | 215,537 | -6.8% |

## Reproduce

Run from a trusted clone; install the pinned compiler with `make setup`, then:

```sh
python3 bench/build-baseline.py --revision 6b8c079ba0414115713b16ae216327197fceb27d \
  --goose .toolchain/goose/build/goose --cc gcc --output .build/baseline-gcc
make bench BENCH_CC=gcc BENCH_ITERATIONS=2000
python3 bench/measure.py --goose .toolchain/goose/build/goose --cc gcc \
  --baseline .build/baseline-gcc \
  --baseline-revision 6b8c079ba0414115713b16ae216327197fceb27d \
  --iterations 2000 --rounds 3 --output .build/compare-gcc.json
```

Repeat with `clang` and a separate baseline/output filename. All workload/sample checksums must match between variants and rounds. See [measurement scope](../../README.md).

## Security and correctness validation

- Two independent reviewers rechecked implementation, optimized lookup, public packaging and measurement methods; all actionable findings were resolved.
- `make check test CC=gcc` and `CC=clang` pass in JIT, optimized native and debug execution, plus ownership/consumer-overload regressions.
- Per compiler: real openat2, forced ENOSYS and forced EPERM paths each pass 3,673 filesystem-oracle calls, an isolated controlling-TTY regression and 20,000 symlink-replacement race probes (120,000 total race probes across both compiler matrices).
- Exact 4,096-entry/1-MiB listings, real 4,095-byte paths, arbitrary filename bytes, closed standard descriptors, descriptor leaks, protected buffer boundaries and injected partial I/O/open/fstat/fdopendir/close failures are covered.
- GCC and Clang ASan/UBSan pass for the public Goose interface, native bounds/ABI/failure suites and forced descriptor fallback.
- A fresh standalone local Git clone successfully built the pinned compiler with `make setup`; standalone API checks/tests, the example and a benchmark smoke run also passed using that compiler.

These checks cannot prove absence of bugs. The [API contract](../../../docs/API.md) retains explicit limits: no confinement/snapshots/deadlines, device opens may have effects, and failed creation may leave a partial file. The only confirmed defect in this audit was benchmark timing (listing formatting was included); that is fixed. A constant invalid-input benchmark was removed because its loop was optimized away.
