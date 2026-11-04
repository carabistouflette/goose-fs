# Benchmarks

`make bench BENCH_ITERATIONS=100` builds the public Goose interface with `-O2`
and records seven samples for each of fifteen workloads in `.build/bench.json`:
empty/64-byte reads with both exact and maximum budgets; 64-KiB/1-MiB reads;
over-limit, missing and 12-component-deep reads; one/1000-entry listings
with right-sized and maximum-capacity buffers; file and directory creation/removal.

Read/list samples are mean nanoseconds per call including loop/status/checksum
overhead. Mutation samples are nanoseconds per **create/remove pair**, containing
two public calls. Timers stop before output formatting. Output buffers are warmed
and reused; results are consumed in checksums. Listings still stage scratch each
call. Maximum-buffer reads initialize growth up to 1 MiB per call. Existing
listing calls and ListOptions.adaptive=false initialize the full budget and
enumerate once. Explicit adaptive=true starts with min(budget, 64 KiB); stable
larger results take a sizing pass and a complete retry. Right-sized short
listing workloads use 12/12000 bytes.
No uninitialized storage is exposed to Goose.

Metadata records CPU/OS, temporary filesystem type, compiler, flags, compiler pin,
source commit, dirty status, load-average snapshots, CPU affinity and executable
SHA256. Runs do not isolate CPU frequency or other workloads on the host. Fixtures are private temporary
directories deleted afterward. These are warm-cache measurements, not storage
bandwidth, cold I/O, concurrent throughput, allocation-free guarantees, or universal
cross-library rankings. CI has no timing thresholds.

For comparisons preserve the baseline executable before editing production code,
then build the candidate with the same compiler and flags. To rebuild an old
library using the current harness (only from trusted commits), run:

```sh
python3 bench/build-baseline.py --revision FULL_COMMIT --goose /path/to/goose \
  --cc gcc --output .build/baseline-gcc
make bench GOOSE=/path/to/goose BENCH_CC=gcc
```

Then compare:

```sh
python3 bench/measure.py --goose /path/to/goose --cc gcc --iterations 1000 \
  --baseline .build/baseline-gcc --baseline-revision FULL_COMMIT \
  --rounds 3 --output .build/compare-gcc.json
```

Each round runs both executables against identical fixtures, reversing their
batch order on alternating rounds. All raw samples are kept, and workload/sample
checksums must match across binaries/rounds. Report every workload and regressions;
Constant invalid-input rejection is not timed: the optimizer can eliminate that
loop entirely. Correctness tests still cover invalid inputs. Profile before changing validation, traversal or ownership. The default per-batch
timeout is one hour; `--timeout SECONDS` changes it.


The paired listing harness covers all four absolute/Root, unsorted/sorted APIs,
exact/maximum budgets, short names and payloads around 64 KiB through 1 MiB.
Baseline, current full staging and current adaptive staging use the same
sampling harness; the builder renders their respective public API calls. Build from a trusted baseline commit:

```sh
python3 bench/listing-build.py --goose /path/to/goose --cc gcc \
  --baseline-revision FULL_COMMIT
python3 bench/listing-measure.py --goose /path/to/goose --cc gcc \
  --baseline .build/listing-pair/baseline --full .build/listing-pair/full \
  --adaptive .build/listing-pair/adaptive \
  --baseline-revision FULL_COMMIT --build-manifest .build/listing-pair/build.json \
  --rounds 5 --iterations 5 --output .build/listing-pair/raw.json
```

The builder records native/source/template/rendered-harness/compiler and executable hashes. The
runner verifies that manifest before measurement and inputs again afterward.
Complete filename/order checks precede timing; timed calls consume entry counts,
name lengths and endpoints. Seven samples per process include all public calls,
initialization, enumeration, retries, owned-name construction and checksum work.
Each round shuffles variant/workload process order with a recorded fixed seed.
Context/Root setup, warmup and formatting are outside timing. No per-operation
allocation or memory claim is made. Keep every raw sample and regression.
