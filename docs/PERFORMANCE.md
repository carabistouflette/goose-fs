# Performance results and scope

The library is not fastest in every operation. Costs depend on lookup policy,
allocation, sorting, synchronization, compiler and filesystem. Native Rust/Go
calls often do different work. Use the API contract as well as the timing table.

## Evidence that matches the current implementation

The [three native-API recordings](../bench/results/2026-11-05-read-link/README.md)
measured `4a7b2c178695fb453b4303184303212ee3d85834` and were published in
`60cec1e1956962772fff6091b4c7ff1876533f9e`. The complete production implementation,
benchmark drivers, compiler pin and recorded dependency sources match the runtime
in this documentation update. The only changed manifest input is benchmark prose,
which is not compiled. [The checked source bridge](announcement-audit.json) lists
each compared path/hash and recorded toolchain identity. It is not a new run.

Those records contain 40 workloads per runner, including whole-file and retained positioned
reads, listing, metadata, locks, rename and link inspection. Unsupported cells
remain unsupported. Only their explicitly described native-API policy is measured;
the data does not establish equal-security performance or a general ranking.
For example, FS rejects symlink ancestors and bounds storage, while ordinary
Rust/Go path calls can follow ancestors and allocate before checking a limit.
Full versus adaptive listing is a separate choice: this profile uses **full**
staging. It does not replace earlier adaptive experiments.

Recorded environment: Intel Core Ultra 7 258V, Linux 7.2.11 x86-64, glibc 2.44,
tmpfs; parent and children pinned to CPU6 on a shared machine. Goose
`eadca409f68210893f366e60d0c2f0dc29a339be` with its 15 recorded stdlib files,
GCC 16.2.1, Rust 1.99.1 and Go 1.27.3-X:nodwarf5. FS uses `-O2`; Rust uses
opt-level 2/codegen-units 1; Go uses `-trimpath` with recorded environment flags.
The Goose compiler executable hash is recorded and checked. GCC/Rust/Go versions
are recorded; every compiler executable and sysroot was not hashed. Different
builds/platforms need their own measurements before transferring these numbers.

Three fixed recordings each use three shuffled process rounds, seven means per
workload per process and 100 calls per mean. Each process first runs an untimed
warmup; four count-one preflight processes per recording are not timed samples.
Full byte/name checks run outside timers; status, length and endpoint checksums
are inside. The 10,080 result rows include 7,686 timed means and 2,394 unsupported
rows; raw journals include 12 preflight and 36 measured process streams. Each
within-record cell has 21 means from **three processes**, not 21 independent
process replicas. Whole-process VmHWM is not per-call memory or allocation count.

[Descriptive dispersion](performance-dispersion.json) gives min, Q1, median, Q3
and max for every timed cell, with each process/round kept separately. Quartiles
use the inclusive interpolation method. Samples are means, not individual-call
latencies; ranges/IQRs are not confidence intervals or proofs of isolation.
The file also covers the historical profiles below without changing their data.
Units follow each workload: ordinary calls are ns/call, mutation/lock/rename
pairs are ns/pair as defined in the corresponding report.

Rust's absolute link-inspection medians are lower than FS at all three recorded
sizes. Go's short-target medians are lower; FS's long-target medians are lower.
The absolute 256-byte ordering changes between recordings. Every pass and slower
case stays visible. These observations do not prove a causal speedup or validate
small differences on this shared host. Earlier failed repeatability controls
remain failed; this profile does not repair them.

## Reproduce or audit

Exact artifact replay belongs in a separate checkout of the publication commit:

```sh
git clone https://github.com/carabistouflette/goose-fs.git goose-fs-records
cd goose-fs-records
git checkout --detach 60cec1e1956962772fff6091b4c7ff1876533f9e
python3 bench/results/2026-11-05-read-link/replay.py
(cd bench/results/2026-11-05-read-link && sha256sum -c SHA256SUMS)
```

In the current documentation checkout, verify the source bridge and recompute
all dispersion **without running a benchmark**:

```sh
python3 scripts/audit-docs.py --output .build/docs-audit.json \
  --dispersion .build/dispersion.json
```

`--goose /absolute/path/to/goose` additionally checks that installed compiler and
local toolchain identities match the recorded environment. A different build of
the same compiler revision need not have the same executable hash. The checked
local audit used the original recorded compiler; this is not a promise that a
fresh `make setup` build is byte-identical to it.

[Benchmark commands](../bench/README.md) produce new measurements. Reproducing an
old candidate requires its recorded source checkout; dates alone are insufficient.
No new timing was needed for this documentation audit.

## Historical results

These remain observations of their recorded revisions, not current-main numerical
claims. The [inventory](announcement-audit.json) records the measured checkout, baseline/candidate/export revision references,
and whole-production-tree differences for each measured checkout. It does not
present those checkout differences as source bridges for every exported variant. Even unchanged operation bodies do not
transfer an old numerical gain across changed code layout, harness or host state.
Ten older profiles lack recorded stdlib source maps; the initial audit and read
reuse profiles also lack a compiler executable hash. Today's dependency hashes
cannot fill those historical gaps.

| Historical profile | Interpretation |
|---|---|
| [2026-11-04](../bench/results/2026-11-04/README.md) | Initial lookup/copy comparison; later read/list/shared code changed. |
| [2026-11-04-adaptive-native-api](../bench/results/2026-11-04-adaptive-native-api/README.md) | Earlier adaptive suite; distinct from the full-staging profile above. |
| [2026-11-04-listing-staging](../bench/results/2026-11-04-listing-staging/README.md) | Full/adaptive tradeoff before current sorting. |
| [2026-11-04-locks](../bench/results/2026-11-04-locks/README.md) | Older lock/registry costs, not current overhead. |
| [2026-11-04-native-api](../bench/results/2026-11-04-native-api/README.md) | Earlier native API suite, before retained resources and current sorting. |
| [2026-11-04-read-reuse](../bench/results/2026-11-04-read-reuse/README.md) | Read-prefix reuse; later whole-operation paths changed. |
| [2026-11-04-rename](../bench/results/2026-11-04-rename/README.md) | Rename bodies remain, but mixed suite and timings stay historical. |
| [2026-11-04-retained](../bench/results/2026-11-04-retained/README.md) | Older File registry/lifetime costs. |
| [2026-11-04-roots](../bench/results/2026-11-04-roots/README.md) | Older Root/listing/resolver costs. |
| [2026-11-05-file-metadata](../bench/results/2026-11-05-file-metadata/README.md) | Setter bodies remain; mixed suite and timing values stay historical. |
| [2026-11-05-listing-control](../bench/results/2026-11-05-listing-control/README.md) | Identical-code variation; not a present noise bound. |
| [2026-11-05-matched-listing](../bench/results/2026-11-05-matched-listing/README.md) | Matched-path observations with mixed controls; no causal ranking. |
| [2026-11-05-read-aa](../bench/results/2026-11-05-read-aa/README.md) | Repeatability diagnostic; only 2/9 long cells qualified then, no current noise bound. |
| [2026-11-05-read-contract](../bench/results/2026-11-05-read-contract/README.md) | Independent bounded adapters; repeatability remained inconclusive. |
| [2026-11-05-read-growth](../bench/results/2026-11-05-read-growth/README.md) | Rejected 1KiB candidate; not in current runtime. Instrumentation is not throughput. |
| [2026-11-05-sorted-listing](../bench/results/2026-11-05-sorted-listing/README.md) | Natural/shuffled and full/adaptive sorting comparisons; no transferred ranking. |
