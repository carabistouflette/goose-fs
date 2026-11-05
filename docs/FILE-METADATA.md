# Held File metadata changes

`set_permissions(file, mode)`, `set_owner(file, uid, gid)` and
`set_times(file, accessed, modified)` return Status and operate on the existing
regular-file descriptor. They do not resolve a pathname again, including after
rename or unlink. A replacement at the old pathname remains a separate inode.
Hard links and duplicate handles see changes to the same original object.

These calls acquire a shared Context lock and that File entry's write lock, then invoke one
native mutation syscall. They create no descriptors, retained slots or operation-owned heap
allocations and do not move the file cursor or write content. A read-only-open
File may change metadata when the OS permits; access mode is not a substitute for
kernel permission checks. Closed, stale, wrong-context and wrong-kind tokens are
rejected even for requests that leave attributes unchanged. Other aliases with
independent entry locks and other processes can still interleave changes. Separate
calls do not form a transaction and have no I/O deadline.

## Permissions and ownership

mode is a u32 containing Linux bits in 0000..07777, including explicitly requested
set-ID/sticky bits; higher bits are InvalidInput. Unlike creation modes, this
request ignores umask. Kernel permission, group, ACL and filesystem rules still
apply and may clear requested bits even on success. The library does not restore
them automatically. See [Linux fchmod](https://www.man7.org/linux/man-pages/man2/fchmod.2.html).

uid and gid are signed i64 values: -1 leaves that ID unchanged; 0..4294967294 are
accepted numeric IDs. Other values are InvalidInput. The accepted width does not
promise that an ID is mapped or the caller has permission to assign it. Chown can
change ctime and clear privilege bits/file capabilities, including when ID values
are unchanged. Both -1 values still request the OS operation; this is not a
promise of a harmless no-op. See [Linux fchown](https://www.man7.org/linux/man-pages/man2/fchown.2.html).

## Access and modification time

TimeUpdate contains action (TimeAction.Keep by default, Now, or Exact) and value
(Timestamp, default zero). accessed and modified are independent:

- Keep maps to UTIME_OMIT and leaves that timestamp unchanged.
- Now maps to UTIME_NOW and requests the OS current time.
- Exact uses signed 64-bit Unix seconds and nanoseconds in 0..999999999.

value is ignored for Keep and Now, including otherwise invalid nanoseconds.
Invalid actions or Exact nanoseconds are rejected before mutation. No library
conversion through floating point, microseconds or 32-bit seconds occurs. Actual
range/precision and permission rules depend on the OS/filesystem; accepted values
may be rounded or constrained. Now/Now has different permission rules from exact
or mixed updates. Both Keep values still validate the File and invoke futimens;
Linux then skips ownership checks and timestamp changes. ctime/birth time are not
settable fields of this API. See [Linux futimens](https://www.man7.org/linux/man-pages/man2/utimensat.2.html).

## Failure and synchronization

The library does not retry these mutations, including after EINTR, or attempt
rollback. Status preserves the syscall error. An error does not establish that
metadata stayed unchanged, particularly with remote filesystems.

There is no implicit synchronization. Call sync_file(file, false) separately to
request full file metadata/data synchronization; data_only=true is not an explicit
request to flush every metadata change. Accepted sync requests remain subject to
filesystem and hardware guarantees.

These setters support regular File handles. Path, Root and directory-handle
metadata changes remain separate Linux coverage work; it does not claim full
Rust/Go feature parity or another platform backend.
