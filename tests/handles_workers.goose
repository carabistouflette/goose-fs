// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
thread_fn read_worker(file: fs::File) {
    var out: u8[>..] = [];
    for _ in 200 {
        let result = fs::read_at(file, 1, 3, out);
        assert(result.status.error == fs::Error.None && result.bytes == 3 && out == "bcd");
    }
}
thread_fn abort_worker(context: fs::Context, path: u8[4095], length: i64) {
    let file, status = fs::open_file(context, path[..length], fs::OpenOptions { .. });
    assert(status.error == fs::Error.None);
    assert(qput(file));
    assert(false); // Intentional contained abort after native open.
}
fn main() {
    let argv = args(); assert(argv.len == 2);
    let path = str(argv[1], "/worker-file");
    assert(fs::create_file(path, "abcdef").error == fs::Error.None);
    let context, cs = fs::create_context(); assert(cs.error == fs::Error.None);
    let file, fs = fs::open_file(context, path, fs::OpenOptions { .. }); assert(fs.error == fs::Error.None);
    var ids: i64[>..] = [];
    for _ in 4 { ids.push(thread_spawn(read_worker, file)); }
    for id in ids { assert(thread_wait(id)); }
    var fixed: u8[4095] = [0; 4095];
    for c, i in path { fixed[i] = c; }
    let aborted = thread_spawn_contained(abort_worker, context, fixed, path.len);
    let escaped = qget<fs::File>();
    assert(!thread_wait(aborted));
    var out: u8[>..] = [];
    assert(fs::read_at(escaped, 0, 6, out).status.error == fs::Error.None && out == "abcdef");
    assert(fs::close_context(context).error == fs::Error.None);
    assert(fs::read_some(escaped, 1, out).status.error == fs::Error.SystemError && out.len == 0);
    assert(fs::close_file(file).error == fs::Error.SystemError);
    print("cross-worker File access and parent-owned contained-abort cleanup passed");
}
