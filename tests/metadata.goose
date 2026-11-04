// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn ok(result: fs::Status) { assert(result.error == fs::Error.None && result.os_error == 0); }
fn main() {
    let argv = args(); assert(argv.len == 2);
    var info = fs::Metadata { .. };
    ok(fs::metadata(argv[1], info));
    assert(info.kind == fs::Kind.Directory && info.inode != 0 && info.links > 0);
    let privileged = info.uid == 0;
    let root_dir, root_error = fs::is_dir(argv[1]); ok(root_error); assert(root_dir);
    ok(fs::metadata("/", info)); assert(info.kind == fs::Kind.Directory);
    let file = str(argv[1], "/adversarial/target");
    ok(fs::metadata(file, info)); assert(info.kind == fs::Kind.File && info.size == 9);
    assert(info.modified.nanoseconds >= 0 && info.modified.nanoseconds < 1000000000);
    if info.created_available { assert(info.created.nanoseconds >= 0 && info.created.nanoseconds < 1000000000); }
    let link = str(argv[1], "/adversarial/link");
    ok(fs::metadata(link, info)); assert(info.kind == fs::Kind.Symlink && info.size == 6);
    let present, pe = fs::exists(link); ok(pe); assert(present);
    let directory, de = fs::is_dir(link); ok(de); assert(!directory);
    let fifo = str(argv[1], "/adversarial/fifo");
    ok(fs::metadata(fifo, info)); assert(info.kind == fs::Kind.Fifo);
    let absent = str(argv[1], "/absent");
    let missing, me = fs::exists(absent); ok(me); assert(!missing);
    assert(fs::metadata(absent, info).error == fs::Error.SystemError);
    assert(info.kind == fs::Kind.Unknown && info.inode == 0 && info.size == 0 && !info.created_available);
    let absent_dir, absent_dir_error = fs::is_dir(absent); ok(absent_dir_error); assert(!absent_dir);
    let dangling = str(argv[1], "/dangling");
    let dangling_exists, dangling_error = fs::exists(dangling); ok(dangling_error); assert(dangling_exists);
    ok(fs::metadata(dangling, info)); assert(info.kind == fs::Kind.Symlink);
    let non_directory = str(file, "/child");
    let bad_prefix, be = fs::exists(non_directory);
    assert(!bad_prefix && be.error == fs::Error.SystemError);
    let through_link = str(argv[1], "/ancestor/target");
    assert(fs::metadata(through_link, info).error == fs::Error.SystemError);
    assert(info.kind == fs::Kind.Unknown && info.inode == 0);
    assert(fs::metadata("relative", info).error == fs::Error.InvalidInput);
    if !privileged {
        let denied = str(argv[1], "/denied/child");
        let denied_exists, error = fs::exists(denied);
        assert(!denied_exists && error.error == fs::Error.SystemError && error.os_error != 0);
    }
    var entries: fs::Entry[>..] = [];
    let binary = str(argv[1], "/binary");
    ok(fs::list_sorted(binary, 273, 3, entries)); assert(entries.len == 3);
    for entry, i in entries {
        if i == 0 { assert(entry.name == "line\nbreak"); }
        else if i == 1 { assert(entry.name.len == 255 && entry.name[0] == 'x'); }
        else { assert(entry.name.len == 2 && entry.name[0] == 255 && entry.name[1] == 254); }
    }
    assert(fs::list_sorted(binary, 272, 3, entries).error == fs::Error.LimitExceeded);
    assert(entries.len == 0);
    var out: u8[>..] = []; out.resize(1024, 165);
    let small = str(binary, "/line\nbreak");
    ok(fs::read(small, 5, out)); assert(out == "bytes");
    let maximum = str(argv[1], "/maximum");
    for _ in 2 {
        ok(fs::read(maximum, fs::MAX_BYTES, out)); assert(out.len == fs::MAX_BYTES);
        for c, i in out { let expected = if i % 2 == 0 { 0 } else { 255 }; assert(c == expected); }
    }
    ok(fs::read(small, 32, out)); assert(out == "bytes");
    let empty = str(argv[1], "/empty"); ok(fs::create_file(empty, ""));
    ok(fs::read(empty, 8, out)); assert(out.len == 0);
    assert(fs::read("relative", 8, out).error == fs::Error.InvalidInput && out.len == 0);
    assert(fs::read(absent, 32, out).error == fs::Error.SystemError && out.len == 0);
    assert(fs::read(small, 4, out).error == fs::Error.LimitExceeded && out.len == 0);
    ok(fs::read(small, 5, out)); assert(out == "bytes");
    print("metadata, sorted names and read-buffer reuse passed");
}
