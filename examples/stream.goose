// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn main() {
    let argv = args(); assert(argv.len == 2);
    let context, created = fs::create_context(); assert(created.error == fs::Error.None);
    defer fs::close_context(context);
    let file, opened = fs::open_file(context, argv[1], fs::OpenOptions { .. });
    assert(opened.error == fs::Error.None);
    var bytes: u8[>..] = []; var count: i64 = 0;
    while true {
        let result = fs::read_some(file, 65536, bytes);
        assert(result.status.error == fs::Error.None);
        count += result.bytes;
        if result.eof { break; }
    }
    assert(fs::close_file(file).error == fs::Error.None);
    print("read ", count, " bytes in bounded chunks");
}
