# Bounded read growth experiment (Linux x86-64)

Baseline: `ce3bdcf92c07c03761e73333526933d2db8b33b1`. One candidate only:
absolute `fs::read` initializes growth with fills of at most 1024 bytes rather
than one full resize fill. Invalid inputs, shrinking, full tail initialization,
read bounds, no-follow resolution and consumed-close/error policy are unchanged.
Root/held-file reads are unchanged. No native ABI addition, CPU dispatch, fill-size
sweep, cached-tail trust or uninitialized storage is introduced.

The 1024-byte bound was selected once after inspecting this host's libc large-fill
REP STOSB path. It is a platform-sensitive candidate, not a general rule about
memset. Its extra loop/header overhead may lose on other CPUs/libcs/compilers.
Local Callgrind and user-cycle samples motivate measurement, not acceptance.
Fresh allocation and all initialization remain charged to fresh-read timings.

## Rules fixed before controlled timing

Use the shared [read contract](../read-contract/README.md), independent Rust and
Go Linux adapters, full byte/errno/fault/descriptor qualification, and matched
fresh builds. Build order is base1/fs1/rust1/go1/base2/fs2/rust2/go2 at one reset
source/output/cache path. Require identical whole ELF and text/rodata within
all four same-source pairs. Execute all variants at one canonical path, atomically
staging and hashing the selected frozen executable outside timers. Retain actual
command paths and source executable hashes per process. Record actual library bytes per revision, adapters,
compiler/libc/CPU identities, commands and executable hashes. Test dirty retained
capacity, 1023/1024/1025 growth gaps, equal-length and shrinking outputs before
and after measurements. No interposition/profiling is used in throughput runs.

Record exactly the first two attempts of one clean frozen checkpoint, sequential
processes on CPU6, five shuffled rounds per attempt, seven means per process.
Each reused-output mean contains 2000 reads; the fresh 1MiB exact-budget cell
contains 100 reads per mean. Include all eleven existing reused-output cells and
that fresh cell, eight labels: 3360 means per complete attempt, 6720 total.
Each raw process stream must be retained losslessly before parsing; keep failed
and partial attempts, never replace a failed control or choose favorable replicas.
Any harness fix requires a new preregistered checkpoint with earlier data retained.

Acceptance requires BOTH records:

- In EVERY cell, max/min replica median <=1.05 for EACH of baseline FS, candidate
  FS, Rust and Go. Failed controls make the checkpoint inconclusive.
- In the target 64-byte-file/1MiB-budget cell, EVERY baseline median / EVERY
  candidate median >=1.10 (all four comparisons).
- In EVERY other cell, no candidate median / baseline median >1.05 in any
  replica comparison. A flag prevents adoption without claiming a causal regression.
- All correctness/resource/fault gates pass before and after; the candidate stays
  within its reviewed scope and KISS design.

Otherwise retain the released runtime. Reference/FS ratios against Rust/Go remain
fully reported; SOTA, suite leadership, portability and broad security equivalence
are not inferred. No pooling, correction or noise normalization. These operational
thresholds are not confidence intervals or a host-noise bound. Shared-host overlap
is disclosed; no exclusive-core, frequency or cache-isolation claim.

A source-dirty diagnostic pilot used the same public entry point and existing
contract runner before this controlled profile. It is ineligible for acceptance:
Callgrind models instructions, user-cycle sampling excludes kernel/blocked time,
and profiled/nonmatched timings cannot establish an improvement. Raw diagnostics
and failed profiler invocations will be retained separately from throughput data.

## Reproduction

Requires the full baseline Git object (use a full clone), the pinned Goose compiler,
Linux x86-64, Python without optimization, GCC/binutils, Rust1.99.1 and Go1.27.3.
No toolchain/dependency download is performed by these experiment scripts.

```sh
python3 tests/read_contract.py
python3 tests/read_growth.py
taskset -c 6 python3 bench/read-contract/build.py --goose /absolute/path/to/goose --baseline-revision ce3bdcf92c07c03761e73333526933d2db8b33b1 --output-dir .build/read-growth-matched
python3 tests/read_growth.py --build-dir .build/read-growth-matched
# After review and a clean frozen checkpoint, first two attempts only:
taskset -c 6 python3 bench/read-contract/measure.py --matched-growth --build-dir .build/read-growth-matched --attempt 1
taskset -c 6 python3 bench/read-contract/measure.py --matched-growth --build-dir .build/read-growth-matched --attempt 2
python3 bench/read-growth/analyze.py .build/read-growth-matched/attempt-1.json .build/read-growth-matched/attempt-2.json
```
