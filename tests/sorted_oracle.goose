// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
// Consumer overloads for the public reference type must not intercept the
// library's internal sorting, including the standard algorithm's helpers.
fn sort<F>(xs: (const fs::Entry&)[:]) { assert(false); }
fn sort_insertion<F>(xs: (const fs::Entry&)[:]) { assert(false); }
fn sort_heap<F>(xs: (const fs::Entry&)[:]) { assert(false); }
fn swap_at(xs: (const fs::Entry&)[:], a: i64, b: i64) { assert(false); }
fn reverse(xs: (const fs::Entry&)[:]) { assert(false); }
fn sift_down<F>(xs: (const fs::Entry&)[:], root: i64) { assert(false); }
fn main() {
    let argv = args(); assert(argv.len == 4);
    let bytes, be = parse_int(argv[2], 10); let count, ce = parse_int(argv[3], 10);
    assert(be && ce);
    var entries: fs::Entry[>..] = [];
    let result = fs::list_sorted(argv[1], bytes, count, entries);
    assert(result.error == fs::Error.None && entries.len == count);
    for entry in entries { write_stdout(entry.name); write_stdout("\0"); }
}
