# Rename policies and native task costs — 2026-11-04

Measured clean source: `15a4951f680c7c9d1abcebc96296dc672189183c`; public rename core: `cd0bd29c78c435caaebf75bfecd8e3e2083636eb`. [All raw samples and verified provenance](raw.json) · [Interactive chart](comparison.html).

Five shuffled process rounds, seven sample means per workload/runner/round, 200 iterations per sample. All 4,340 rows, including 875 unsupported, are retained across 31 workloads. Values are median sample means. Rename rows are **ns per pair: two namespace operations**; other rows remain ns/call. Warm tmpfs, shared Intel Core Ultra7 258V Linux host, CPU6 affinity, without exclusive-core/frequency isolation.

The basic rows move one existing entry to an absent destination and back. Replace is the policy name; these rows do not measure existing-target overwrite latency. Root lifecycle is outside timing. In this run Root basic pairs take 4,934 ns for goose-fs versus Go 7,088 ns (about 1.44× as fast), and checked-parent-sync Root pairs take 9,775 ns versus 20,347 ns (about 2.08× as fast). Absolute basic pairs take 7,210 ns for goose-fs versus Rust 4,388 ns and Go 6,867 ns; checked-sync absolute pairs take 11,949 ns versus Rust 11,211 ns and Go 20,999 ns. All slower cells remain visible. Small differences may be shared-host noise; these differing native API task costs do not establish equal-security performance or universal superiority.

**Goose standard rename_file always performs best-effort destination-parent sync**, even in the basic row. Rust/Go/fs basic calls request no sync, so that row's work is not identical. Checked-sync absolute rows compose two readable-parent opens before each rename, both sync calls and cleanup for Rust/Go; fs uses RenameOptions.sync_parents=true. Rust File::Drop cannot report close errors. Absolute Rust/Go rename re-resolves pathnames, so preopened sync handles are not a concurrent-parent identity guarantee; fixtures remain stable. goose-fs uses the exact held parent FDs for rename and sync. Go Root checked rows use two readable Root.Open(".") handles; Root lifecycle is excluded. Goose lacks a checked-sync result. NoReplace is unsupported outside fs in this native API profile; link+unlink is not substituted for atomic generic entry rename.

All listings in this profile explicitly select goose-fs adaptive staging; other runners' listing APIs are unchanged. [The long-name staging report](../2026-11-04-listing-staging/README.md) retains adaptive regressions and noisy one-pass controls. This profile's short names fit one staging pass.

| Workload | goose-fs ns | Goose stdlib ns | Rust ns | Go ns |
| --- | ---: | ---: | ---: | ---: |
| read-fresh-0 | 2,899 | 1,926 | 2,006 | 4,198 |
| read-reuse-0 | 2,687 | 1,918 | 2,196 | 2,992 |
| read-retained-0 | 86 | unsupported | 212 | 7 |
| read-fresh-64 | 3,257 | 2,529 | 2,391 | 4,489 |
| read-reuse-64 | 3,063 | 2,516 | 2,629 | 3,444 |
| read-retained-64 | 373 | unsupported | 303 | 306 |
| read-fresh-4096 | 3,148 | 2,628 | 2,375 | 5,250 |
| read-reuse-4096 | 2,961 | 2,638 | 2,434 | 3,574 |
| read-retained-4096 | 461 | unsupported | 416 | 436 |
| read-fresh-65536 | 8,526 | 7,755 | 6,207 | 17,134 |
| read-reuse-65536 | 6,365 | 7,768 | 6,013 | 6,988 |
| read-retained-65536 | 3,935 | unsupported | 4,038 | 3,756 |
| read-fresh-1048576 | 121,264 | 136,383 | 78,507 | 263,094 |
| read-reuse-1048576 | 84,862 | 118,865 | 86,359 | 73,630 |
| read-retained-1048576 | 70,398 | unsupported | 81,047 | 69,044 |
| list-sorted-0 | 5,043 | 1,919 | 2,097 | 2,281 |
| list-sorted-1 | 4,969 | 2,039 | 2,190 | 2,509 |
| list-sorted-128 | 27,569 | 19,170 | 31,023 | 34,115 |
| list-sorted-4096 | 2,701,966 | 2,398,957 | 2,191,887 | 3,125,761 |
| metadata-file | 1,906 | unsupported | 657 | 943 |
| lock-exclusive-pair | 708 | unsupported | 486 | unsupported |
| is-dir | 1,780 | 595 | 620 | 737 |
| root-read-fresh-64 | 2,732 | unsupported | unsupported | 5,156 |
| root-metadata-file | 1,024 | unsupported | unsupported | 865 |
| root-list-sorted-128 | 31,668 | unsupported | unsupported | 28,789 |
| rename-replace-pair | 7,210 | 7,753 | 4,388 | 6,867 |
| rename-parents-sync-pair | 11,949 | unsupported | 11,211 | 20,999 |
| rename-noreplace-pair | 7,280 | unsupported | unsupported | unsupported |
| root-rename-replace-pair | 4,934 | unsupported | unsupported | 7,088 |
| root-rename-parents-sync-pair | 9,775 | unsupported | unsupported | 20,347 |
| root-rename-noreplace-pair | 4,861 | unsupported | unsupported | unsupported |


