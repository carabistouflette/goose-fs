# Interface contract

Experimental 64-bit Linux interface; byte-oriented paths and contents. No release yet.

The absolute-path APIs require paths of at most 4095 bytes, with no NUL, empty, `.` or `..`
components, and no trailing slash. `/` is accepted by read/list/metadata and predicates (read reports
NotRegular under ordinary accessible-root permissions). Component size limits are enforced by the OS. Invalid UTF-8 is allowed.
Those paths start with `/`. [Root methods](ROOTS.md) instead accept strict relative
arguments, with their own root-self and lifecycle rules.
Parent directories are resolved with Linux openat2 RESOLVE_NO_SYMLINKS. If the
syscall returns ENOSYS (older kernel) or EPERM (including seccomp denial), a
component-by-component O_NOFOLLOW/O_DIRECTORY descriptor walk enforces the same
policy. EPERM is retried by that walker; its final result/errno is returned.
Other lookup failures are propagated without retry. Reads/listing reject final symlinks too. No process
cwd/umask changes. One-shot operations retain no native pointers or descriptors;
[retained Files](HANDLES.md) use a synchronized registry with explicit Context ownership.

This is a path-resolution policy, not confinement: hard links, mount points and
concurrent renames are possible. Operations use the directories they opened even
if those directories are subsequently moved. Paths may change during traversal.
Final read targets are opened before fstat rejects nonregular types; device-open
callbacks can run even when a read is rejected. Ordinary filesystem I/O may block indefinitely; there is no deadline guarantee.

- `read(path, limit, out)`: require a regular file, replace out with its bytes.
  Accept zero limit for an empty file. Inspect up to limit+1 bytes, independent
  of stat size; files may change while reading, so this is not a snapshot.
- `list(path, byte_limit, entry_limit, out)`: replace out with owned Entry values.
  Skip `.`/`..`; unspecified filesystem order. Name bytes are preserved, including
  newlines and invalid UTF-8. Kind is a readdir hint and may be Unknown or stale.
  byte_limit counts name bytes plus two bytes per entry (kind and delimiter).
  This is not a directory snapshot; changes may produce omissions/repetitions.
- `create_file(path, data)`: exclusively create mode 0600 (umask may reduce it),
  write data, close. Existing entries, including dangling symlinks, fail. A write
  or close failure can leave a partial file; no rollback, atomic publication or
  durability guarantee. No fsync; success reports writes/close accepted by the OS.
- `create_dir(path)`: exclusively create mode 0700, subject to umask.
- `remove_file(path)`: unlink a non-directory entry, including a final symlink,
  without following it. No identity check/use promise under concurrent replacement.
- `remove_empty_dir(path)`: remove an empty directory, never recursively.

- `metadata(path, out)`: inspect the final entry without following it. Replace
  fixed-size Metadata on success and reset every field to its default on error.
  File type is authoritative at lookup time; the result is not a later-use
  identity guarantee. Kind distinguishes regular file, directory, symlink, FIFO,
  socket, character/block device and other. Device/inode/link identities and
  size are u64; size is meaningful for regular files and varies for other types.
  Permissions contain Linux mode bits `07777`; uid/gid are numeric IDs.
  accessed/modified/changed/created timestamps contain signed seconds since the
  Unix epoch and nanoseconds in 0..999999999. changed is inode status-change time,
  not birth time. created is valid only when created_available is true.
  statx supplies birth time where supported; missing/denied statx or incomplete
  basic data uses fstatat with birth unavailable. Native bits preserve u64 fields.
- `exists(path)` / `is_dir(path)`: return `(bool, Status)` using final-entry
  metadata. Only ENOENT becomes false/success. Permission errors, ENOTDIR and
  invalid paths remain errors. A dangling symlink exists; a symlink to a directory
  is not itself a directory. These are no-follow entry predicates, unlike ordinary
  link-following Rust/Go stat predicates.
- `list_sorted(path, byte_limit, entry_limit, out)`: same complete-result/failure
  contract and byte budget as list, with unsigned-byte lexicographic ordering.
  Empty/prefix/non-UTF-8 names use byte order without locale conversion.

Status has Error {None, InvalidInput, LimitExceeded, NotRegular, SystemError}
and os_error (errno only for SystemError; zero otherwise). Read/list clear output
on every error, including invalid input. No error embeds path or content bytes.
Inputs must not borrow output storage, which Goose checks. Owned names survive
later calls. Allocation failure follows Goose runtime behavior, not Status.

Limits are fixed: 1 MiB read/write/list payload, 4096 listing entries, 4095 path
bytes. Public buffers may retain high-water capacity. Read uses caller storage;
list additionally stages at most byte_limit bytes, then copies names into owned
entries. Listing starts with min(byte_limit, 64 KiB) of initialized staging.
If it fills, native code stops writing but counts to EOF within the caller's
byte/entry limits. After closing every temporary descriptor and releasing Root
locks, Goose grows to at least the required size and retries. A stable directory
needs at most two complete passes. Under changes, growth at least doubles,
bounded to five attempts with a 1 MiB budget; the final successful pass supplies
all published entries. Retries may observe different names or directory identity
and provide no snapshot guarantee. Limit and OS/cleanup errors stop immediately.
Work is linear in path bytes and payload/entries inspected across these passes,
except OS costs and repeated EINTR. Sorted listing instead adds O(entries × log(entries))
byte-name comparisons (each bounded by the longer compared name), an array of
entry references, and a second owned-name copy while unsorted names remain live.
Its temporary memory includes those extra names and references; callers may retain
high-water capacity.  Readdir's internal libc buffering is outside that bound.
The private C ABI is not a supported public API.

Read reuses an initialized output prefix rather than zeroing it again; growth
is still initialized. Small files with oversized limits continue paying for
that growth after each result is shrunk.
