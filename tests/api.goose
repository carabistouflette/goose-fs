// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn ok(s: fs::Status) { assert(s.error == fs::Error.None); assert(s.os_error == 0); }
fn main() {
    let args = args(); assert(args.len == 2);
    let dir = str(args[1], "/case");
    ok(fs::create_dir(dir));
    assert(fs::create_dir(dir).error == fs::Error.SystemError);
    let file = str(dir, "/data");
    ok(fs::create_file(file, "a\0b\n"));
    assert(fs::create_file(file, "replaced").error == fs::Error.SystemError);
    var out: u8[>..] = [];
    ok(fs::read(file, 4, out)); assert(out == "a\0b\n");
    assert(fs::read(file, 3, out).error == fs::Error.LimitExceeded); assert(out.len == 0);
    assert(fs::read(file, 0, out).error == fs::Error.LimitExceeded); assert(out.len == 0);
    assert(fs::read(dir, 10, out).error == fs::Error.NotRegular);
    assert(fs::read("/", 10, out).error == fs::Error.NotRegular);
    assert(fs::read("relative", 10, out).error == fs::Error.InvalidInput);
    assert(fs::read(file, -1, out).error == fs::Error.InvalidInput);
    assert(fs::read(file, fs::MAX_BYTES + 1, out).error == fs::Error.InvalidInput);
    let invalid: (const u8[:])[8] = ["", "/a/", "//a", "/a//b", "/./a", "/a/..", "/a/../b", "/a\0b"];
    for path in invalid {
        assert(fs::read(path, 10, out).error == fs::Error.InvalidInput);
        assert(fs::create_dir(path).error == fs::Error.InvalidInput);
    }
    let empty = str(dir, "/empty"); ok(fs::create_file(empty, ""));
    ok(fs::read(empty, 0, out)); assert(out.len == 0);
    var entries: fs::Entry[>..] = [];
    ok(fs::list(dir, 13, 2, entries)); assert(entries.len == 2);
    var found = false;
    for e in entries { if e.name == "data" { found = true; assert(e.kind == fs::Kind.File || e.kind == fs::Kind.Unknown); } }
    assert(found);
    var saved: u8[>..] = [];
    for e in entries { saved.append(e.name); }
    assert(fs::list(dir, 12, 2, entries).error == fs::Error.LimitExceeded); assert(entries.len == 0);
    assert(saved.len > 0);
    assert(fs::list(dir, 100, 1, entries).error == fs::Error.LimitExceeded); assert(entries.len == 0);
    assert(fs::list(dir, 100, -1, entries).error == fs::Error.InvalidInput);
    assert(fs::list(dir, 100, fs::MAX_ENTRIES + 1, entries).error == fs::Error.InvalidInput);
    assert(fs::remove_file(dir).error == fs::Error.SystemError);
    assert(fs::remove_empty_dir(dir).error == fs::Error.SystemError);
    ok(fs::remove_file(file)); ok(fs::remove_file(empty));
    ok(fs::list(dir, 0, 0, entries)); assert(entries.len == 0);
    ok(fs::remove_empty_dir(dir));
    assert(fs::create_dir("/").error == fs::Error.InvalidInput);
    let adversarial = str(args[1], "/adversarial");
    let link = str(adversarial, "/link");
    assert(fs::read(link, 100, out).error == fs::Error.SystemError);
    assert(fs::create_file(link, "bad").error == fs::Error.SystemError);
    let ancestor = str(args[1], "/ancestor/target");
    assert(fs::read(ancestor, 100, out).error == fs::Error.SystemError);
    assert(fs::remove_file(ancestor).error == fs::Error.SystemError);
    let fifo = str(adversarial, "/fifo");
    assert(fs::read(fifo, 100, out).error == fs::Error.NotRegular);
    ok(fs::remove_file(link));
    let target = str(adversarial, "/target");
    ok(fs::read(target, 9, out)); assert(out == "protected");
    print("filesystem API passed");
}
