# Bounded-read A/A scheduling: repeatability remains inconclusive

Only **2 of 9** long-batch language/case controls met the preregistered max/min ≤1.05 limit in both attempts. Longer batches did not establish adequate repeatability at this checkpoint. This same-code diagnostic establishes no speedup, causal explanation or SOTA claim. Released runtime bytes remain unchanged.

## Source and validation

- [Finite schedule and limits](../../read-aa/README.md), preregistered in `f3f43b9` before implementation and timing.
- Measured clean source: `5ec174fd07af943ad883dde90a82cf4dd4b4edc6`. [Exact-source CI](https://github.com/carabistouflette/goose-fs/actions/runs/42015240150) passed GCC13/Clang18 release/sanitizer suites and read-contract/growth/A/A checks.
- Runtime: `c4411fdf5d1e73e4d74bda74d843627fb4365caa`, with library bytes identical to `ce3bdcf92c07c03761e73333526933d2db8b33b1`. No runtime, native source, compiler pin or consumer API change.
- Two fresh matched-path replicas each for FS, Rust1.99.1 + Linux/stat ABI bridge, and Go1.27.3-X:nodwarf5 + Linux adapter. Whole ELF and text/rodata hashes match within each pair. Executables are staged at one canonical path and verified outside timers.
- Local GCC16/Clang23 builds each passed 276 release and 129 fault/boundary checks. Both supervised count-one smoke checks passed (36 processes /252 means each; ineligible measurements). All 13 A/A tests passed, including timeout pipe tails, child/grandchild cleanup, late signals, external completion, journal corruption and overwrite refusal. Seven read-contract and five growth tests also passed before freezing.
- Each attempt passed **288 release +132 fault/boundary checks before and after** recording, including fresh-output probes. Both worker and supervisor journals completed; external tool exits were directly observed as **0**. All 216 streams match all 1512 means, commands, schedules, checksums and executable hashes.
- Two independent reviewers approved the source before timing, then independently recomputed all 72 medians, 36 controls, 324 resource-summary medians and the 2/9 decision. They checked journals, commands, counters, source/tool/stdlib hashes and actual release/fault ELF/section bytes.

## Complete controls

Each label/cell/batch/attempt median uses seven means from each of three processes: **21 means, three process replicas**. Controls are symmetric max(replica median)/min(replica median); no preferred replica is selected. Display rounding does not decide qualification. Reused short/long means average 2000/10000 calls; fresh-output means average 100/500 calls. Fresh logical output is allocated per call while the 1MiB file is reused. Lifetime/GC costs occur as incurred; deferred collection is not charged per call.

| Attempt | Case | Batch | FS | Rust | Go |
|---|---|---|---:|---:|---:|
| 1 | tiny | short | 1.0438 | 1.1583 | 1.0163 |
| 1 | tiny | long | 1.0539 | 1.0306 | 1.0945 |
| 1 | large-budget | short | 1.0175 | 1.0864 | 1.0377 |
| 1 | large-budget | long | 1.0113 | 1.2734 | 1.0089 |
| 1 | fresh-max | short | 1.0681 | 1.1035 | 1.0271 |
| 1 | fresh-max | long | 1.3812 | 1.3003 | 1.0203 |
| 2 | tiny | short | 1.0620 | 1.1016 | 1.0267 |
| 2 | tiny | long | 1.0859 | 1.0628 | 1.0511 |
| 2 | large-budget | short | 1.1555 | 1.2104 | 1.2344 |
| 2 | large-budget | long | 1.0366 | 1.3206 | 1.2317 |
| 2 | fresh-max | short | 1.4388 | 1.0186 | 1.0275 |
| 2 | fresh-max | long | 1.1670 | 1.0229 | 1.0189 |


The qualifying long-batch cells are **FS /large-budget** and **Go /fresh-max**. The other seven fail in at least one attempt. No complete three-language case qualifies. Short controls remain descriptive and are not pooled with long controls. This neither proves longer batches help or hurt nor gives a noise bound, confidence interval, future-run guarantee or permission to reinterpret rejected candidates.

[Full-precision medians, controls and resource summaries](analysis.json). [Interactive controls and replica medians](comparison.html).

## Whole-process observations and limits

The worker directly spawning/reaping each serial runner snapshots Linux RUSAGE_CHILDREN before spawn and after both pipes are drained and the child is reaped. Snapshots/deltas cover taskset/exec, startup, warmup, all seven loops, printing and shutdown; **they are not loop-only counters**. Parent wall duration also includes launcher/pipe overhead. Child CPU time can include multiple threads. Context switches can reflect runtime behavior as well as scheduling. Filesystem I/O fields count operations, not bytes. The high-water ru_maxrss field is not differenced.

Below are medians over six whole processes per language/case/long batch (two labels ×three rounds):

| Attempt | Long case | Language | Parent wall ms | Voluntary switches | Involuntary switches |
|---|---|---|---:|---:|---:|
| 1 | tiny | fs | 268.0 | 1 | 14 |
| 1 | tiny | rust | 279.6 | 1 | 13.5 |
| 1 | tiny | go | 330.9 | 1336.5 | 1340 |
| 1 | large-budget | fs | 3025.4 | 1 | 38 |
| 1 | large-budget | rust | 2579.7 | 1 | 34.5 |
| 1 | large-budget | go | 2632.9 | 1145.5 | 1178.5 |
| 1 | fresh-max | fs | 474.2 | 1 | 14 |
| 1 | fresh-max | rust | 397.7 | 1 | 14 |
| 1 | fresh-max | go | 977.3 | 4670.5 | 4801 |
| 2 | tiny | fs | 328.7 | 1 | 13.5 |
| 2 | tiny | rust | 309.9 | 1 | 13 |
| 2 | tiny | go | 397.4 | 1470.5 | 1470.5 |
| 2 | large-budget | fs | 3012.9 | 1 | 28.5 |
| 2 | large-budget | rust | 3692.7 | 1 | 27 |
| 2 | large-budget | go | 3671.9 | 1658 | 1676 |
| 2 | fresh-max | fs | 421.6 | 1 | 14.5 |
| 2 | fresh-max | rust | 617.7 | 1 | 14 |
| 2 | fresh-max | go | 963.7 | 4762.5 | 4909 |


All raw CPU seconds, context switches, minor/major faults, filesystem I/O operations and parent wall durations are retained. These counts, or wall-minus-CPU subtraction, do not establish scheduling delay or explain timing variation. No normalization, interruption filtering, startup subtraction or old-data modification was performed. Frequency/cache/thermal effects remain unmeasured.

All owned heavy builds and smoke checks finished before recording. Parent and measured runners were pinned to CPU6. Other work could continue on the shared host; no exclusive core, cache or frequency isolation is asserted. The ongoing CPU4 courtesy was honored. No host settings changed.

## Completion and reproduction

The first two attempts were launched separately. A supervisor held its worker leader unreaped until private process-group cleanup, then recorded status/streams. Its journal is separate from the worker journal and externally observed tool status. Unlike the previous growth experiment's wrapper anomaly, both external statuses here were directly observed as 0. No failed or unfavorable attempt was replaced.

- Attempt 1: `2026-11-05T12:26:14.537798+00:00`–`2026-11-05T12:27:44.581462+00:00`; [summary](aa-attempt-1.json), [lossless worker journal](aa-attempt-1.jsonl), [supervisor journal](aa-attempt-launch-1.jsonl).
- Attempt 2: `2026-11-05T12:27:58.050872+00:00`–`2026-11-05T12:29:48.935229+00:00`; [summary](aa-attempt-2.json), [lossless worker journal](aa-attempt-2.jsonl), [supervisor journal](aa-attempt-launch-2.jsonl).


[External statuses](outer-statuses.json). Embedded manifests bind clean source, compiler/stdlib inputs, tool hashes, libc/CPU/runtime settings, actual commands and replica ELF/section hashes. They do not hermetically capture every linker/sysroot file. No executables, caches, credentials or private planning are published.

Check out the full measured source SHA above, then follow the [build/smoke/two-attempt commands](../../read-aa/README.md) in a fresh private build directory with no concurrent writers. A new recording does not replace these records. Offline replay:

```sh
python3 bench/read-aa/analyze.py \
  bench/results/2026-11-05-read-aa/aa-attempt-1.json \
  bench/results/2026-11-05-read-aa/aa-attempt-2.json \
  --outer-statuses bench/results/2026-11-05-read-aa/outer-statuses.json
(cd bench/results/2026-11-05-read-aa && sha256sum -c SHA256SUMS)
```

An anonymous HTTPS clone checked out at measured `5ec174f` passed `make check`
using the pinned Goose compiler, a fresh six-replica build (276 release +129
fault checks; byte-identical pairs), all 13 A/A tests and the supervised
252-mean smoke plus duplicate/resource/-O guards. No measured timings were
repeated in that checkout.

[SHA-256 manifest](SHA256SUMS) covers numeric/process records and the chart; the README is excluded to avoid a self-referential hash.
