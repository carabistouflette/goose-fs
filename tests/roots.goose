// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn ok(result: fs::Status) { assert(result.error == fs::Error.None && result.os_error == 0); }
fn main() {
    let argv = args(); assert(argv.len == 2);
    let context, ce = fs::create_context(); ok(ce);
    let fixture, fe = fs::open_root(context, argv[1]); ok(fe);
    var info = fs::Metadata { .. };
    ok(fs::root_metadata(fixture, info)); assert(info.kind == fs::Kind.Directory);
    ok(fs::metadata_at(fixture, ".", info)); assert(info.kind == fs::Kind.Directory);
    ok(fs::metadata_at(fixture, "adversarial/link", info)); assert(info.kind == fs::Kind.Symlink);
    var out: u8[>..] = []; out.append("sentinel");
    assert(fs::read_file_at(fixture, "adversarial/link", 16, out).error == fs::Error.SystemError && out.len == 0);
    assert(fs::read_file_at(fixture, "ancestor/target", 16, out).error == fs::Error.SystemError && out.len == 0);
    ok(fs::read_file_at(fixture, "adversarial/target", 9, out)); assert(out == "protected");
    assert(fs::read_file_at(fixture, "adversarial/target", 8, out).error == fs::Error.LimitExceeded && out.len == 0);
    assert(fs::read_file_at(fixture, ".", 16, out).error == fs::Error.NotRegular && out.len == 0);
    ok(fs::metadata_at(fixture, "dangling", info)); assert(info.kind == fs::Kind.Symlink);
    ok(fs::remove_file_at(fixture, "dangling"));
    assert(fs::metadata_at(fixture, "dangling", info).error == fs::Error.SystemError && info.inode == 0);
    var entries: fs::Entry[>..] = [];
    ok(fs::list_sorted_at(fixture, "binary", 273, 3, entries)); assert(entries.len == 3);
    for entry, i in entries {
        if i == 0 { assert(entry.name == "line\nbreak"); }
        if i == 2 { assert(entry.name.len == 2 && entry.name[0] == 255); }
    }
    assert(fs::list_at(fixture, "binary", 272, 3, entries).error == fs::Error.LimitExceeded && entries.len == 0);
    ok(fs::create_dir_at(fixture, "cap"));
    let root, re = fs::open_root_at(fixture, "cap"); ok(re);
    ok(fs::list_at(root, ".", 0, 0, entries)); assert(entries.len == 0);
    ok(fs::create_file_at(root, "x", "bytes")); ok(fs::create_dir_at(root, "child"));
    ok(fs::create_file_at(root, "line\nbreak", "data"));
    for _ in 2 { ok(fs::list_sorted_at(root, ".", 64, 3, entries)); assert(entries.len == 3); }
    let child, ch = fs::open_root_at(root, "child"); ok(ch);
    let file, opened = fs::open_file_at(child, "file", fs::OpenOptions { access: fs::Access.ReadWrite, creation: fs::Creation.CreateNew }); ok(opened);
    let written = fs::write_all(file, "owned"); ok(written.status); assert(written.bytes == 5);
    ok(fs::close_root(child));
    let read = fs::read_at(file, 0, 5, out); ok(read.status); assert(out == "owned");
    let same_root, se = fs::open_root_at(root, "."); ok(se);
    ok(fs::close_root(root));
    ok(fs::read_file_at(same_root, "x", 5, out)); assert(out == "bytes");
    let wrong_file = fs::File { context: same_root.context, id: same_root.id };
    assert(fs::close_file(wrong_file).error == fs::Error.SystemError);
    assert(fs::file_metadata(wrong_file, info).error == fs::Error.SystemError && info.kind == fs::Kind.Unknown);
    let locked, le = fs::try_lock_file(wrong_file, fs::LockMode.Exclusive); assert(!locked && le.error == fs::Error.SystemError);
    ok(fs::root_metadata(same_root, info)); assert(info.kind == fs::Kind.Directory);
    let wrong_root = fs::Root { context: file.context, id: file.id };
    assert(fs::close_root(wrong_root).error == fs::Error.SystemError);
    assert(fs::read_file_at(wrong_root, ".", 5, out).error == fs::Error.SystemError && out.len == 0);
    ok(fs::file_metadata(file, info)); assert(info.size == 5);
    for bad in ["", "/", "/x", "..", "../x", "x/..", "x/./y", "x//y", "x/", "./x", "x\0y"] {
        var invalid_out:     u8[>..]        = []; invalid_out.append("sentinel");
        var invalid_entries: fs::Entry[>..] = [];
        invalid_entries.push(fs::Entry { name: "sentinel" });
        assert(fs::read_file_at(same_root, bad, 5, invalid_out).error == fs::Error.InvalidInput && invalid_out.len == 0);
        assert(fs::metadata_at(same_root, bad, info).error == fs::Error.InvalidInput && info.inode == 0);
        assert(fs::list_at(same_root, bad, 64, 3, invalid_entries).error == fs::Error.InvalidInput && invalid_entries.len == 0);
    }
    assert(fs::create_file_at(same_root, ".", "bad").error == fs::Error.InvalidInput);
    assert(fs::create_dir_at(same_root, ".").error == fs::Error.InvalidInput);
    assert(fs::remove_file_at(same_root, ".").error == fs::Error.InvalidInput);
    assert(fs::remove_empty_dir_at(same_root, ".").error == fs::Error.InvalidInput);
    let dot, doe = fs::open_file_at(same_root, ".", fs::OpenOptions { access: fs::Access.ReadWrite });
    assert(doe.error == fs::Error.InvalidInput && dot.id == 0);
    ok(fs::remove_file_at(same_root, "line\nbreak"));
    ok(fs::create_dir_at(same_root, "empty")); ok(fs::remove_empty_dir_at(same_root, "empty"));
    ok(fs::close_context(context));
    assert(fs::root_metadata(same_root, info).error == fs::Error.SystemError && info.inode == 0);
    assert(fs::read_some(file, 5, out).status.error == fs::Error.SystemError && out.len == 0);
    print("Root relative paths, kind/lifetime guards, owned names and clearing tests passed");
}
