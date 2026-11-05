# Directory-relative operations

`Root` retains a directory descriptor in a Context. Relative operations use that
directory's identity after it is renamed; they never change process cwd or
concatenate its original absolute name. This is a strict no-follow interface,
not a confinement or sandbox promise. It differs from Go Root, which can follow
permitted in-tree symlinks. See [comparison coverage](feature-coverage.md).

| Function | Behavior |
| --- | --- |
| `open_root(context, absolute_path)` | Return `(Root, Status)` for an existing directory |
| `open_root_at(root, relative_path)` | Open an independently closable child Root in the same Context |
| `open_file_at(root, relative_path, options)` | Open a regular File with the existing OpenOptions contract |
| `root_metadata(root, out)` | Inspect the held directory directly, without pathname lookup |
| `metadata_at(root, relative_path, out)` | Inspect the final entry without following it |
| `read_link_at(root, path, limit, out)` | [Bounded final-symlink target bytes](READ-LINK.md); never resolves the target |
| `read_file_at(root, relative_path, limit, out)` | Bounded whole-file read, including overflow probe |
| `list_at`, `list_sorted_at` | Same limits/owned Entry format as list/list_sorted |
| `rename_at(root, from, to, options)` | Two operands under one Root; [explicit outcomes and parent sync](RENAME.md) |
| `create_file_at`, `create_dir_at` | Exclusive creation, modes 0600/0700 before umask |
| `remove_file_at`, `remove_empty_dir_at` | Unlink a non-directory entry or remove an empty directory |
| `close_root(root)` | Close this Root, invalidating copied aliases |

All argument orders follow their absolute counterparts after the leading Root.
Root/File outputs are zero on failed open; byte/list/metadata outputs are cleared
on errors. Paths and names are bytes, including invalid UTF-8 and newlines.

Relative paths are 1..4095 bytes. Reject absolute paths, NUL, empty/repeated or
trailing separators, and any `.`/`..` component. Exactly `.` is accepted for
root-self inspection/listing, readonly-existing File open and child-Root open.
Reading/opening that directory normally reports NotRegular after open/fstat, but
can instead report an OS access error before type inspection. Explicit mutations
and any write/create/append/truncate File options with `.` return InvalidInput
before filesystem effects. Root metadata uses the held descriptor directly;
`metadata_at(root,".")` still performs a relative lookup and can have different
access requirements. Original absolute and relative path limits are independent.
Chaining child Roots permits traversal whose cumulative pathname exceeds 4095 bytes.

Every ancestor is resolved through the held Root with no symlinks. Nested parents
use openat2 with RESOLVE_BENEATH|RESOLVE_NO_SYMLINKS and O_PATH/O_DIRECTORY/CLOEXEC.
Only ENOSYS/EPERM falls back to a duplicated-root descriptor walk with
O_PATH/O_DIRECTORY/O_NOFOLLOW/CLOEXEC. Other lookup failures are returned unchanged.
A simple leaf duplicates the Root descriptor. Parent descriptors are always owned
and closed by that call. Final metadata can inspect a symlink, and remove_file_at
can unlink it; read/list/open reject final links. Listings open a fresh readable
directory descriptor, giving repeated/concurrent calls independent cursors.

No native pointers into Goose storage or original pathnames are retained. A Root
is a copied token like File: aliases share lifetime; child Roots and Files own
independent descriptors and survive closing their parent Root. ContextClose owns
and invalidates all of them. Native kind checks prevent File methods from closing
or using Root tokens and vice versa. Capacity is a combined 4096 retained resources
per loaded process registry (`MAX_RESOURCES`); `MAX_FILES` is an upper-bound alias,
not an additional allowance. Open reserves a slot before create/truncate effects.
One-shot relative operations require no new retained slot and can remain usable
when the table is full, subject to ordinary kernel descriptor/memory limits.

Relative native operations hold Context R and the anchor Root's entry R through completion.
New File/Root allocation uses the same free-target-slot exception as duplication;
no registry allocator lock is held while waiting for a target lock. Closing a Root
or Context waits for native calls using it. Parent-owned abnormal-exit cleanup and
cross-worker rules are in [HANDLES.md](HANDLES.md). I/O has no deadline.

The descriptor walk, hard links, mounts and concurrent directory moves do not give
a stable tree, snapshot or containment guarantee. A call can operate on a directory
that has moved after being opened. Root-relative operations do not prevent other
processes from modifying entries. Kernel openat2 and fallback paths share the
no-follow policy, but this API makes no stronger concurrent-rename confinement
claim. Failed creation can leave a partial new entry; there is no rollback or
implicit durability. Device-open callbacks can occur before regular-file checks.
Directory duplication adds syscalls; relative-call speed requires measurements.
