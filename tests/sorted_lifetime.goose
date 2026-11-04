// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn ok(value: fs::Status) { assert(value.error == fs::Error.None && value.os_error == 0); }
fn check(entries: const fs::Entry[>..]&) {
    assert(entries.len == 4);
    for entry, i in entries {
        let expected = if i == 0 { fs::Kind.Other } else if i == 1 { fs::Kind.Symlink }
                       else if i == 2 { fs::Kind.Directory } else { fs::Kind.File };
        assert(entry.kind == expected || entry.kind == fs::Kind.Unknown);
        if i == 0 { assert(entry.name == "fifo"); }
        else if i == 1 { assert(entry.name == "link"); }
        else if i == 2 { assert(entry.name == "subdir"); }
        else { assert(entry.name == "target"); }
    }
}
fn main() {
    let argv = args(); assert(argv.len == 2);
    let path = str(argv[1], "/adversarial");
    let binary = str(argv[1], "/binary");
    for route in 4 {
        let context, ce = fs::create_context(); ok(ce);
        let root, re = fs::open_root(context, argv[1]); ok(re);
        var saved: fs::Entry[>..] = [];
        let options = fs::ListOptions { adaptive: true };
        if route == 0 { ok(fs::list_sorted(path, fs::MAX_BYTES, fs::MAX_ENTRIES, saved)); }
        else if route == 1 { ok(fs::list_sorted(path, options, saved)); }
        else if route == 2 { ok(fs::list_sorted_at(root, "adversarial", fs::MAX_BYTES, fs::MAX_ENTRIES, saved)); }
        else { ok(fs::list_sorted_at(root, "adversarial", options, saved)); }
        check(saved);
        var scratch: fs::Entry[>..] = [];
        for _ in 8 { ok(fs::list_sorted(binary, options, scratch)); assert(scratch.len == 3); }
        ok(fs::close_context(context));
        assert(fs::list_sorted_at(root, "adversarial", options, scratch).error == fs::Error.SystemError && scratch.len == 0);
        var pressure: u8[>..] = []; pressure.resize(fs::MAX_BYTES, 165);
        assert(pressure[0] == 165 && pressure[pressure.len - 1] == 165);
        check(saved);
        assert(fs::list_sorted("relative", options, saved).error == fs::Error.InvalidInput && saved.len == 0);
    }
    print("sorted owned names survive later calls, allocation pressure and Context close; mixed kinds stay associated");
}
