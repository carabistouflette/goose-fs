# Held-file metadata task costs — 2026-11-05

Measured clean source: `d100cf58d719fde6e8a0b04fa0ad2895e3faff81`; setter core: `e2414156fa1043b9fe9ac39d1fff024cb31f18d8`. [All raw samples and provenance](raw.json) · [Interactive chart](comparison.html). The run timestamp is 2026-11-04T23:20:47Z (2026-11-05 in the author's local timezone).

Five shuffled process rounds, seven sample means per workload/runner/round, 200 iterations per sample. All 4,760 rows, including 1,015 unsupported, are retained across 34 workloads. Values below are median sample means. Setter rows are **ns per single setter call**; rename rows are ns per two-operation pair. Warm tmpfs, shared Intel Core Ultra7 258V Linux host, CPU6 affinity, without exclusive-core or frequency isolation.

The three new goose-fs rows take 429 ns for permissions, 490 ns for ownership and 510 ns for exact times; Rust takes 339, 411 and 461 ns respectively. Go takes 420/493 ns for permissions/ownership. goose-fs is about 11–27% slower than Rust on these rows; its Go differences are within about 2.2%, which should not be treated as a speed win on this shared host. Go's held-File time setter and all pinned Goose stdlib held-File setters are unsupported in this native API profile. No pathname or raw-syscall substitute is timed as an equivalent held-File operation. This increment does not establish universal performance superiority or full feature parity.

| Workload | goose-fs ns | Goose stdlib ns | Rust ns | Go ns |
| --- | ---: | ---: | ---: | ---: |
| read-fresh-0 | 3,375 | 2,547 | 2,261 | 6,369 |
| read-reuse-0 | 3,351 | 2,494 | 2,458 | 4,658 |
| read-retained-0 | 105 | unsupported | 243 | 10 |
| read-fresh-64 | 3,826 | 3,371 | 2,782 | 6,891 |
| read-reuse-64 | 3,924 | 3,428 | 3,028 | 5,110 |
| read-retained-64 | 463 | unsupported | 367 | 490 |
| read-fresh-4096 | 4,143 | 3,744 | 2,967 | 9,260 |
| read-reuse-4096 | 4,008 | 3,727 | 3,049 | 6,134 |
| read-retained-4096 | 632 | unsupported | 530 | 643 |
| read-fresh-65536 | 12,880 | 11,897 | 8,381 | 31,516 |
| read-reuse-65536 | 9,529 | 11,958 | 8,532 | 12,403 |
| read-retained-65536 | 5,944 | unsupported | 5,906 | 6,365 |
| read-fresh-1048576 | 234,575 | 270,244 | 170,774 | 429,168 |
| read-reuse-1048576 | 177,046 | 272,758 | 174,167 | 189,022 |
| read-retained-1048576 | 156,692 | unsupported | 171,677 | 173,900 |
| list-sorted-0 | 8,303 | 3,164 | 3,162 | 4,004 |
| list-sorted-1 | 7,976 | 3,325 | 3,424 | 4,187 |
| list-sorted-128 | 46,755 | 33,299 | 47,596 | 59,161 |
| list-sorted-4096 | 3,582,138 | 3,289,359 | 3,203,882 | 4,961,915 |
| metadata-file | 2,126 | unsupported | 784 | 1,123 |
| lock-exclusive-pair | 817 | unsupported | 611 | unsupported |
| is-dir | 2,015 | 710 | 750 | 1,129 |
| root-read-fresh-64 | 3,350 | unsupported | unsupported | 7,565 |
| root-metadata-file | 1,208 | unsupported | unsupported | 1,036 |
| root-list-sorted-128 | 45,630 | unsupported | unsupported | 44,581 |
| rename-replace-pair | 11,016 | 9,678 | 5,431 | 9,615 |
| rename-parents-sync-pair | 18,795 | unsupported | 15,113 | 35,021 |
| root-rename-replace-pair | 7,344 | unsupported | unsupported | 10,229 |
| root-rename-parents-sync-pair | 14,164 | unsupported | unsupported | 35,392 |
| rename-noreplace-pair | 10,231 | unsupported | unsupported | unsupported |
| root-rename-noreplace-pair | 7,569 | unsupported | unsupported | unsupported |
| file-set-permissions | 429 | unsupported | 339 | 420 |
| file-set-owner | 490 | unsupported | 411 | 493 |
| file-set-times | 510 | unsupported | 461 | unsupported |

## Method and limits

Setters use one read-only-open regular File, with open/close, Context lifecycle, identity capture, seek setup, warmup and metadata/content checks outside timing. Each iteration sets mode 0640, the fixture's captured current numeric UID/GID, or exact access time 1000.123456789 and modification time 2200000000.987654321 seconds since the Epoch. Repeated same-value requests remain OS mutations; chown can change ctime or privilege attributes. No implicit sync is requested. Status checks and one checksum increment per successful call are timed. The fixture supports nanosecond timestamps and these date ranges. Every runner preserves the held cursor. Independent Python postflight checks complete fixture content, mode/IDs and exact timestamps for supported time setters.

Rust uses File::set_permissions, Unix fchown and File::set_times. Go uses File.Chmod and File.Chown; syscall.Stat_t extracts fixture IDs outside timing. Goose stdlib has no retained Files in the pinned version. The runners have different lock, runtime, token-validation and error contracts. Timings are sequential task costs, not equal-security or concurrent-throughput measurements. Native syscall counts are not instrumented.

All earlier workloads remain visible. Listings explicitly select goose-fs adaptive staging; [long-name staging regressions](../2026-11-04-listing-staging/README.md) remain documented separately. Rename pairs move to absent destinations and back, without measuring existing-target overwrite latency. Pinned Goose rename_file always best-effort syncs its destination parent even in the basic row. Checked rows include both parent opens/syncs/cleanup; Rust Drop cannot report close errors. Absolute Rust/Go checked rename compositions re-resolve pathnames; fixtures are stable. Root lifecycle is excluded. See [all comparison policies](../../compare/README.md) and the [previous rename report](../2026-11-04-rename/README.md).

Read/list full pattern/name validation occurs outside timers; timed checksums consume length and endpoints, and fresh timed reads do not receive a full-content postcheck. Whole-process VmHWM includes validation, registry initialization, allocator/GC history and retained sinks; it is not per-operation memory or allocations. All raw data, including slower cells, is retained. No cold-storage, remote-filesystem, crash-recovery or equal-security ranking is claimed. A hardened-adapter comparison remains outstanding.

## Reproduction

Check out measured source and install the pinned Goose compiler and recorded Rust/Go toolchains, then:

```sh
python3 bench/compare/build.py --goose .toolchain/goose/build/goose --cc gcc --adaptive-listing
python3 bench/compare/run.py --goose .toolchain/goose/build/goose --cc gcc --adaptive-listing \
  --iterations 200 --rounds 5 --seed 20261105 --output .build/compare/file-metadata-final.json
```

The recorded run used `taskset -c 6`. Build/run source, binary, toolchain and adaptive-profile checks passed before/after timing. Executable hashes, fixture hashes, toolchain flags/settings, affinity, host load and per-process peak RSS are in raw.json. No other heavy goose-fs job ran during measurement; other projects' host activity was not excluded.

## Validation

Two independent reviewers checked the production implementation and benchmark contract. Their concrete harness findings were fixed before the measured freeze: preserve the fixture's actual inherited IDs and align untimed metadata-validation placement across runners. GCC/Clang full tests and ASan/UBSan passed; native GCC and Clang static analysis reported no diagnostics. Public JIT/optimized/debug setters, 71 direct-OS oracle cases per model run, forced lookup/statx fallback variants, numeric/action edges, full resource-table operation, duplicate/hardlink/unlink lifetime and cursor preservation passed. Injected failures cover EINTR without retry, permission/I/O errors, successful mutation followed by an error, lock release and invalid tokens.

A separately run root-owned fixture test now passes after fixing its initial library-loading permission bug: a fresh process drops supplementary groups and UID/GID before opening the file; held tokens cannot authorize otherwise-forbidden mode, owner or timestamp changes. Keep/Keep still validates lifetime. CI explicitly runs this check with sudo for both compilers. This test-only follow-up changes no production code or measured harness sources.

Read [the setter contract](../../../docs/FILE-METADATA.md) for access rules, special bits, ID/time ranges, error effects and explicit synchronization. Path/Root/directory metadata mutations, copying, staged-byte helpers, durable unlink, canonical paths and other Linux/platform gaps remain in [feature coverage](../../../docs/feature-coverage.md). Tests and reviews do not prove absence of bugs.
