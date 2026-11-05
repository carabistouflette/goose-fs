# Identical-code listing controls

Independently build one trusted revision twice at the same absolute source,
harness, output, CWD and GOOSE_HOME paths. Remove the private build tree and
caches between builds. Compiler, stdlib and flags match. Saved executables have
different execution paths (a/b), recorded with runtime settings, affinity and load.

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
Old results remain unchanged. Future A/B work needs matched-path builds and its
own control. No host settings change or isolation claim is made.
