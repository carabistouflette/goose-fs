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
    if argv.len != 2 { print("usage: read ABSOLUTE_PATH"); return; }
    var content: u8[>..] = [];
    let result = fs::read(argv[1], 65536, content);
    if result.error == fs::Error.None { print("read ", content.len, " bytes"); }
    else { print("read failed: ", error_name(result.error), "; errno ", result.os_error); }
}
