// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn error_name(error: fs::Error) -> const u8[:] {
    return if error == fs::Error.InvalidInput { "invalid input" }
           else if error == fs::Error.LimitExceeded { "limit exceeded" }
           else if error == fs::Error.NotRegular { "not a regular file" }
           else { "OS error" };
}
fn main() {
    let argv = args();
    if argv.len != 2 { print("usage: stream ABSOLUTE_PATH"); return; }
    let context, created = fs::create_context();
    if created.error != fs::Error.None { print("context failed: ", error_name(created.error)); return; }
    defer fs::close_context(context);
    let file, opened = fs::open_file(context, argv[1], fs::OpenOptions { .. });
    if opened.error != fs::Error.None { print("open failed: ", error_name(opened.error), "; errno ", opened.os_error); return; }
    var bytes: u8[>..] = []; var count: i64 = 0;
    while true {
        let result = fs::read_some(file, 65536, bytes);
        if result.status.error != fs::Error.None { print("read failed: ", error_name(result.status.error), "; errno ", result.status.os_error); return; }
        count += result.bytes;
        if result.eof { break; }
    }
    let closed = fs::close_file(file);
    if closed.error != fs::Error.None { print("close failed: ", error_name(closed.error), "; errno ", closed.os_error); return; }
    print("read ", count, " bytes in bounded chunks");
}
