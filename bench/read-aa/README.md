# Finite read A/A scheduling diagnostic — Linux x86-64

This is a new diagnostic checkpoint, not a replacement for earlier recordings.
The released runtime (`c4411fdf5d1e73e4d74bda74d843627fb4365caa`, with library
bytes identical to ce3bdcf) stays unchanged. No optimization candidate, timing
correction, favorable-run selection or SOTA claim is permitted by this checkpoint.

## Preregistered schedule and rules

Use the existing independent read-contract builder: two fresh matched-path builds
per language (FS, Rust + Linux/stat ABI bridge, Go + Linux), requiring whole ELF
and text/rodata equality in each pair. Bind clean source, compiler/libc/CPU,
standard-library hashes, settings, every executable and actual command. Use one
canonical executable path with atomic staging/hash checks outside timers.
Run the complete byte/errno/fault/FD qualification before and after each attempt.

Exactly the first TWO attempts, THREE shuffled rounds each, seven in-process
means per invocation. All six replicas run every cell and batch in every round:

| Cell | Short calls/mean | Long calls/mean |
|---|---:|---:|
| reused 64-byte file, exact 64-byte budget (`tiny`) | 2000 | 10000 |
| reused 64-byte file, 1MiB budget (`large-budget`) | 2000 | 10000 |
| fresh output for a reused 1MiB file, exact budget (`fresh-max`) | 100 | 500 |

Thus 108 process invocations / 756 means per complete attempt, 216 / 1512 total.
Fixed process seeds are 62602+attempt; fixture creation uses the existing 62501
seed. Count arguments have five decimal digits in both batches, avoiding an
argument-length difference. Both launcher and children run on CPU6; no other
heavy local work owned by this thread runs during recording. Other shared-host
work may continue, without an exclusive-core/frequency/cache-isolation claim.

Keep every process stream losslessly and flush it before parsing. Failed, partial
and timed-out attempts remain reserved; no replacement attempt at this checkpoint.
Launch the two recorders separately. A supervisor reserves an exclusive launcher
journal and records the worker exit status and lossless streams separately from
the worker completion marker. It signals only its own dedicated worker group
after waitid(WNOWAIT) leaves the leader unreaped, including a worker crash.
A process-local alarm bounds the blocking wait without polling; original signal
handlers are restored. External hard kills can
prevent cleanup/completion and never qualify. Retain the tool wrapper exit status
as well as both journals. A launcher anomaly is reported, never
silently treated as complete. A harness fix requires a new preregistered source
checkpoint, preserving earlier records.

For each language/cell/batch/attempt, the control is max(replica median ns)/
min(replica median ns), with medians over 21 means from three processes (not 21 independent process replicas). A LONG language/cell is
qualified only if its control <=1.05 in BOTH complete attempts and all qualification
and launcher-completion gates pass. Only if all nine LONG language/cells qualify
may we say 'long-batch controls qualified at this checkpoint'. Otherwise the
broader repeatability question stays inconclusive. SHORT controls are reported
alongside LONG controls, not pooled. Even a pass is not a noise bound, confidence
interval, future-run guarantee, proof of isolation or permission to reinterpret
old rejected candidates. There is no runtime acceptance decision here.

## Process resource observations

The serial launcher snapshots Linux RUSAGE_CHILDREN immediately before spawning
its one child and after the one-child capture helper has drained its pipes and reaped it. No other child runs or is
reaped between those snapshots. Record both snapshots and additive deltas for
user/system CPU seconds, voluntary/involuntary context switches, minor/major
faults and filesystem input/output operations. Never difference ru_maxrss: it is
a high-water field, not additive. Record monotonic parent wall duration too.
Timeouts retain partial streams and resource observations after kill/reap.

These observations cover taskset/exec, startup, warmup, all seven timed loops,
printing and shutdown. They do not include the outer supervisor’s worker wait. They are not loop-only measurements. Wall duration also
includes launcher/pipe overhead; child CPU time may cover multiple threads.
Do not subtract CPU time from wall time as a pure scheduling-delay estimate,
subtract startup, normalize timings, drop interrupted processes or infer causality
from a correlation. Context counts can also reflect runtime/GC behavior. Fresh
allocation/init and normal lifetime/GC costs occur as incurred; deferred collection
is not charged to each call. Frequency/cache/thermal effects remain unmeasured.

Sources: [Python resource](https://docs.python.org/3/library/resource.html),
[Linux getrusage](https://man7.org/linux/man-pages/man2/getrusage.2.html),
[Linux waitid](https://man7.org/linux/man-pages/man2/waitpid.2.html).

## Reproduction

Use the recorded clean checkpoint with the pinned Goose compiler, Rust1.99.1,
Go1.27.3, GCC/binutils, taskset and ordinary Python (not -O). Scripts download no
dependencies. Build/run only in caller-controlled private .build directories with
no concurrent writers. Full baseline read-contract qualification is retained.

```sh
python3 tests/read_aa.py
taskset -c 2 python3 bench/read-contract/build.py --goose /absolute/path/to/goose --output-dir .build/read-aa
python3 tests/read_aa.py --build-dir .build/read-aa
# After review and freeze; separate launches, first two attempts only:
taskset -c 6 python3 bench/read-aa/record.py --build-dir .build/read-aa --attempt 1
taskset -c 6 python3 bench/read-aa/record.py --build-dir .build/read-aa --attempt 2
python3 bench/read-aa/analyze.py .build/read-aa/aa-attempt-1.json .build/read-aa/aa-attempt-2.json --outer-statuses .build/read-aa/outer-statuses.json
```

`outer-statuses.json` records externally observed tool exit codes as
`{"tool_exit_codes":{"1":0,"2":0}}`. Supply observed values, never inferred
zeros: a missing, unknown or nonzero status cannot qualify. Supervisor and worker
journals are both retained alongside this file.
