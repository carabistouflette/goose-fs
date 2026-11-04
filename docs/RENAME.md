# Rename outcomes

`rename(from, to, RenameOptions)` accepts two strict absolute byte paths.
`rename_at(root, from, to, RenameOptions)` accepts two paths relative to one Root.
Both return RenameResult. Root/self mutations are rejected; ordinary path limits
and no-follow parent traversal apply to both operands. Cross-Root operands are
not yet supported. Final entries are renamed themselves, including symlinks.

RenameOptions contains policy (Replace by default, or NoReplace) and sync_parents
(false by default). Replace invokes renameat. NoReplace invokes
renameat2(RENAME_NOREPLACE); unsupported kernels/filesystems return their error.
There is no check-then-rename fallback, copying fallback, or rename retry,
including after EINTR.

| RenameResult field | Meaning |
| --- | --- |
| status | None, InvalidInput or SystemError; os_error retains the first primary errno |
| outcome | NotAttempted, Applied or Unknown, as defined below |
| parents_synced | Both requested parent fsync calls returned success |
| cleanup_os_error | First descriptor-close errno, or zero |

NotAttempted means no rename syscall was issued. Applied means the syscall
returned success, including successful same-path or same-inode no-ops; it does
not imply the source name disappeared. Unknown means a rename syscall was
attempted and returned an error. An NFS server can apply a rename before the
client receives an error. Do not infer absence of mutation from status alone or
automatically roll back/retry an Unknown result. These namespace rules follow
[Linux rename semantics](https://man7.org/linux/man-pages/man2/rename.2.html).

The operation moves the entry found at lookup time. It does not pin a previously
inspected source inode, transfer a File lock, or protect names against other
writers. Held Files and child Roots remain tied to their original objects after
a move or replacement. No snapshot, tree confinement, source-content validation,
or multi-operation transaction is provided.

## Parent synchronization and errors

With sync_parents=false, the operation requests no synchronization. With true,
it first opens readable directory descriptors for both resolved parents, before
attempting the rename. This requires additional directory read permission and
FD capacity beyond ordinary rename. A failure at that stage is NotAttempted.

After Applied, both parents are fsynced even if the first fails; EINTR is retried
for fsync only. The first sync error becomes status.os_error, while outcome stays
Applied. parents_synced is true only if both calls succeeded, and remains true
if a later close fails. Both requests are made even when the parents identify the
same directory. This synchronizes parent directories, not the source file's data;
callers needing that must sync the file separately before renaming it.
[Directory and file synchronization are distinct](https://www.man7.org/linux/man-pages/man2/fsync.2.html).
The flag records accepted sync requests, not a universal hardware or filesystem
persistence guarantee.

Every temporary descriptor owned by the operation is closed once. This includes intermediate descriptors in
fallback traversal, final parent descriptors and readable sync descriptors. An
intermediate close failure stops traversal before mutation; a failed next-open
keeps precedence over a close error. cleanup_os_error independently retains the
first close error. If there was no earlier error, a close failure sets SystemError.
Late cleanup never changes Applied/parents_synced and never triggers rollback.
Linux close is not retried because its descriptor number may already have been
reused. See [Linux close semantics](https://man7.org/linux/man-pages/man2/close.2.html).

The Root operation holds its Context/Root read locks only inside native code,
through final cleanup. Closing that Root or Context waits for the call. No operation-owned temporary
FD, held lock, borrowed path pointer or allocation survives return to Goose. Existing
[Context ownership and worker restrictions](HANDLES.md) apply. I/O and repeated
interruptions have no deadline. Allocation failure follows the Goose runtime.

This primitive renames existing entries. It does not implement byte publication,
installation, temporary-file management, selected copying or durable unlink.
