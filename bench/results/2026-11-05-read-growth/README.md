# Bounded read growth: candidate not adopted

The sole 1KiB initialization candidate did not meet the [preregistered rules](../../read-growth/README.md). The released FS runtime is retained. Replica controls failed, not every target comparison reached 1.10, and other cells raised descriptive regression flags. These results establish neither a causal regression nor a speedup, SOTA performance, security ranking or overall leadership. No fill-size sweep or replacement timing was performed.

## Source and qualification

- Two independent agent reviewers approved the source/recorder and final artifacts, recomputing all 192 medians, 96 controls and 480 ratios and matching every process stream.
- Baseline library: `ce3bdcf92c07c03761e73333526933d2db8b33b1`.
- Sole candidate library change: `f24d5b49f4b7b68c1f4949032eaaeb7623cdc800`; only absolute `fs::read` zero-filled growth in ≤1024-byte steps. Shrink, complete initialization, native code and error/close policy stayed the same. Root and held-file reads were untouched.
- Measured clean source/driver/recorder: `a6f1345bd1b69bb642d78763ddfc41b7b545ec14`. [Exact-source CI](https://github.com/carabistouflette/goose-fs/actions/runs/42003091311) passed GCC13/Clang18 release/sanitizer matrices and default plus matched-growth recorder checks.
- Local GCC16 and Clang23 frozen builds each passed 384 release/fresh probes and 176 fault/boundary probes. All four pairs had identical whole ELF/text/rodata bytes. Both 672-mean nonqualifying smoke checks and negative baseline/library-byte/overwrite gates passed; seven existing and five growth decision/retention tests passed.
- A clean anonymous HTTPS checkout of measured `a6f1345` passed `make check`, a fresh eight-replica build with all 560 checks, and the 672-mean smoke plus negative provenance/overwrite gates.
- Local full GCC check/test and Clang test/ASan/UBSan suites passed. Dirty retained growth gaps around 1024 bytes, fresh empty outputs, full byte contents/errno, fallback, EINTR/partial reads, misleading stat sizes, exact consumed-close FD reuse and descriptor balance remain checked.
- In each of the two fixed attempts, 480 canonical-path process invocations produced 3360 means. All 960 lossless process streams match the 6720 JSON rows, checksums, selected executable hashes, paths and schedules. Both attempts passed all 384+176 preflight and postflight checks.
- Runtime restoration: `81509ef` restores `fs.goose` exactly to the baseline. Public native sources, fs.build and compiler pin are unchanged. No consumer API or parent integration change is requested.

## Native diagnosis and limits

For the released runner reading a 64-byte file with a 1MiB budget, 96.98% of sampled **user cycles** landed at libc’s REP STOSB zero-fill instruction (756 samples, zero reported lost samples). This excludes kernel and blocked time. A raw Callgrind run attributes 99.43% of its 118162689 modeled instructions to memset; exact-budget control totals 667436. Syscall-count summaries agree exactly between those budgets: 884 total including startup, 232 read and 113 openat2 calls. The hot emitted read specialization calls memset/native I/O without allocator calls.

The one fixed 1024-byte candidate shifts work to libc’s vector-fill path. Callgrind totals 11312344 modeled instructions, but fewer modeled instructions did **not** establish a native throughput improvement. Diagnostic sampling, instrumentation and nonmatched elapsed values are separate from the controlled records. Failed explicit-PMU/call-stack sampling attempts are retained; no host permission, frequency, affinity policy or sysctl setting was changed. Per-process taskset affinity was used.

[Diagnostic provenance and text/raw Callgrind](diagnostics/) bind both runner hashes, source bytes, libc and fixture. No executables, build/cache directories or raw perf stack-memory data are published. Kernel-IP literals in perf text summaries are redacted; percentages, counts and measured values are unchanged.

## Complete controlled results

Five shuffled rounds, eight labels, seven means per invocation. Each reused mean averages 2000 calls; `fresh-max` averages 100 calls with a new logical output per call and its own untimed warmup. FS variants, Rust and Go all execute at one canonical path after atomic staging/hash checks outside timers. Fixture creation/preflight are outside timing; subsequent logical growth/zeroing, fresh allocation/initialization, validation, I/O, status checks and checksum work stay inside. Normal language lifetime/GC costs are included as incurred; deferred reclamation is not charged per call.

Controls below show symmetric max/min for base/candidate/Rust/Go respectively and must all be ≤1.05 in every cell of both records. Base/candidate spans all four cross-replica ratios; target `large-budget` requires the entire range ≥1.10 in both records. A non-target candidate/base ratio >1.05 blocks adoption. Full-precision ratios and every reference/FS ratio are in [analysis.json](analysis.json); display rounding never determines the decision.

### Attempt 1

| Cell | Base1 ns | Base2 ns | Candidate1 ns | Candidate2 ns | Rust1 ns | Rust2 ns | Go1 ns | Go2 ns | Controls base/FS/Rust/Go | Base/candidate range |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| empty | 4260 | 4833 | 5975 | 6190 | 6347 | 5287 | 4795 | 4827 | 1.1345/1.0360/1.2005/1.0067 | 0.6882–0.8089 |
| tiny | 5047 | 5673 | 5302 | 5074 | 4793 | 5928 | 7667 | 5589 | 1.1240/1.0449/1.2368/1.3718 | 0.9519–1.1181 |
| page | 7163 | 5358 | 6426 | 5164 | 5171 | 4973 | 5795 | 8887 | 1.3369/1.2444/1.0398/1.5336 | 0.8338–1.3871 |
| chunk | 9095 | 13846 | 8401 | 13472 | 13405 | 11885 | 9670 | 14858 | 1.5224/1.6036/1.1279/1.5365 | 0.6751–1.6481 |
| max | 130868 | 130887 | 103273 | 96510 | 101366 | 144495 | 109936 | 114455 | 1.0001/1.0701/1.4255/1.0411 | 1.2672–1.3562 |
| large-budget | 54880 | 68604 | 56828 | 46267 | 51805 | 54586 | 59510 | 52271 | 1.2501/1.2283/1.0537/1.1385 | 0.9657–1.4828 |
| missing | 2971 | 3480 | 3187 | 2902 | 2747 | 3975 | 4035 | 5048 | 1.1713/1.0982/1.4470/1.2511 | 0.9322–1.1992 |
| overflow | 7452 | 6638 | 6927 | 5101 | 4631 | 5928 | 7444 | 5561 | 1.1226/1.3580/1.2801/1.3386 | 0.9583–1.4609 |
| zero-overflow | 5571 | 4539 | 6862 | 4275 | 6983 | 6398 | 8369 | 5178 | 1.2274/1.6051/1.0914/1.6163 | 0.6615–1.3032 |
| nonregular | 7101 | 4476 | 5822 | 4416 | 7091 | 5910 | 8048 | 6364 | 1.5865/1.3184/1.1998/1.2646 | 0.7688–1.6080 |
| deep | 8065 | 7018 | 8756 | 8942 | 5675 | 7291 | 9472 | 6881 | 1.1492/1.0212/1.2848/1.3765 | 0.7848–0.9211 |
| fresh-max | 163279 | 161355 | 179886 | 141677 | 149502 | 198038 | 597634 | 593961 | 1.0119/1.2697/1.3247/1.0062 | 0.8970–1.1525 |

### Attempt 2

| Cell | Base1 ns | Base2 ns | Candidate1 ns | Candidate2 ns | Rust1 ns | Rust2 ns | Go1 ns | Go2 ns | Controls base/FS/Rust/Go | Base/candidate range |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| empty | 3992 | 4185 | 3977 | 4064 | 3886 | 3886 | 4594 | 4523 | 1.0483/1.0219/1.0000/1.0157 | 0.9823–1.0523 |
| tiny | 4483 | 4216 | 4615 | 4459 | 4325 | 4376 | 5127 | 5385 | 1.0633/1.0350/1.0118/1.0503 | 0.9135–1.0054 |
| page | 4588 | 4822 | 4680 | 4592 | 4569 | 4530 | 5482 | 5438 | 1.0510/1.0192/1.0086/1.0081 | 0.9803–1.0501 |
| chunk | 8386 | 8147 | 8248 | 8505 | 8554 | 8692 | 9170 | 9579 | 1.0293/1.0312/1.0161/1.0446 | 0.9579–1.0167 |
| max | 82042 | 84740 | 96168 | 87981 | 86134 | 85801 | 87740 | 90941 | 1.0329/1.0931/1.0039/1.0365 | 0.8531–0.9632 |
| large-budget | 42731 | 44117 | 41320 | 34313 | 44951 | 44590 | 45331 | 48322 | 1.0324/1.2042/1.0081/1.0660 | 1.0341–1.2857 |
| missing | 2702 | 2687 | 2651 | 2549 | 2490 | 2538 | 2900 | 2962 | 1.0056/1.0400/1.0193/1.0214 | 1.0136–1.0600 |
| overflow | 4884 | 4555 | 4659 | 4344 | 4374 | 4343 | 5130 | 5343 | 1.0722/1.0725/1.0071/1.0415 | 0.9777–1.1243 |
| zero-overflow | 4018 | 4220 | 4031 | 4509 | 4085 | 4058 | 4809 | 4582 | 1.0503/1.1186/1.0067/1.0495 | 0.8911–1.0469 |
| nonregular | 4141 | 4209 | 4386 | 4055 | 4293 | 3904 | 4570 | 4616 | 1.0164/1.0816/1.0996/1.0101 | 0.9441–1.0380 |
| deep | 5868 | 5907 | 5854 | 5491 | 5244 | 5615 | 6675 | 6587 | 1.0066/1.0661/1.0707/1.0134 | 1.0024–1.0758 |
| fresh-max | 138834 | 119171 | 114079 | 112097 | 117671 | 141047 | 286856 | 286287 | 1.1650/1.0177/1.1987/1.0020 | 1.0446–1.2385 |

Attempt 1 descriptive non-target regression flags: empty, tiny, page, chunk, missing, zero-overflow, nonregular, deep, fresh-max.
Attempt 2 descriptive non-target regression flags: tiny, max, zero-overflow, nonregular.

The target ranges are 0.9657–1.4828 and 1.0341–1.2857 (base/candidate); favorable individual replicas cannot be selected. Across both records, unchanged replica variation is retained without correction or a causal explanation. First-attempt and second-attempt shifts are not normalized.

## Completion, provenance and reproduction

Processes were sequential on CPU6. This thread’s other heavy local jobs finished before recording. CPU4 courtesy remained active and was honored. Other users/threads could continue on this shared host; no exclusive core, cache or frequency isolation is asserted. Compiler/libc/CPU metadata, actual canonical commands, source files, stdlib hashes and both replica ELF/section hashes are in the JSON records. Go is `go1.27.3-X:nodwarf5`; Rust1.99.1. Toolchain identities are recorded, not a hermetic capture of every linker/sysroot file.

The outer command wrapper reported status143 after both recorder summaries had persisted `complete`, all 3360 rows each and successful final source/binary/toolchain checks. Its cause is not established. Both process journals end with `finish:complete`; all 960 measured children report exit0. No measured process remained. The analysis command was subsequently run separately against the unchanged records; no measurements were repeated. [Wrapper observation](diagnostics/outer-wrapper-status.json). The checkpoint already fails adoption independently of this anomaly.

- Attempt 1: `2026-11-05T09:36:53.130631+00:00`–`2026-11-05T09:39:51.927664+00:00`; [JSON](attempt-1.json), [lossless process JSONL](attempt-1.jsonl).
- Attempt 2: `2026-11-05T09:39:52.118298+00:00`–`2026-11-05T09:42:17.370320+00:00`; [JSON](attempt-2.json), [lossless process JSONL](attempt-2.jsonl).

To reproduce the candidate experiment, first check out the full measured source commit `a6f1345bd1b69bb642d78763ddfc41b7b545ec14`, then follow the [build/record commands](../../read-growth/README.md). Current main retains the baseline initialization, so building it against the baseline is a same-code control, not reproduction of the rejected candidate. Use a new build directory and never replace old measured attempts.

```sh
python3 bench/read-growth/analyze.py bench/results/2026-11-05-read-growth/attempt-1.json bench/results/2026-11-05-read-growth/attempt-2.json
```

[Interactive medians, controls and ratios](comparison.html). SHA-256 for the complete numeric/process records:

- `analysis.json`: `1a86a25e33ed6a0a199e40b4705a73d41725de28cd4e543cd0ab0ef7cf2d388f`
- `attempt-1.json`: `81d76f0ede32065703b6ed1176385e0abc5482832bbc299c386ed6ef970bfa18`
- `attempt-1.jsonl`: `ba86037360c1bed820832d12fd01280f585bcaeb942ef5abc61cea7e95232363`
- `attempt-2.json`: `03206aaaba51854e9a7f65b9fdcc0ddfad127de6d57d11273fa7ce77d56baeb4`
- `attempt-2.jsonl`: `89cfa8893d0b83b4a6766b8b3ed12567de2878d4844815ae611856fd6e3829cb`
