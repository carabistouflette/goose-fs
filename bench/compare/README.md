# Native API comparison

This harness compares goose-fs with stable Rust std::fs (1.99.1), Go os (the
installed toolchain, recorded), and the pinned Goose standard library.
It is a **task-cost comparison with different safety contracts**, not an
equal-security ranking. See docs/comparison-research.md for the hardened-adapter
profile still required before equal-security performance conclusions.

```sh
python3 bench/compare/build.py --goose /absolute/path/to/goose --cc gcc
python3 bench/compare/run.py --goose /absolute/path/to/goose --cc gcc \
  --iterations 100 --rounds 3 --output .build/compare/native-api.json
```

All binaries use the same private fixtures, with full byte-pattern and sorted-name
validation outside timers. Seven samples per workload per process use fresh or
reused read outputs; sizes 0/64/4096/65536/1048576 bytes. Listings have
0/1/128/4096 ASCII names. General metadata is explicitly unsupported for Goose
stdlib; is-directory is a separate workload. Each batch retains its language's
normal allocator/GC behavior. Whole batches are shuffled with a recorded seed.

Results record native-API policies, source/executable/fixture hashes, versions,
flags, affinity, filesystem, shared-host load, all raw samples, and per-process
VmHWM sampled after the workload suite. Reads consume length and endpoint bytes;
listing checksums include every name's length and endpoint bytes. Rust black_box
and retained Go sinks prevent owned-result dead-store elimination; Goose's
separately compiled native sidecar remains opaque to the program optimizer.
The builder saves source/toolchain/flag/binary provenance only after all builds
succeed; the runner rejects changed inputs or a mismatched compiler selection.
Go build settings and selected inherited runtime/allocator settings are retained.
Full-content preflight checks are separate from timed endpoint/length checks;
fresh timed results do not receive a full-content postcheck.

Fresh Rust/Go convenience calls return newly owned data; reused variants use
File.read_to_end/File.Read and retain storage. Goose stdlib appends into a cleared
caller builder; goose-fs replaces caller data and enforces regular-file, path,
symlink and byte bounds that ordinary comparator APIs do not. Goose stdlib uses
newline framing and omits newline filenames; these common fixtures contain none.
Sorted outputs differ in representation and kind-hint work. They are not identical
ownership/error/lookup interfaces. Unsupported cells never receive a timing score.
goose-fs listings use a 1 MiB byte budget and 4096-entry limit for every size,
including empty directories; oversized staging initialization is a caller cost.
Metadata callers test regular kind and size. Rust/Go also retain full metadata
objects, while Goose may elide unused wrapper-field materialization. VmHWM covers
the whole suite, validation, allocators/GC and retained Go sinks; it is neither
per-operation memory nor an allocation count.

Do not infer portable parity, durability, cold-I/O, equal-security or universal
language performance from this harness. Publish regressions and unsupported cases.
