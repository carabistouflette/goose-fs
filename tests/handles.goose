// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn ok(result: fs::Status) { assert(result.error == fs::Error.None && result.os_error == 0); }
fn io_ok(result: fs::IOResult, bytes: i64) { ok(result.status); assert(result.bytes == bytes); }
fn main() {
    let argv = args(); assert(argv.len == 2);
    let context, context_status = fs::create_context(); ok(context_status);
    let path = str(argv[1], "/handle-file");
    let options = fs::OpenOptions { access: fs::Access.ReadWrite, creation: fs::Creation.CreateNew };
    let file, opened = fs::open_file(context, path, options); ok(opened);
    io_ok(fs::write_all(file, "abcdef"), 6);
    var info = fs::Metadata { .. }; ok(fs::file_metadata(file, info));
    assert(info.kind == fs::Kind.File && info.size == 6);
    var out: u8[>..] = []; out.resize(50, 165);
    let end_read = fs::read_some(file, 1, out); io_ok(end_read, 0); assert(end_read.eof && out.len == 0);
    let zero_read = fs::read_some(file, 0, out); io_ok(zero_read, 0); assert(!zero_read.eof);
    let start, se = fs::seek(file, 0, fs::SeekOrigin.Start); ok(se); assert(start == 0);
    let part = fs::read_some(file, 2, out); io_ok(part, 2); assert(!part.eof && out == "ab");
    io_ok(fs::read_at(file, 4, 5, out), 2); assert(out == "ef");
    let position, pe = fs::seek(file, 0, fs::SeekOrigin.Current); ok(pe); assert(position == 2);
    io_ok(fs::write_at(file, 1, "Z"), 1);
    let duplicate, de = fs::duplicate_file(file); ok(de);
    let alias = file;
    ok(fs::close_file(file));
    assert(fs::read_some(alias, 4, out).status.error == fs::Error.SystemError && out.len == 0);
    io_ok(fs::read_some(duplicate, 10, out), 4); assert(out == "cdef");
    ok(fs::remove_file(path));
    ok(fs::file_metadata(duplicate, info)); assert(info.size == 6 && info.links == 0);
    ok(fs::truncate_file(duplicate, 3));
    ok(fs::sync_file(duplicate, true)); ok(fs::sync_file(duplicate, false));
    io_ok(fs::read_at(duplicate, 0, 10, out), 3); assert(out == "aZc");
    assert(fs::read_at(duplicate, -1, 2, out).status.error == fs::Error.InvalidInput && out.len == 0);
    assert(fs::read_at(duplicate, 9223372036854775807, 1, out).status.error == fs::Error.InvalidInput);
    assert(fs::write_at(duplicate, 9223372036854775807, "x").status.error == fs::Error.InvalidInput);
    ok(fs::close_context(context));
    assert(fs::close_file(duplicate).error == fs::Error.SystemError);
    assert(fs::file_metadata(duplicate, info).error == fs::Error.SystemError && info.size == 0 && info.inode == 0);
    let stale, stale_status = fs::open_file(context, path, options);
    assert(stale_status.error == fs::Error.SystemError && stale.id == 0);
    let next, ne = fs::create_context(); ok(ne); assert(next.id != context.id);
    let appended, ae = fs::open_file(next, path, fs::OpenOptions { access: fs::Access.Write, creation: fs::Creation.CreateNew, append: true }); ok(ae);
    io_ok(fs::write_some(appended, "tail"), 4);
    assert(fs::write_at(appended, 0, "bad").status.error == fs::Error.SystemError);
    assert(fs::read_some(appended, 0, out).status.error == fs::Error.SystemError && out.len == 0);
    let invalid, ie = fs::open_file(next, path, fs::OpenOptions { truncate: true });
    assert(ie.error == fs::Error.InvalidInput && invalid.id == 0);
    let nonregular, nre = fs::open_file(next, argv[1], fs::OpenOptions { .. });
    assert(nre.error == fs::Error.NotRegular && nonregular.id == 0);
    ok(fs::close_context(next));
    ok(fs::read(path, 4, out)); assert(out == "tail");
    print("retained File ownership, bounded I/O and cursor tests passed");
}
