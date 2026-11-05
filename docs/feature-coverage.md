# Linux feature coverage

The current interface targets 64-bit Linux. Full Linux filesystem coverage is the
first rollout stage; macOS and Windows follow after that stage is validated.
[The research inventory](comparison-research.md) pins the Rust, Go and Goose
versions used to define the target. This is a progress record, not a parity claim.

| Capability | Current goose-fs | Remaining Linux work |
| --- | --- | --- |
| Whole-file reads | Bounded regular-file reads; caller-owned replacement storage; File streaming for larger inputs | Unbounded convenience calls are outside the current bounded API |
| Directory enumeration | Unsorted and bytewise sorted owned names with kind hints, Root-relative calls and opt-in adaptive staging | Streaming cursors |
| Metadata and predicates | No-follow identity, type, size, mode, ownership, timestamps; optional birth time; error-preserving predicates; held-File/Root and relative metadata | Following-link variants with explicit policy |
| Creation and removal | Exclusive file/directory creation; File create/overwrite/append modes; unlink; empty-directory removal; entry rename | Recursive operations; one-shot overwrite/append helpers |
| Retained File operations | Explicit Context ownership; bounded read/write and positioned I/O; independent duplication; seek/truncate/sync/close and metadata | Streaming directory cursors and wider ecosystem adapters |
| Root/directory capabilities | Strict no-follow Root/child Root ownership; relative File/metadata/read/readlink/list/create/remove operations | Following permitted symlinks; relative links/metadata mutations; streaming directory cursors |
| Permissions and timestamps | Inspection plus held-File permissions, numeric ownership and independent Keep/Now/Exact atime/mtime setters | Path/Root/directory mutations |
| Links and paths | Strict absolute or Root-relative byte paths; bounded verbatim read_link/read_link_at; rejects parent symlinks | Hard/symbolic link creation, canonical and lexical path utilities |
| Copy and publication | Atomic entry replace/no-replace rename with explicit outcomes and optional checked parent sync | File/selected/tree copy; staged byte publication/installation; durable unlink |
| Temporary resources | Not implemented | Exclusive temporary file/directory creation and explicit cleanup |
| Advisory locks | Shared/exclusive try and polling wait; explicit unlock; duplicate/Context lifetime rules | Contention/fairness measurements and other platform backends |
| Platforms | 64-bit Linux | macOS and Windows backends, policy differences and CI |

The safety contract deliberately differs from ordinary std::fs/os calls: strict
absolute or Root-relative paths, no-follow parent traversal, bounded storage, regular-file reads
and clear-on-error outputs. Those restrictions must remain visible rather than
being presented as interchangeable native APIs. Broader APIs need equally explicit
lookup, partial-I/O, ownership and durability contracts.

The [four-implementation harness](../bench/compare/README.md) measures matching
read, sorted-listing and metadata tasks through each public native API. It rejects
stale binaries using build-time provenance, validates common fixtures and retains
all samples. It does not establish equal-security performance or full feature
parity. A separately labelled hardened-adapter comparison is still required.

Retained-resource ownership addresses both normal return and parent-owned cleanup after contained worker
abort. The pinned Goose runtime does not expose a native lifecycle cleanup hook;
thread completion can become visible before TLS destructors finish. The [File contract](HANDLES.md) requires a surviving owner to close the Context;
resources created without such an owner cannot be reclaimed automatically after abort.
