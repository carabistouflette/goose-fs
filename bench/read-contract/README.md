# Preregistered bounded-read contract (Linux x86-64)

Historical experiment protocol. It describes the recorded revision, not current
main or an ongoing run. [Results](../results/2026-11-05-read-contract/README.md) retain the outcome.
For reproduction, use a separate checkout first:

```sh
git checkout --detach dee8b163244dfa62eea7016835e9d40a70920342
```

Then follow the protocol below in that checkout. Do not run its old commands on
main and describe the result as the original experiment. For current costs see
[performance scope](../../docs/PERFORMANCE.md).

This profile compares goose-fs `read` against independently implemented Rust and
Go + Linux adapters. It is not a Rust std::fs or Go os native-API guarantee, a
sandbox, or proof of security equivalence outside the tested contract. It adds
no runtime/library API or native variant. The Rust + Linux adapter uses a narrow
C stat ABI bridge (one fstat, immediately captured errno and mode output only on
success); all traversal, ownership and read policy remain independently Rust.
The bridge compiler, flags, bytes and cost are included. No shared C policy
implementation is timed in place of the Rust/Go adapters. The pinned toolchains and actual source bytes,
flags, stdlib, executable hashes and settings must be bound before timing.

## Shared contract

- Absolute byte paths, 1..4095 bytes, no NUL, empty/dot/dotdot components or
  trailing slash; root `/` accepted. No Unicode conversion or normalization.
- Parent lookup uses openat2 RESOLVE_NO_SYMLINKS with O_PATH/O_DIRECTORY/CLOEXEC.
  Only ENOSYS/EPERM fall back to a component walk using O_PATH/DIRECTORY/NOFOLLOW/
  CLOEXEC. Intermediate close failure stops walking; failed next-open error
  precedes old-parent close error. All consumed closes are attempted once.
- Final open uses RDONLY/NOFOLLOW/NONBLOCK/NOCTTY/CLOEXEC; fstat-equivalent regular
  file check precedes reads. Do not reject by advertised size. Device open effects
  before classification, mount traversal and rename races remain possible.
- Limit 0..1MiB; read at most limit plus one overflow-probe byte. Unbuffered short
  reads loop; EINTR retries reads only. Zero limits still open/check/probe.
- Replace caller output on success; clear logical output on every error. Preserve
  primary errno; distinguish Invalid/Limit/NotRegular/System. Checked final-file
  close failure becomes System only without prior error, and that fd is consumed.
- Parent-only cleanup close is best-effort, matching the existing goose-fs read
  implementation. It is not a promise that every cleanup error is surfaced.
  This limitation is explicit; no silent strengthening in adapters or native edit.
- Caller output is reused; zero newly grown logical bytes before OS reads, as in
  Goose resize(limit,0). Clear does not promise capacity erasure. No extra read
  buffering, retained fd, filesystem snapshot, implicit sync or I/O deadline.
- Callers supply path storage separate from mutable output and no concurrent
  mutation of either. Rust borrows, safe Go string inputs and Goose borrow rules
  differ; arbitrary unsafe/native pointer abuse is outside this common domain.

## Decision rules fixed before timing

Eligibility requires all conformance cases and applicable fault tests to pass,
full filename/content/errno checks outside timers, bounded-read syscall policy,
no fd leaks, frozen clean source/toolchains, and independent same-language replica
builds with identical complete ELF and text/rodata bytes. Failure means no eligible
measurement, not a faster result. Keep every observation and failed eligibility
record. No old data is overwritten or normalized.

The fixed recording schedule is five shuffled rounds, seven in-process means
per invocation, 200 read calls per mean, six labels (two builds per language),
and all eleven cells. Two attempts yield 4620 raw means if both complete.
Creation and process-order seeds are fixed separately; all processes run
sequentially pinned to CPU6 on this shared host, without isolation claims.

Primary cells: reused-output successful reads of 0,64,4096,65536,1048576 bytes
with exact budgets, plus 64-byte input with 1MiB budget. Secondary cells cover
missing, overflow, zero-budget overflow, nonregular and deep-parent inputs.
The initial buffer warmup/allocation is outside timers; any subsequent logical
growth/zeroing remains inside. Every cell includes validation, lookup, reads, closes, status
checks and checksum work; fixture setup, independent preflight and printing are
outside timers. All languages use identical fixtures and filesystem byte paths.

