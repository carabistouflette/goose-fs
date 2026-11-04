// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
extern fn lp_arm();
extern fn lp_disarm();
extern fn lp_configure(fail: bool);
extern fn lp_wait();
extern fn lp_release();
extern fn lp_calls() -> i64;
extern fn lp_permission_error() -> i64;
thread_fn waiter(file: fs::File) {
    lp_arm();
    let result = fs::lock_file(file, fs::LockMode.Exclusive);
    lp_disarm();
    assert(qput(result));
}
fn main() {
    let argv = args(); assert(argv.len == 2);
    let path = str(argv[1], "/pause-lock"); assert(fs::create_file(path, "").error == fs::Error.None);
    let owner, oe = fs::create_context(); assert(oe.error == fs::Error.None);
    let holder, he = fs::open_file(owner, path, fs::OpenOptions { .. }); assert(he.error == fs::Error.None);
    assert(fs::lock_file(holder, fs::LockMode.Exclusive).error == fs::Error.None);
    let pending, pe = fs::create_context(); assert(pe.error == fs::Error.None);
    let blocked, be = fs::open_file(pending, path, fs::OpenOptions { .. }); assert(be.error == fs::Error.None);
    lp_configure(true);
    let denied = thread_spawn(waiter, blocked); lp_wait();
    let failure = qget<fs::Status>();
    assert(failure.error == fs::Error.SystemError && failure.os_error == lp_permission_error());
    assert(thread_wait(denied) && lp_calls() == 1);
    lp_configure(false);
    let sleeping = thread_spawn(waiter, blocked); lp_wait();
    assert(lp_calls() == 1); // The actual wrapper is now inside its first pause.
    assert(fs::close_context(pending).error == fs::Error.None);
    lp_release();
    let closed = qget<fs::Status>(); assert(closed.error == fs::Error.SystemError && closed.os_error != 0);
    assert(thread_wait(sleeping) && lp_calls() == 1);
    assert(fs::close_context(owner).error == fs::Error.None);
    print("public lock wait propagates denied sleep and closes Context during an observed pause");
}
