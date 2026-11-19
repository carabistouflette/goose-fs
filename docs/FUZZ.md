# Bounded path-grammar fuzzing

`make fuzz` builds the generated Goose path target with Clang/libFuzzer and
ASan/UBSan, runs a bounded campaign, replays the retained corpus through an
independent byte oracle, and runs a weakened-guard control. It is a test
harness, not a product surface, and it makes no filesystem, host-configuration,
timing, soak or universal-correctness claim.

## What the campaign exercises

The target is `tests/fuzz.goose`, compiled by the pinned compiler from
`GOOSE_REVISION` into generated C. Every input is one raw byte string, and each
call checks:

- `fs::valid_path` and `fs::valid_relative` against a second, split-based
  implementation of the documented component rule in the same file;
- `fs::valid_components` directly, and its agreement with the two wrappers;
- the documented metamorphic relations: stripping the leading `/` of a valid
  absolute path yields a valid relative path, appending one ordinary component
  preserves validity, and a trailing separator or a `.`/`..` component never
  does;
- the documented error priority for invalid paths: `read`, `list`, `metadata`,
  `create_file` and `remove_file` return `InvalidInput` before any limit check,
  clear their outputs, and make no native call.

No input reaches the filesystem. Valid paths are only classified, never opened,
listed or mutated, so the campaign needs no fixture and no privileges.

## What it does not cover

Filesystem I/O, the native adapter in `native/`, `Root`-relative operations,
retained handles, locks, rename, metadata decoding and every limit other than
the path grammar. Those keep their existing suites (`tests/api.goose`, the
dedicated per-feature tests and `make sanitize`). The campaign also does not
replace `tests/path_grammar.py`, which exhaustively compares the Python spec,
the native C helpers and optimized/debug Goose over all 0..7-byte strings from a
five-symbol alphabet plus 4094/4095/4096-byte boundaries. Fuzzing adds longer
inputs, the full byte range and coverage-guided mutation; it does not make the
exhaustive check redundant, and the exhaustive check does not make fuzzing
redundant.

## Bounds

`scripts/fuzz.py` refuses to exceed its declared bounds: at most 300 seconds and
at most 20000 inputs per campaign, with defaults of 30 seconds and 20000 inputs.
There is no soak mode and no host tuning. Each invocation writes a fresh
directory under `.build/fuzz/runs/<UTC stamp>-seed<seed>/` and refuses to reuse
an existing one, so an earlier attempt is never overwritten.

## Oracle and controls

- `tests/path_oracle.py` is an independent byte implementation of the rule in
  [API](API.md) and [Roots](ROOTS.md): 1..4095 bytes, no NUL, and no empty, `.`
  or `..` component, with `/` and `.` accepted as the whole path. It is not Rust
  `Path` normalization and shares no code with `fs.goose`. It replays the
  retained corpus and the declared seeds through a built `path_grammar` target
  and compares every verdict.
- The assertion-artifact self-test proves a failed Goose assertion reaches
  libFuzzer and saves the exact triggering bytes before the campaign starts.
- The coverage control runs the same instrumented binary on one empty input and
  requires strictly less target coverage than the campaign, so the counters are
  live rather than a static report.
- The mutation control copies the package, removes the `..` rejection from
  `valid_components`, and requires both the oracle replay and the in-process
  contract assertion to fail. A weakened guard that passes is a harness defect.

## Evidence

`summary.json` in the run directory records the source revision and dirty flag,
SHA256 of every campaign input file, the compiler executable hash and reported
version, the C compiler hash and version, the seed manifest, the completed run
count, the campaign and baseline coverage counters, per-function coverage of the
generated C, the replay and mutant-replay results, the saved artifacts and every
command with its exit code. Raw logs (`run.log`, `self-test.log`, `baseline.log`,
`replay.log`, `mutant-replay.log`, `mutant-run.log`) stay beside it.

The pinned compiler inlines `fs::valid_relative` into its callers, so the
generated C has no symbol for it; `summary.json` records that observation
instead of claiming per-function coverage that does not exist. Its verdicts are
covered by the differential replay.

## Limitations

A campaign that completes proves only that the retained corpus and the executed
mutations agreed with the oracle and the contract checks. It does not prove the
absence of defects, and the run count alone is not evidence. The corpus is
bounded by `MAX_INPUT_BYTES = 4096`, one byte past the 4095-byte path limit. The
generated C is compiled with `-fno-inline` so per-function coverage is
attributable; that is a test-only build flag. A reused writable corpus changes
mutation sequences, so two campaigns with the same seed are not byte-identical.
