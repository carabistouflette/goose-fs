# Contributing

Keep the interface small, explicit and bounded. Goose owns validation and output;
the native C layer owns OS descriptors. Retained resources require explicit Context ownership and
the lock-order invariants in native/handles.c; calls into Goose while holding native locks are forbidden. Do not broaden pathname,
symlink or failure semantics without reviewing the contract and adversarial tests.
Use focused branches (`feat/...`, `fix/...`) and Conventional Commits with imperative
subjects: `feat: add ...`, `fix: reject ...`, `test: cover ...`, `docs: clarify ...`.
Each commit contains one coherent change. No stability guarantee before 1.0.

For behavior changes add public-interface regression tests. Run `make format`,
`make check test`, `make sanitize SANITIZER_CC=gcc`, the same with clang, and
`git diff --check`. Request independent security and quality/performance reviews,
fix actionable findings, and keep CI passing. Compiler updates require a reviewed
full upstream commit in GOOSE_REVISION and full validation. Never commit credentials,
generated compiler output, or private coordination notes.

Profile before optimizing. `make bench` records raw public-interface measurements,
compiler/source revisions, hardware and flags. Report all workloads and regressions;
no universal microbenchmark ranking or CI timing thresholds. Use semantic versions
only when a reviewed release is ready.

## Test environment

Use the compiler in GOOSE_REVISION. To reuse that exact compiler, pass
`GOOSE=/absolute/path/to/goose` to Make. Setup refuses modified compiler source.
Tests need Python 3.11+, Linux /proc and GCC/Clang for the full matrix. The retained
resource-capacity test requires a hard descriptor limit of at least 5000.
Rename tests need NoReplace support and directory fsync. Metadata tests need
POSIX permissions and timestamps before 1970 and after 2038; actual filesystem
rounding is compared against OS calls. Link race fixtures need 513-byte targets;
4095-byte real targets are explicitly skipped on ENAMETOOLONG, while synthetic
maximum-buffer tests remain required. Sanitizers supplement debug/runtime bounds
and independent models; they do not cover every logical Goose array lifetime.

See [documentation and measurement audit](docs/ANNOUNCEMENT-AUDIT.md) when changing
public claims. Historical samples must remain unchanged. A benchmark date alone
is not evidence that it measures the current code.
