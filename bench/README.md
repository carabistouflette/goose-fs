# Benchmarks

Start with [results and currentness](../docs/PERFORMANCE.md). It identifies the
recorded code and toolchains that still match the library. Older experiments are
kept as history, including rejected changes and slower cases.

## Record a new run

These commands create **new measurements**, not a reproduction of an old result.
Use the pinned Goose compiler from `make setup`. Keep the output, source revision,
compiler settings and machine details together. Use a new output path for each
run. On a shared machine, schedule a finite run before starting heavy work.

```sh
make bench BENCH_ITERATIONS=100
```

This runner writes `.build/bench.json`: seven mean-nanosecond samples for fifteen
read/list/create/remove workloads. Reads/listings include public-call, status and
checksum costs. Mutations are measured per create/remove pair. Output formatting
is outside timing; buffers and file cache are warm. It is not a storage-bandwidth
or concurrent-throughput result. CI uses small iteration counts to check behavior,
without timing thresholds. Move an earlier output aside before reusing this
legacy runner; it overwrites its default output.

For the four native APIs (FS, Goose stdlib, Rust and Go), install the versions in
the [comparison guide](compare/README.md), then use:

```sh
python3 bench/compare/build.py --goose .toolchain/goose/build/goose
python3 bench/compare/run.py --goose .toolchain/goose/build/goose \
  --iterations 100 --rounds 3 --seed 65811 --output .build/new-native-api.json
```

The native-API recorder refuses existing outputs, keeps process streams and
records unsupported operations. Lookup, allocation, error and synchronization
policies differ between libraries; it is not a security-equivalent ranking.
All samples, slower workloads and failed runs belong in the report.

## Historical experiments

Each result report identifies the revision and commands needed to reproduce it.
Use a separate checkout of that revision. Building today's code with an old
protocol does not reproduce its original candidate or binary.

| Experiment | Protocol |
|---|---|
| Preserved-baseline comparison | `build-baseline.py`, `measure.py`; command-line `--help` describes required revision/paths |
| Full/adaptive directory staging | `listing-build.py`, `listing-measure.py` |
| Identical-code listing controls | [listing-control.md](listing-control.md) |
| Bounded reads with independent Linux adapters | [read-contract](read-contract/README.md) |
| Rejected read-growth candidate | [read-growth](read-growth/README.md) |
| Read scheduling controls | [read-aa](read-aa/README.md) |

[The currentness inventory](../docs/PERFORMANCE.md#historical-results) covers every
published result directory. Their raw files remain unchanged. Instrumented
profiles, compiler smoke checks and incomplete controls are not throughput wins.
