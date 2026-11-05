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
    if argv.len != 2 { print("usage: root ABSOLUTE_DIRECTORY"); return; }
    let context, created = fs::create_context();
    if created.error != fs::Error.None { print("context failed: ", error_name(created.error), "; errno ", created.os_error); return; }
    defer fs::close_context(context);
    let root, opened = fs::open_root(context, argv[1]);
    if opened.error != fs::Error.None { print("root failed: ", error_name(opened.error), "; errno ", opened.os_error); return; }
    var entries: fs::Entry[>..] = [];
    let result = fs::list_sorted_at(root, ".", 65536, 1024, entries);
    if result.error == fs::Error.None { print("listed ", entries.len, " owned entries"); }
    else { print("listing failed: ", error_name(result.error), "; errno ", result.os_error); }
}
