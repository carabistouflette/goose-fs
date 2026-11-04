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
call. Maximum-buffer workloads include 1 MiB of initialization per call; right-sized
listing workloads use 12/12000 bytes. No uninitialized storage is exposed to Goose.

Metadata records CPU/OS, temporary filesystem type, compiler, flags, compiler pin,
source commit, dirty status and executable SHA256. Fixtures are private temporary
directories deleted afterward. These are warm-cache measurements, not storage
bandwidth, cold I/O, concurrent throughput, allocation-free guarantees, or universal
cross-library rankings. CI has no timing thresholds.

For comparisons preserve the baseline executable before editing production code,
then build the candidate with the same compiler and flags. Run:

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
