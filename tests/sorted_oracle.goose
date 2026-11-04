// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn main() {
    let argv = args(); assert(argv.len == 4);
    let bytes, be = parse_int(argv[2], 10); let count, ce = parse_int(argv[3], 10);
    assert(be && ce);
    var entries: fs::Entry[>..] = [];
    let result = fs::list_sorted(argv[1], bytes, count, entries);
    assert(result.error == fs::Error.None && entries.len == count);
    for entry in entries { write_stdout(entry.name); write_stdout("\0"); }
}
