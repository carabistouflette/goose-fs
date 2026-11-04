// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
thread_fn reader(root: fs::Root) {
    var out: u8[>..] = []; var entries: fs::Entry[>..] = [];
    for _ in 100 {
        assert(fs::read_file_at(root, "file", 5, out).error == fs::Error.None && out == "bytes");
        assert(fs::list_at(root, ".", 64, 1, entries).error == fs::Error.None && entries.len == 1);
    }
}
fn main() {
    let argv = args(); assert(argv.len == 2);
    let context, created = fs::create_context(); assert(created.error == fs::Error.None);
    let root, opened = fs::open_root(context, argv[1]); assert(opened.error == fs::Error.None);
    assert(fs::create_file_at(root, "file", "bytes").error == fs::Error.None);
    var ids: i64[>..] = [];
    for _ in 4 { ids.push(thread_spawn(reader, root)); }
    for id in ids { assert(thread_wait(id)); }
    assert(fs::close_context(context).error == fs::Error.None);
    print("cross-worker rooted reads and independent directory cursors passed");
}
