// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn main() {
    let argv = args();
    if argv.len != 2 { print("usage: read ABSOLUTE_PATH"); return; }
    var content: u8[>..] = [];
    let result = fs::read(argv[1], 65536, content);
    if result.error == fs::Error.None { print("read ", content.len, " bytes"); }
    else { print("read failed; errno ", result.os_error); }
}
