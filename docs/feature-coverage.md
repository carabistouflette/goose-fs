# Linux feature coverage

The current interface targets 64-bit Linux. Full Linux filesystem coverage is the
first rollout stage; macOS and Windows follow after that stage is validated.
[The research inventory](comparison-research.md) pins the Rust, Go and Goose
versions used to define the target. This is a progress record, not a parity claim.

| Capability | Current goose-fs | Remaining Linux work |
| --- | --- | --- |
| Whole-file reads | Bounded regular-file reads; caller-owned replacement storage | General size/streaming choices through File handles |
| Directory enumeration | Unsorted and bytewise sorted owned names with kind hints | Streaming cursors; directory-relative access |
| Metadata and predicates | No-follow identity, type, size, mode, ownership, timestamps; optional birth time; error-preserving predicates | Handle-relative metadata; following-link variants with explicit policy |
| Creation and removal | Exclusive file/directory creation; unlink; empty-directory removal | Overwrite/append; rename; recursive operations |
| Retained File operations | Not implemented | Read/write, positioned I/O, seek, truncate, sync, explicit close and ownership |
| Root/directory capabilities | Not implemented | Relative traversal and operations through retained directories |
| Permissions and timestamps | Inspection only | Permission, ownership and time changes |
| Links and paths | Strict absolute byte paths; rejects parent symlinks | Hard/symbolic links, readlink, canonical and lexical path utilities |
| Copy and publication | Not implemented | File/selected/tree copy; atomic replacement/install; explicit durability outcomes |
| Temporary resources | Not implemented | Exclusive temporary file/directory creation and explicit cleanup |
| Advisory locks | Not implemented | Shared/exclusive, blocking/nonblocking and release |
| Platforms | 64-bit Linux | macOS and Windows backends, policy differences and CI |

The safety contract deliberately differs from ordinary std::fs/os calls: strict
absolute paths, no-follow parent traversal, bounded storage, regular-file reads
and clear-on-error outputs. Those restrictions must remain visible rather than
being presented as interchangeable native APIs. Broader APIs need equally explicit
lookup, partial-I/O, ownership and durability contracts.

The [four-implementation harness](../bench/compare/README.md) measures matching
read, sorted-listing and metadata tasks through each public native API. It rejects
stale binaries using build-time provenance, validates common fixtures and retains
all samples. It does not establish equal-security performance or full feature
parity. A separately labelled hardened-adapter comparison is still required.

Retained-resource design must address both normal return and contained worker
abort. The pinned Goose runtime does not expose a native lifecycle cleanup hook;
thread completion can become visible before TLS destructors finish. No retained
resource API is published until its ownership and cleanup behavior is validated.
