# File locks on Linux

`lock_file(file, LockMode.Shared/Exclusive) -> Status` waits until acquired or an
error occurs. `try_lock_file(file, mode) -> (bool, Status)` attempts immediately:
contention alone returns `(false, success)`; stale handles, access errors, ENOLCK
and other OS errors remain errors. `unlock_file(file)` reports its own status.
Successful acquisition is not a lease against another worker closing the token.

These operations use [Linux flock](https://man7.org/linux/man-pages/man2/flock.2.html).
Locks belong to the open file description. Copies and duplicates share lock state;
any duplicate can unlock it. Repeated acquisition is not recursive ownership or a
per-worker mutex. Independent opens contend, including within one process.
Closing the last duplicate releases its lock; closing only one may leave it held.
Conversions between shared and exclusive modes are not atomic: a failed attempt
can lose the previous lock. Reacquire explicitly before relying on protection.

Local filesystem flock locks normally coordinate cooperating processes; they do
not authorize access. Remote filesystem behavior varies: NFS can require write
access for exclusive locking, and SMB can impose mandatory I/O restrictions.
Paths can be renamed/unlinked/replaced while locked; locking an old inode does not
lock a replacement entry. Applications need a stable lock-file convention.

Each native acquisition attempt uses LOCK_NB, retrying EINTR, with token validation and the
existing Context/entry locks. The blocking Goose wrapper makes its first attempt
immediately, then requests a 1 ms pause between contentions. It releases all
native registry locks before each pause and revalidates tokens on every attempt.
An interrupted pause resumes its remainder; other sleep errors stop the wait with
SystemError rather than retrying without delay.
Context closure can therefore invalidate a waiter without waiting for it to
acquire a contended lock; the next attempt returns EBADF. ContextClose may return
while the waiter is sleeping, with no retained native waiter resource left behind.
An acquired lock can survive a contained worker abort until its parent closes the
owning Context; see [resource ownership](HANDLES.md).

The pause is not a latency bound. Scheduler delays, roughly 1000 failed attempts
per second per waiter, contention herding and starvation are possible. No fairness,
deadline or cancellation of a kernel/remote-filesystem call is promised. This
covers the acquire/try/shared/unlock capabilities of
[Rust File locking](https://doc.rust-lang.org/std/fs/struct.File.html#method.lock),
with a different waiting strategy. Polling contention and concurrent I/O require
separate measurements before performance claims. The inspected Go os and Goose
stdlib have no portable File locking API; platform adapters are separate work.
