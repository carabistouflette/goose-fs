# Interface contract

Experimental Linux-only interface; byte-oriented paths and contents. No release yet.

All paths are absolute, at most 4095 bytes, with no NUL, empty, `.` or `..`
components, and no trailing slash. `/` is accepted only by read/list (read reports
NotRegular). Component size limits are enforced by the OS. Invalid UTF-8 is allowed.
Each directory component is opened relative to the preceding descriptor with
O_NOFOLLOW and O_DIRECTORY. Reads/listing reject final symlinks too. No process
cwd/umask changes, global mutable state, or retained descriptors.

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

Status has Error {None, InvalidInput, LimitExceeded, NotRegular, SystemError}
and os_error (errno only for SystemError; zero otherwise). Read/list clear output
on every error, including invalid input. No error embeds path or content bytes.
Inputs must not borrow output storage, which Goose checks. Owned names survive
later calls. Allocation failure follows Goose runtime behavior, not Status.

Limits are fixed: 1 MiB read/write/list payload, 4096 listing entries, 4095 path
bytes. Public buffers may retain high-water capacity. Read uses caller storage;
list additionally stages at most byte_limit bytes, then copies names into owned
entries. Work is linear in path bytes and payload/entries inspected, except OS
costs and repeated EINTR. Readdir's internal libc buffering is outside that bound.
The private C ABI is not a supported public API.
