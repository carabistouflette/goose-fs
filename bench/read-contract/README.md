# Preregistered bounded-read contract (Linux x86-64)

This profile compares goose-fs `read` against independently implemented Rust and
Go + Linux adapters. It is not a Rust std::fs or Go os native-API guarantee, a
sandbox, or proof of security equivalence outside the tested contract. It adds
no runtime/library API or native variant. No shared C implementation is timed in
place of the Rust/Go adapters. The pinned toolchains and actual source bytes,
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

Primary cells: reused-output successful reads of 0,64,4096,65536,1048576 bytes
with exact budgets, plus 64-byte input with 1MiB budget. Secondary cells cover
missing, overflow, zero-budget overflow, nonregular and deep-parent inputs.
Every cell includes validation, lookup, allocation/growth, reads, closes, status
checks and checksum work; fixture setup, independent preflight and printing are
outside timers. All languages use identical fixtures and filesystem byte paths.

Two complete independently built records are required for a per-cell performance
lead label. Every same-language replica median ratio in that cell must stay within
0.95..1.05 in both records, and every FS/reference cross-replica median ratio must
be at least 1.10. A primary regression beyond 5% in any cross-replica comparison
vetoes an overall primary-suite leadership label. A failed control or conflicting
record makes that cell inconclusive. These are preregistered operational decision
rules, not a confidence interval, noise bound or causal proof. No universal SOTA
or general language/library security ranking follows. There is no runtime change
being accepted/rejected in this profile. Raw per-replica results remain separate;
no pooling, correction or favorable-replica selection.

Sources: [openat2](https://man7.org/linux/man-pages/man2/openat2.2.html),
[Linux close](https://man7.org/linux/man-pages/man2/close.2.html),
[Rust OwnedFd](https://doc.rust-lang.org/std/os/fd/struct.OwnedFd.html),
[Go syscall](https://pkg.go.dev/syscall).
