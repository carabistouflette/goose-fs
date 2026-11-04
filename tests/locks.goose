// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn ok(result: fs::Status) { assert(result.error == fs::Error.None && result.os_error == 0); }
fn acquired(file: fs::File, mode: fs::LockMode, expected: bool) {
    let yes, result = fs::try_lock_file(file, mode); ok(result); assert(yes == expected);
}
thread_fn waiter(file: fs::File) {
    let yes, result = fs::try_lock_file(file, fs::LockMode.Exclusive);
    assert(!yes && result.error == fs::Error.None);
    assert(qput(true));
    let final = fs::lock_file(file, fs::LockMode.Exclusive);
    assert(qput(final));
}
thread_fn abort_locked(context: fs::Context, path: u8[4095], length: i64) {
    let file, opened = fs::open_file(context, path[..length], fs::OpenOptions { .. }); ok(opened);
    ok(fs::lock_file(file, fs::LockMode.Exclusive));
    assert(qput(file));
    assert(false); // Parent owns the Context and must release this acquired lock.
}
fn main() {
    let argv = args(); assert(argv.len == 2);
    let path = str(argv[1], "/lock-file"); ok(fs::create_file(path, "data"));
    let owner, oe = fs::create_context(); ok(oe);
    let one, a = fs::open_file(owner, path, fs::OpenOptions { .. }); ok(a);
    let two, b = fs::open_file(owner, path, fs::OpenOptions { .. }); ok(b);
    acquired(one, fs::LockMode.Shared, true); acquired(two, fs::LockMode.Shared, true);
    acquired(one, fs::LockMode.Exclusive, false);
    // Failed conversion does not promise retention of the previous shared lock.
    ok(fs::lock_file(one, fs::LockMode.Shared)); ok(fs::unlock_file(two));
    acquired(two, fs::LockMode.Exclusive, false);
    ok(fs::unlock_file(one)); acquired(two, fs::LockMode.Exclusive, true);
    let duplicate, de = fs::duplicate_file(two); ok(de);
    acquired(duplicate, fs::LockMode.Exclusive, true); // Same OFD, not recursive ownership.
    ok(fs::unlock_file(duplicate)); acquired(one, fs::LockMode.Exclusive, true);
    ok(fs::unlock_file(one)); ok(fs::close_file(duplicate));
    ok(fs::lock_file(one, fs::LockMode.Exclusive));
    let pending, pe = fs::create_context(); ok(pe);
    let blocked, be = fs::open_file(pending, path, fs::OpenOptions { .. }); ok(be);
    let waiting = thread_spawn(waiter, blocked); assert(qget<bool>());
    ok(fs::close_context(pending));
    let cancelled = qget<fs::Status>(); assert(cancelled.error == fs::Error.SystemError && cancelled.os_error != 0);
    assert(thread_wait(waiting));
    let pending_again, pae = fs::create_context(); ok(pae);
    let blocked_again, bae = fs::open_file(pending_again, path, fs::OpenOptions { .. }); ok(bae);
    let waiting_again = thread_spawn(waiter, blocked_again); assert(qget<bool>());
    ok(fs::unlock_file(one));
    let success = qget<fs::Status>(); ok(success); assert(thread_wait(waiting_again));
    ok(fs::close_context(pending_again));
    let aborted_owner, aoe = fs::create_context(); ok(aoe);
    var fixed: u8[4095] = [0; 4095]; for c, i in path { fixed[i] = c; }
    let aborted = thread_spawn_contained(abort_locked, aborted_owner, fixed, path.len);
    let escaped = qget<fs::File>(); assert(!thread_wait(aborted));
    acquired(one, fs::LockMode.Exclusive, false);
    ok(fs::close_context(aborted_owner));
    acquired(one, fs::LockMode.Exclusive, true); ok(fs::unlock_file(one));
    assert(fs::unlock_file(escaped).error == fs::Error.SystemError);
    ok(fs::close_context(owner));
    let stale, stale_error = fs::try_lock_file(one, fs::LockMode.Exclusive);
    assert(!stale && stale_error.error == fs::Error.SystemError);
    print("shared/exclusive/duplicate locks, polling cancellation and abort cleanup passed");
}