## Method and reproduction

Each rename pair performs left→right and right→left with its destination absent before each leg. Full preflight observes the intermediate file contents and source absence, then restores the original name; postflight verifies the restored content and absent destination. Timers include both renames, public status/outcome checks and checksum work. Checked rows also include both parent opens, sync calls and cleanup for each leg. Fixture creation, full-content checks, Root/Context lifecycle, warmup and formatting are excluded. The harness independently checks final entry/content after every runner process. Checksums count successful pairs, not individual renames.

Pinned Goose's best-effort helper resolves its destination parent after renaming and does not report sync errors. Other lookup, no-follow, error, bounds, ownership and output contracts also differ. Reads/metadata/locks retain their existing policy disclosures. Full pattern/name checks run outside timers; fresh timed reads receive length/endpoints rather than a full-content postcheck. Whole-process VmHWM includes registry initialization, validation, allocator/GC history and retained sinks; it is not per-operation memory or allocations. No cold-storage, remote-filesystem, contention, crash-recovery or equal-security claim. See [all policies](../../compare/README.md), the [rename contract](../../../docs/RENAME.md), and [remaining Linux coverage](../../../docs/feature-coverage.md).

Check out measured source and install the pinned Goose compiler and recorded Rust/Go toolchains, then:

```sh
python3 bench/compare/build.py --goose .toolchain/goose/build/goose --cc gcc --adaptive-listing
python3 bench/compare/run.py --goose .toolchain/goose/build/goose --cc gcc --adaptive-listing \
  --iterations 200 --rounds 5 --seed 20261104 --output .build/compare/rename-final.json
```

The recorded run used `taskset -c 6`. Source/binary/toolchain inputs and the selected adaptive profile were verified before/after timing. Compiler executable hash, toolchain versions/settings, fixture hashes, all raw batches and process peak RSS are retained. No other heavy goose-fs job ran during timing; other projects' shared-host activity was not excluded. A separate hardened-adapter profile remains outstanding.

## Validation

Independent security and quality/performance implementation, contract and benchmark reviews passed. GCC and Clang passed full public/JIT/optimized/debug/worker/native/OS/fault/fallback suites, ASan/UBSan and native static analysis. Six targeted compiler/resolver model runs each passed 336 OS-oracle cases, 2,000 ancestor-parent swap probes, permission distinctions, binary names, ENOENT phase distinctions, concurrent NoReplace contenders, complete old/new replacement reads, uncertain EXDEV and FD balance. Native faults cover rename success followed by EIO, EINTR without rename retry, unsupported NoReplace without fallback, both sync attempts, every final close position, combined primary/cleanup errors, exact FD-number reuse, malformed aliases, forced parent fallback and closed standard descriptors. Intermediate walker close errors now stop all shared callers before downstream effects while preserving a failed next-open as primary. Tests do not prove absence of bugs.

The public core's GCC/Clang CI passed at [cd0bd29](https://github.com/carabistouflette/goose-fs/actions/runs/41904186551). A fresh anonymous HTTPS clone of that pin passed package checks, the JIT rename regression and read/stream/Root examples with the pinned compiler. Copying, staged-byte/installation helpers, durable unlink, canonical paths and other Linux/platform gaps remain; this increment does not claim full Rust/Go feature parity.
