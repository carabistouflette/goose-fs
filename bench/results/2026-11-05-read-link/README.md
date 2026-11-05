# Bounded symlink inspection: Linux API and task costs

Recorded experiment, with the source and toolchain identities stated below.
These tables are not automatically measurements of current main. See
[the currentness inventory](../../../docs/PERFORMANCE.md) before applying them.
To rebuild an experiment, use its measured source revision in a separate checkout.
For the retained raw artifacts and original replay scripts, use publication
`60cec1e1956962772fff6091b4c7ff1876533f9e`. Historical raw artifacts are unchanged.

`read_link(path, limit, out)` and `read_link_at(root, path, limit, out)` now inspect
complete symlink target bytes with bounded adaptive staging, strict no-follow
ancestors and clear-on-error output. Targets are never followed or normalized.
See the [complete contract](../../../docs/READ-LINK.md).

## Source and validation

- Implementation: `170b394d2f4f31682459b64507a90789c2103703`; [exact CI](https://github.com/carabistouflette/goose-fs/actions/runs/42083074955) passed all jobs.
- Measured clean source and frozen recorder: `4a7b2c178695fb453b4303184303212ee3d85834`; [exact CI](https://github.com/carabistouflette/goose-fs/actions/runs/42084508996) passed GCC13/Clang18 release/sanitizer and recorder/comparator smoke checks.
- Two independent reviewers approved implementation and benchmark code after fixes to fault portability, clear-on-error assertions and recorder retention. Final artifact review is recorded before publication.
- Local full `make check test`, GCC16 and Clang23 ASan/UBSan passed. Public JIT/release/debug tests cover 0/exact/overflow budgets, 255/256/257 and 511/512/513 transitions, binary names/targets, caller-output/path aliasing, dangling/cyclic/outside targets, strict ancestors and held/stale/kind-checked Roots. Held child Roots survive parent-entry rename.
- Native faults check EINTR, full-buffer ambiguity, close-once FD reuse, syscall/limit/cleanup precedence, invalid ABI overlap and guard-page/MAX_BYTES+1 boundaries through absolute and Root APIs. Public fault injection covers all 14 sizing passes, complete replacement targets and clearing after later failure.
- 500 seeded byte/limit cases and 1000 concurrent atomic-replacement observations passed with descriptor balance; this host excluded no long-target fixtures. On filesystems rejecting 4095-byte symlinks, the public fixture/model explicitly reports target-length exclusions; synthetic maximum bounds stay mandatory. Real replacement-race tests require support for 513-byte targets.
- An anonymous HTTPS checkout at measured `4a7b2c1` passed `make check readlink CC=clang` with the pinned Goose compiler, all 500 seeded cases and 1000 replacement observations. No measured recording was repeated there.
- All 15 capture/decision tests passed, including drained timeout tails and a real binary-prefix interruption. Recorder regressions cover completion, duplicate preservation, dangling reservation paths, failed timeout evidence and Python -O rejection.

## Finite recording and policy differences

The [preregistered schedule](../../compare/README.md#bounded-symlink-inspection-checkpoint)
used three separate first recordings, seeds 65811/65812/65813, three shuffled rounds,
seven means per workload/runner and 100 calls per mean. All external exits were
observed as 0. The complete four-runner suite is retained: **10080 rows**, of which
7686 are timed and 2394 explicitly unsupported. The new six readlink workloads
contain **1512 rows: 945 timed, 567 unsupported**. All 48 process streams are kept:
12 count-one preflight processes and 36 measured processes. Warmup/preflight
streams are ineligible measurements.

Each table median uses 21 means from three processes in that recording, not 21
independent process replicas. All three records remain separate; no favorable
pass selection, normalization, replacement run or new threshold variant occurred.
These are descriptive native-API task costs, **not matched-policy security,
allocation, causal-speedup or SOTA evidence**. Earlier failed A/A controls remain
failed and are not requalified by this profile.

| Caller | Timed symlink policy |
|---|---|
| goose-fs | Strict no-follow ancestors; caller budget 1MiB; fresh adaptive staging per call, reusable owned output; checked owned-parent close; bounded sizing passes, with no deadline on EINTR retries |
| Rust std::fs | Native read_link returns a fresh PathBuf; ordinary ancestor traversal; consumer bound checked after native allocation; no stdlib Root interface substituted |
| Go os /os.Root | Native Readlink returns a fresh string; ordinary absolute traversal or permitted in-tree Root links; consumer bound checked after native allocation |
| Pinned Goose stdlib | No readlink operation; unsupported retained explicitly |

FS starts with at most 256 initialized staging bytes, avoiding full-budget
initialization for short targets. Exact fills and longer targets require repeated
lookup/read/close passes; success copies staged bytes into owned output. This
tradeoff is disclosed, not proved optimal. Root open/close is outside timing.
Stable targets contain only `x`; full bytes are checked before/after timing,
status/length/endpoint checksums inside. Allocation/lifetime/GC costs occur as
incurred, with no deferred-GC charge per call. VmHWM covers the **whole suite
process**, including unrelated workloads and validation; it is not per-call memory.

## Every symlink median

Nanoseconds per call, no display-derived acceptance decision. `—` means unsupported.

| Workload | Recording | goose-fs | Rust | Go | Goose stdlib |
|---|---:|---:|---:|---:|---:|
| readlink-64 | 1 | 1883 | 791 | 949 | — |
| readlink-64 | 2 | 2024 | 764 | 1022 | — |
| readlink-64 | 3 | 1974 | 870 | 970 | — |
| readlink-256 | 1 | 4452 | 1950 | 4738 | — |
| readlink-256 | 2 | 4545 | 1942 | 4611 | — |
| readlink-256 | 3 | 4351 | 2190 | 3861 | — |
| readlink-4095 | 1 | 24783 | 17321 | 31045 | — |
| readlink-4095 | 2 | 23476 | 16975 | 34782 | — |
| readlink-4095 | 3 | 23005 | 20509 | 28485 | — |
| root-readlink-64 | 1 | 1218 | — | 1010 | — |
| root-readlink-64 | 2 | 1238 | — | 978 | — |
| root-readlink-64 | 3 | 1203 | — | 1014 | — |
| root-readlink-256 | 1 | 2906 | — | 4318 | — |
| root-readlink-256 | 2 | 2902 | — | 5711 | — |
| root-readlink-256 | 3 | 2839 | — | 4058 | — |
| root-readlink-4095 | 1 | 20508 | — | 31332 | — |
| root-readlink-4095 | 2 | 19341 | — | 31557 | — |
| root-readlink-4095 | 3 | 19705 | — | 27328 | — |

Rust's absolute native-call medians are lower than FS in all three recorded target
sizes. Go's 64-byte medians are lower than FS for absolute and Root cases; its
4095-byte medians are higher. The absolute 256-byte ordering changes across
recordings. Different lookup/allocation policies and shared-host variability
prevent a universal leadership or causal explanation. Small differences are not
acceptance evidence. All slower cases remain visible.

[Interactive per-record costs](comparison.html), [full-precision derived medians](analysis.json).

## Provenance, completion and replay

Parent and measured children inherited CPU6 affinity. All owned heavy local
builds/tests finished first; other host work could continue. No exclusive core,
cache, frequency, thermal or filesystem isolation is claimed. Fixtures are warm,
trusted and stable; no cold-storage, hostile-tree timing or durability conclusion.
The full mixed suite's process order was shuffled, and allocator state can carry
between workloads. No host settings were changed and no timing process remains.

Raw JSON and JSONL bind clean source, runtime/native hashes, compiler/stdlib/tool
identities, flags, actual commands, process ordering, fixtures, limits, runtime
settings and load averages. This is not a hermetic capture of every sysroot file.
No executable/cache, credential or private planning artifact is published. Numeric
records and process streams are copied unchanged. All successful streams are
flushed before parsing; failures reserve their names and retain partial evidence.
Default SIGTERM/hard-kill cleanup is not guaranteed by this recorder; incomplete,
nonzero or unknown external completion is ineligible. This checkpoint has none.

- Recording 1 started `2026-11-05T18:29:23.352689+00:00`; [JSON](pass-1.json), [lossless streams/journal](pass-1.jsonl), [outer log](pass-1.log).
- Recording 2 started `2026-11-05T18:30:13.418922+00:00`; [JSON](pass-2.json), [lossless streams/journal](pass-2.jsonl), [outer log](pass-2.log).
- Recording 3 started `2026-11-05T18:30:59.853350+00:00`; [JSON](pass-3.json), [lossless streams/journal](pass-3.jsonl), [outer log](pass-3.log).

[Observed external statuses](outer-statuses.json). Reproduce new measurements from
the full measured source SHA using `bench/compare/build.py`, then the schedule and
commands in its README with fresh output names. Do not replace these recordings.
Offline replay from a clone:

```sh
python3 bench/results/2026-11-05-read-link/replay.py
(cd bench/results/2026-11-05-read-link && sha256sum -c SHA256SUMS)
```

`replay.py` checks all streams against every parsed suite row, preserves unsupported
states, verifies completion/provenance/fixture gates and derives all 45 supported
readlink medians. [SHA-256 manifest](SHA256SUMS) covers evidence, replay code and chart;
the README is excluded to avoid a self-referential hash.
