# Bounded-read contract comparison — 2026-11-05

No cell qualifies for an FS lead under the [preregistered rules](../../read-contract/README.md).
All eleven cells are inconclusive: none passes every language’s replica control in both
attempts. Every cell also fails the required 1.10 reference/FS ratio in at least one
cross-replica comparison. These recordings establish no overall leadership, SOTA,
causal optimization effect or general security equivalence. The published FS runtime
and native files are unchanged from `b53e1d336b9841d80375cb18c65031555283f20a`.

## Frozen source and validation

- Two independent agent reviewers approved the adapters/recorder and final publication artifacts. The final review recomputed all 132 medians, 176 ratios and 66 controls, and matched all 660 process streams to 4620 rows.
- Measured clean checkpoint: `dee8b163244dfa62eea7016835e9d40a70920342`.
- [Exact checkpoint CI](https://github.com/carabistouflette/goose-fs/actions/runs/41996200979): GCC13 and Clang18 release/sanitizer matrices plus the new read-contract job passed.
- Two independent builds per language at one reset source/output/cache path; whole ELF, text and rodata match within every language. The same six frozen executables serve both attempts.
- A clean anonymous HTTPS checkout of the measured checkpoint passed `make check`, a fresh six-replica build, all 321 contract probes and recorder smoke/rejection tests. GCC and Clang static analysis also reported no diagnostics in the two new C files.
- Local GCC16.2.1 and Clang23.1.4 builds each passed 210 release probes and 111 fault/boundary probes. Seven decision/retention tests and separate 462-row count-one recorder smokes passed for each build. Only the GCC build below is measured.
- Actual public FS / independent Rust and Go entry points are tested for bounded reads, complete bytes/errno, dirty retained-buffer growth, strict paths, symlinks, fallback, partial/EINTR/EIO reads, misleading fstat sizes, consumed close errors, exact descriptor reuse and leaks.
- The first two measured attempts completed normally; each has 2310 means (five shuffled rounds × eleven cells × six labels × seven means). Each mean averages 200 calls. Each attempt’s 210 release and 111 fault/boundary preflight and postflight probes passed.
- Processes ran sequentially on CPU6. Other local work owned by this thread finished before timing; this is a shared machine without exclusive-core, frequency or cache isolation. No reruns, correction, pooling or favorable-replica selection.

## Scope and implementation costs

The references are **Rust + Linux adapter with stat ABI bridge** and **Go + Linux adapter**,
not plain std::fs/os native APIs. They independently implement strict no-follow lookup,
regular-file checking, a limit-plus-one read and matching close/error behavior.
Rust’s narrow C bridge performs exactly one fstat and captures errno; all read/ownership
policy is Rust. Its compiler, source, flags and cost are included. Rust/Go zero their
4096-byte stack path scratch; FS initializes only path bytes plus terminator. These
adapters are not claimed to be optimal Rust/Go implementations. All three retain the
existing best-effort final-parent close limitation. See the contract for filesystem
races, special-file opening effects and caller ownership assumptions.

The pinned Goose stdlib whole-file API has no equivalent bounded/no-follow/errno
contract. Its separate [native API results](../2026-11-04-native-api/README.md) remain
available; silently dropping safeguards would not make it an eligible reference here.
Only reused-output warm-cache reads are measured. Initial buffer warmup is outside
each timer; later logical growth and zeroing remain inside, notably a 64-byte file
with a 1MiB budget. Fresh allocation, streaming, memory leadership, durability,
cold I/O and broad platform/API parity remain outside this profile.

## Complete medians and controls

All values below are ns/call medians across 35 process means per cell/label.
Controls are symmetric max/min within each language, required to be ≤1.05.
The ratio range spans all eight reference-replica/FS-replica comparisons and
must be entirely ≥1.10 in both attempts for a qualifying cell. Rounded display
values never determine labels; [analysis.json](analysis.json) retains full ratios.

### Attempt 1

| Cell | FS1 | FS2 | Rust1 | Rust2 | Go1 | Go2 | FS A/A | Rust A/A | Go A/A | Ref/FS range |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| empty | 4383 | 4373 | 4286 | 4281 | 5344 | 5301 | 1.0023 | 1.0012 | 1.0081 | 0.9767–1.2220 |
| tiny | 4913 | 4964 | 4911 | 4826 | 5814 | 5536 | 1.0104 | 1.0176 | 1.0502 | 0.9722–1.1834 |
| page | 5054 | 5142 | 4963 | 5120 | 6245 | 5960 | 1.0174 | 1.0316 | 1.0478 | 0.9652–1.2357 |
| chunk | 9386 | 9722 | 9389 | 9296 | 9666 | 10324 | 1.0358 | 1.0100 | 1.0681 | 0.9562–1.0999 |
| max | 76853 | 86803 | 82123 | 88823 | 93029 | 86674 | 1.1295 | 1.0816 | 1.0733 | 0.9461–1.2105 |
| large-budget | 48659 | 52679 | 46096 | 46109 | 52217 | 47812 | 1.0826 | 1.0003 | 1.0921 | 0.8750–1.0731 |
| missing | 2940 | 2965 | 2822 | 2657 | 3269 | 3506 | 1.0085 | 1.0621 | 1.0725 | 0.8961–1.1925 |
| overflow | 5063 | 5254 | 4940 | 4859 | 6022 | 6149 | 1.0377 | 1.0167 | 1.0211 | 0.9248–1.2145 |
| zero-overflow | 4523 | 4600 | 4504 | 4540 | 5505 | 5095 | 1.0170 | 1.0080 | 1.0805 | 0.9791–1.2171 |
| nonregular | 4474 | 4600 | 4729 | 4377 | 5362 | 5197 | 1.0282 | 1.0804 | 1.0317 | 0.9515–1.1985 |
| deep | 6359 | 6328 | 6245 | 5978 | 7185 | 6942 | 1.0049 | 1.0447 | 1.0350 | 0.9401–1.1354 |

### Attempt 2

| Cell | FS1 | FS2 | Rust1 | Rust2 | Go1 | Go2 | FS A/A | Rust A/A | Go A/A | Ref/FS range |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| empty | 4643 | 4638 | 4236 | 4622 | 4982 | 5320 | 1.0011 | 1.0911 | 1.0678 | 0.9123–1.1470 |
| tiny | 4929 | 5014 | 4687 | 4732 | 5468 | 5612 | 1.0172 | 1.0096 | 1.0263 | 0.9348–1.1386 |
| page | 5076 | 5410 | 4847 | 5226 | 6432 | 6382 | 1.0658 | 1.0782 | 1.0078 | 0.8959–1.2671 |
| chunk | 9390 | 9452 | 9584 | 9221 | 10659 | 9469 | 1.0066 | 1.0394 | 1.1257 | 0.9756–1.1351 |
| max | 80147 | 76607 | 84212 | 81992 | 76951 | 78090 | 1.0462 | 1.0271 | 1.0148 | 0.9601–1.0993 |
| large-budget | 49610 | 43138 | 44666 | 45324 | 49537 | 48121 | 1.1500 | 1.0147 | 1.0294 | 0.9003–1.1483 |
| missing | 2959 | 3057 | 2751 | 2832 | 3400 | 3585 | 1.0331 | 1.0294 | 1.0544 | 0.8999–1.2116 |
| overflow | 4957 | 4830 | 4965 | 4699 | 5805 | 6024 | 1.0263 | 1.0566 | 1.0377 | 0.9480–1.2472 |
| zero-overflow | 4834 | 4590 | 4404 | 4527 | 5310 | 5901 | 1.0532 | 1.0279 | 1.1113 | 0.9110–1.2856 |
| nonregular | 4435 | 4572 | 4361 | 4271 | 5555 | 5393 | 1.0309 | 1.0211 | 1.0300 | 0.9342–1.2525 |
| deep | 6524 | 6180 | 6071 | 6304 | 7805 | 7082 | 1.0557 | 1.0384 | 1.1021 | 0.9306–1.2629 |

The preregistered descriptive primary regression flags (any FS/reference >1.05)
are attempt 1: max, large-budget; attempt 2: empty, tiny, page, large-budget. They are observations, not a causal regression claim.
No runtime optimization is accepted from these inconclusive controls. The large-budget
cell is an investigation target, but this profile does not establish the cause of its cost.

## Raw data and reproduction

Check out the full measured source commit, install the pinned toolchains, then follow
[the build/record instructions](../../read-contract/README.md). The scripts make no
dependency downloads; never overwrite a measured build directory. The JSON records
bind source and Goose standard-library hashes, compiler identities, flags, actual
commands/build paths,
executable/section hashes, runtime settings, case byte paths/digests, process seeds,
check counts and all raw means. JSONL retains every process’s lossless stdout/stderr.
Go is recorded as `go1.27.3-X:nodwarf5`; Rust is 1.99.1. Toolchain/host details in
each record are authoritative. Rust/Go compiler identities are recorded, not a
hermetic capture of every system linker/sysroot file. These are not cross-host
reproducibility claims.

- Attempt 1: `2026-11-05T08:42:00.032105+00:00` to `2026-11-05T08:42:17.142650+00:00`; [JSON](attempt-1.json), [process JSONL](attempt-1.jsonl).
- Attempt 2: `2026-11-05T08:42:17.373159+00:00` to `2026-11-05T08:42:34.762906+00:00`; [JSON](attempt-2.json), [process JSONL](attempt-2.jsonl).

```sh
python3 bench/read-contract/analyze.py bench/results/2026-11-05-read-contract/attempt-1.json bench/results/2026-11-05-read-contract/attempt-2.json
```

[Interactive medians and controls](comparison.html). Complete raw files have these SHA-256 hashes:

- `analysis.json`: `90f41ba46102aa994c7d0dc44c2f13f1090e5c60dd19562584e363409f25ca7c`
- `attempt-1.json`: `936687c61a7a2d577d80666cd27c9125ef17bbd8560bc2e7bd59d4d217e1a3db`
- `attempt-1.jsonl`: `f7b5845b1f8f509f32f24da827f74983f548b7159e6a42e30ded5643b257a8f6`
- `attempt-2.json`: `c6cd9ced9a2704496d626be41703daa7c69e840417606a1627010c320eb75ff5`
- `attempt-2.jsonl`: `48e7c05a886bc4ebc7dbe8e78e51b84eed0d87e731c9476f14d7cfbd05b4863a`
