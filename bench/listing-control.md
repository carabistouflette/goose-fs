# Identical-code listing controls

Independently build one trusted revision twice at the same absolute source,
harness, output, CWD and GOOSE_HOME paths. Remove the private build tree and
caches between builds. Compiler, stdlib and flags match. Saved executables have
different execution paths (a/b), recorded with runtime settings, affinity and load.

Requires Linux, Python 3.11+, GNU objcopy, the pinned Goose compiler and a C compiler.

```sh
python3 bench/listing-control-build.py --revision FULL_TRUSTED_COMMIT --goose /path/to/goose
python3 tests/listing_control.py --goose /path/to/goose
taskset -c 6 python3 bench/listing-measure.py --identical-control --goose /path/to/goose \
  --baseline .build/listing-control/a --full .build/listing-control/b \
  --baseline-revision FULL_TRUSTED_COMMIT --build-manifest .build/listing-control/build.json \
  --creation-order shuffled --rounds 5 --iterations 5 --output .build/listing-control/raw.json
```

The manifest binds source/rendered hashes, compiler bytes/versions, stdlib sources,
exported files, paths/settings/logs, complete ELF hashes and text/rodata hashes.
Unequal executables/sections retain evidence but are ineligible for timing. Failed
builds invalidate the old manifest. Builders hold an exclusive lock; recording
holds a shared lock through final checks. Optimized Python is rejected. Outputs
must be under this checkout's .build. Source revisions must be trusted.

All 76 cases, independent filename/order preflights and checksums are retained.
Five rounds produce 5,320 sample means for two identical full-staging binaries.
There is no adaptive comparison. A/A variation is an observation, not a speed
gain, correction, normalization factor or proof of cause. ASLR, execution paths,
allocator history, temperature/frequency and host work are not held constant.
A/A recording refuses an existing output path and creates new records exclusively.
Old results remain unchanged. Future A/B work needs matched-path builds and its
own control. No host settings change or isolation claim is made.

## Matched baseline/candidate profile

```sh
python3 bench/listing-control-build.py --revision BASELINE_FULL_SHA --candidate-revision CANDIDATE_FULL_SHA --goose /path/to/goose
python3 tests/listing_matched.py --goose /path/to/goose
taskset -c 6 python3 bench/listing-measure.py --matched-comparison --goose /path/to/goose --baseline .build/listing-matched/a1 --full .build/listing-matched/b1 --baseline-revision BASELINE_FULL_SHA --candidate-revision CANDIDATE_FULL_SHA --build-manifest .build/listing-matched/build.json --creation-order shuffled --rounds 5 --iterations 5 --output .build/listing-matched/raw.json
```

Build order is a1, b1, a2, b2. Reset the entire private build/cache tree between
builds. a1/a2 export baseline; b1/b2 export candidate. Within each revision, both
complete executables and text/rodata must match before timing. Cross-revision
executables may differ. Identity flags apply to the recorded replica pairs, not
all four collectively. Source maps and hashes for all labels remain visible.
Exact pins and profiles are checked. Five rounds retain 10,640 sample means.
Report all four medians, all four baseline/candidate ratios and both same-revision
controls, without pooling, favorable-replica selection or normalization. Execution
paths and host effects remain uncontrolled. CI tests this profile using one
revision in both roles and makes no performance claim.