Only the first two measured attempts at a frozen checkpoint are used for labels.
An incomplete attempt, failed eligibility or failed control is retained and makes
that checkpoint inconclusive; there is no replacement run. Fixing a harness bug
requires a new preregistered checkpoint while preserving all prior records.

A per-cell FS lead requires, in BOTH records: for EACH of all three languages,
max(replica median ns)/min(replica median ns)<=1.05; and EVERY reference-replica
median / EVERY FS-replica median >=1.10, against both references. All three
languages' controls are required even for a pairwise label. A primary descriptive
regression flag means FS median/reference median>1.05 in any replica comparison;
it is not a causal assertion. No overall suite-leadership label is assigned by
this profile. A failed or conflicting condition yields inconclusive, never a
correction factor. These are operational rules, not confidence intervals or noise
bounds. No universal SOTA or general security ranking follows. There is no runtime
change being accepted/rejected. No pooling or favorable-replica selection.

Mandatory fault matrix, through the actual public read/adapter entry points:
short reads; one EINTR then success; EIO after partial progress; fstat EIO and
misleading small/large advertised sizes; ENOSYS/EPERM parent fallback; intermediate
close failure with successful/failed next open; final-file close EIO/EINTR after
successful consumption and with a prior read error or limit failure; ignored
parent-only close error; and exact FD reuse after consumed close, proving no
retry/destructor double-close. Test instrumentation must be separate from timed
builds, and injection counters must prove each intended boundary was reached.

Sources: [openat2](https://man7.org/linux/man-pages/man2/openat2.2.html),
[Linux close](https://man7.org/linux/man-pages/man2/close.2.html),
[Rust OwnedFd](https://doc.rust-lang.org/std/os/fd/struct.OwnedFd.html),
[Go syscall](https://pkg.go.dev/syscall).

## Native APIs and scope

The pinned Goose `os::read_file` appends the whole file, returns a boolean and
has no read budget or no-follow option. Rust `std::fs::read` and Go `os.ReadFile`
also do not supply this complete contract on their own. Their native-API results
remain in the separate [comparison](../compare/README.md); they cannot qualify
as references here by silently dropping safety checks. This profile measures
FS against the explicit independent Linux adapters above, including their added
validation, traversal and checked cleanup costs. It does not establish general
Rust/Go feature parity, portability, throughput for streaming handles, cold-cache
I/O, durability, memory leadership or broad state-of-the-art performance.

## Reproduction

Requires the repository's pinned Goose compiler, Linux x86-64, GCC (or Clang),
GNU objcopy, Python without optimization, Rust 1.99.1 and Go 1.27.3. No dependency
is downloaded by these scripts; build both language toolchains separately.

```sh
python3 tests/read_contract.py
taskset -c 6 python3 bench/read-contract/build.py --goose /absolute/path/to/goose
python3 tests/read_contract.py --build-dir .build/read-contract
# Run only after the recorder and source have been independently reviewed/frozen.
taskset -c 6 python3 bench/read-contract/measure.py --attempt 1
taskset -c 6 python3 bench/read-contract/measure.py --attempt 2
python3 bench/read-contract/analyze.py .build/read-contract/attempt-1.json .build/read-contract/attempt-2.json
```

The builder resets one private source/cache/output path before each replica and
requires whole-ELF and text/rodata equality within each language. Fault builds use
the same adapter/public FS entry point with separately compiled instrumentation;
they are never timed. The recorder checks full byte contents, errno, bounded
consumption, descriptors and fault counters before and after recording. Each
completed process is flushed to an exclusively created JSONL attempt file before
parsing, so failures and interruptions leave evidence. A smoke run uses a separate
namespace and count-one schedule, is always ineligible, and cannot receive a
performance label. No output/caches/generated binaries belong in a source commit.
The build directory is exclusive-lock protected during recording. Its parent is
caller-controlled and must not be concurrently modified by another writer.

Rust/Go use zero-initialized 4096-byte stack path scratch; FS copies only its
validated path plus terminator into native scratch. This implementation cost is
included, and these adapters are not claimed to be the fastest possible Rust/Go
implementations. Dirty retained-capacity tests observe zero growth at the actual
read boundary, including previous logical lengths on either side of the file size.
The same frozen set of six independently built executables is used in both
recording attempts; controls are evaluated independently in each attempt.
