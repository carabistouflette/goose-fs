// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
extern fn set_mode(mode: i64) = "gf_test_link_mode";
extern fn calls() -> i64 = "gf_test_link_calls";
fn main() {
    let argv = args(); assert(argv.len == 2);
    let context, created = fs::create_context(); assert(created.error == fs::Error.None);
    let root, opened = fs::open_root(context, argv[1]); assert(opened.error == fs::Error.None);
    let path = str(argv[1], "/synthetic");
    for relative in [false, true] {
        for mode in 3 {
            set_mode(mode);
            var out: u8[>..] = []; out.append("sentinel");
            let result = if relative { fs::read_link_at(root, "synthetic", fs::MAX_BYTES, out) }
                         else { fs::read_link(path, fs::MAX_BYTES, out) };
            if mode == 0 { assert(result.error == fs::Error.LimitExceeded && result.os_error == 0 && out.len == 0 && calls() == 14); }
            else if mode == 1 { assert(result.error == fs::Error.None && out == "new" && calls() == 2); }
            else { assert(result.error == fs::Error.SystemError && result.os_error != 0 && out.len == 0 && calls() == 2); }
        }
    }
    assert(fs::close_context(context).error == fs::Error.None);
    print("public readlink MAX+1/14pass/replacement/later-error staging passed");
}
