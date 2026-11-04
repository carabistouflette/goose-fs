# Contributing

Keep the interface small, explicit and bounded. Goose owns validation and output;
the native Linux kernel owns short-lived OS resources. Do not broaden pathname,
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
