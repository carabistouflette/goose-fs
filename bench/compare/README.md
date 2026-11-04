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
Retained-read cases open once before timing, then read at offset zero into reused
storage through goose-fs read_at, Rust FileExt::read_at and Go File.ReadAt. Open,
Context initialization and close are outside those timings; the pinned Goose
stdlib has no retained File API and receives unsupported rows. Exact-sized stable
fixtures are intended to permit one successful pread for nonempty inputs, despite
Go ReadAt's more general fill/EOF contract. Short reads/EINTR remain possible;
syscall counts are not measured. Zero-sized retained reads may avoid
syscalls. Context+entry lock and error checks remain in goose-fs timings; these
are sequential retained calls, not a concurrency or lifecycle-cost measurement.
The uncontended lock case times an exclusive try-acquire/unlock pair through
goose-fs and Rust File. Both use Linux flock on this host; Go os and the pinned
Goose stdlib have no portable File locking API and receive unsupported rows.
It excludes open/close and does not measure contention or polling wakeup costs.
Root cases open a directory once, then time fresh 64-byte reads, final-entry
metadata and sorted 128-entry listings through goose-fs Root and Go os.Root.
Go listings use Root.Open+File.Readdirnames(-1)+slices.Sort; goose-fs retains the
1 MiB/4096-entry budget and structured entries with kind hints. Names alone are
consumed. Go Root DirEntry enumeration eagerly loads metadata, so using Readdirnames
avoids charging unused full metadata work to this names task. The Go result is
owned sorted strings, while goose-fs also returns kind hints.
Rust std and the pinned Goose stdlib have no equivalent Root API and receive
unsupported rows. Root creation/close are outside timing. Go permits in-tree links;
goose-fs rejects them. These common stable fixtures do not exercise that difference,
so the results remain task costs with different lookup/ownership policies.

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
