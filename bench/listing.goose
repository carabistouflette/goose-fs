// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn listing(path: const u8[:], root: fs::Root, api: i64, budget: i64, entries: fs::Entry[>..]&) {
    var result = fs::Status { .. };
    if api == 0 { result = fs::list(path, budget, fs::MAX_ENTRIES, entries); }
    if api == 1 { result = fs::list_sorted(path, budget, fs::MAX_ENTRIES, entries); }
    if api == 2 { result = fs::list_at(root, ".", budget, fs::MAX_ENTRIES, entries); }
    if api == 3 { result = fs::list_sorted_at(root, ".", budget, fs::MAX_ENTRIES, entries); }
    assert(result.error == fs::Error.None && result.os_error == 0);
}
fn main() {
    let argv = args(); assert(argv.len == 5);
    let budget, bv = parse_int(argv[2], 10); let api, av = parse_int(argv[3], 10);
    let iterations, iv = parse_int(argv[4], 10);
    assert(bv && av && iv && api >= 0 && api < 4 && iterations >= 0 && iterations <= 1000000);
    let context, ce = fs::create_context(); assert(ce.error == fs::Error.None);
    defer fs::close_context(context);
    let root, re = fs::open_root(context, argv[1]); assert(re.error == fs::Error.None);
    var entries: fs::Entry[>..] = [];
    listing(argv[1], root, api, budget, entries);
    if iterations == 0 {
        for entry in entries { write_stdout(entry.name); write_stdout("\0"); }
        return;
    }
    var checksum: i64 = 0;
    for sample in 7 {
        let start = clock_ns();
        for _ in iterations {
            listing(argv[1], root, api, budget, entries);
            checksum += entries.len;
            for entry in entries {
                checksum += entry.name.len + entry.name[0] + entry.name[entry.name.len - 1];
            }
        }
        let elapsed = clock_ns() - start;
        print(sample, " ", elapsed / iterations, " ", checksum);
    }
}
