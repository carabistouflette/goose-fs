// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn main() {
    let argv = args(); assert(argv.len == 6);
    let bytes, bv = parse_int(argv[2], 10); let count, cv = parse_int(argv[3], 10);
    let api, av = parse_int(argv[4], 10); let expected, ev = parse_int(argv[5], 10);
    assert(bv && cv && av && ev && api >= 0 && api < 12);
    let context, ce = fs::create_context(); assert(ce.error == fs::Error.None);
    defer fs::close_context(context);
    let root, re = fs::open_root(context, argv[1]); assert(re.error == fs::Error.None);
    var entries: fs::Entry[>..] = []; entries.push(fs::Entry { name: "sentinel" });
    var result = fs::Status { .. };
    if api == 0 { result = fs::list(argv[1], bytes, count, entries); }
    if api == 1 { result = fs::list_sorted(argv[1], bytes, count, entries); }
    if api == 2 { result = fs::list_at(root, ".", bytes, count, entries); }
    if api == 3 { result = fs::list_sorted_at(root, ".", bytes, count, entries); }
    let options = fs::ListOptions { byte_limit: bytes, entry_limit: count, adaptive: api < 8 };
    if api == 4 || api == 8 { result = fs::list(argv[1], options, entries); }
    if api == 5 || api == 9 { result = fs::list_sorted(argv[1], options, entries); }
    if api == 6 || api == 10 { result = fs::list_at(root, ".", options, entries); }
    if api == 7 || api == 11 { result = fs::list_sorted_at(root, ".", options, entries); }
    if expected == 2 { assert(result.error == fs::Error.LimitExceeded && result.os_error == 0 && entries.len == 0); }
    else if expected == 1 { assert(result.error == fs::Error.InvalidInput && result.os_error == 0 && entries.len == 0); }
    else {
        assert(result.error == fs::Error.None && result.os_error == 0);
        for entry in entries { write_stdout(entry.name); write_stdout("\0"); }
    }
}
