# Benchmarks

`make bench BENCH_ITERATIONS=100` builds the public Goose interface with `-O2`
and records seven samples per workload in `.build/bench.json`: empty, 64-byte,
64-KiB and 1-MiB reads; an over-limit read; a 12-component-deep read; one-entry
and 1000-entry listings with both right-sized and maximum-capacity buffers. The harness warms reusable output buffers first and
consumes results in checksums. Each raw sample is mean nanoseconds per call
including loop/status/checksum overhead. Metadata includes CPU/OS, temporary filesystem type, compiler,
flags, compiler pin, source commit and dirty status. Fixtures live in private
temporary directories and are deleted afterward.

These are warm filesystem/cache measurements, not storage bandwidth, cold I/O,
concurrent throughput, cross-library rankings, or allocation-free guarantees.
The maximum-buffer listing workloads include 1 MiB of scratch initialization
per call; right-sized workloads use 12 and 12000 bytes. The runner has a one-hour
benchmark timeout; invoke bench/measure.py --timeout SECONDS to change it. No timing threshold runs in CI. Profile before changing
validation, path traversal or ownership, and compare interleaved runs on the same
machine with all raw workloads retained.
