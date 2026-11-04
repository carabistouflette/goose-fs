// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn str(a: const u8[:]) -> u8[>..] { [] }
fn copy(a: const u8[:]) -> u8[>..] { [] }
fn min(a: i64, b: i64) -> i64 { 0 }
fn max(a: i64, b: i64) -> i64 { 0 }
fn valid_path(a: const u8[:]) -> bool { true }
fn main() {
    let argv = args();
    var file: u8[>..] = [];
    file.append(argv[1]); file.append("/filename");
    assert(fs::create_file(file, "bytes").error == fs::Error.None);
    var out: u8[>..] = [];
    assert(fs::read(file, 5, out).error == fs::Error.None && out == "bytes");
    var entries: fs::Entry[>..] = [];
    assert(fs::list(argv[1], 100, 10, entries).error == fs::Error.None);
    assert(entries.len == 1);
    for e in entries { assert(e.name == "filename"); }
    assert(fs::read("relative", 10, out).error == fs::Error.InvalidInput);
}
