// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn ok(status: fs::Status) { assert(status.error == fs::Error.None && status.os_error == 0); }
fn main() {
    let argv = args(); assert(argv.len == 2);
    let context, ce = fs::create_context(); ok(ce); defer fs::close_context(context);
    let root, re = fs::open_root(context, argv[1]); ok(re);
    ok(fs::create_file_at(root, "file", "contents"));
    let file, fe = fs::open_file_at(root, "file", fs::OpenOptions { .. }); ok(fe);
    let duplicate, de = fs::duplicate_file(file); ok(de);
    let position, se = fs::seek(file, 3, fs::SeekOrigin.Start); ok(se); assert(position == 3);
    ok(fs::set_permissions(file, 0));
    var info = fs::Metadata { .. }; ok(fs::file_metadata(file, info)); assert(info.permissions == 0);
    ok(fs::set_permissions(file, 416)); // 0640, independent of creation umask.
    ok(fs::file_metadata(duplicate, info)); assert(info.permissions == 416);
    ok(fs::set_owner(file, -1, -1));
    let exact = fs::TimeUpdate { action: fs::TimeAction.Exact, value: fs::Timestamp { seconds: 2200000000, nanoseconds: 987654321 } };
    let negative = fs::TimeUpdate { action: fs::TimeAction.Exact, value: fs::Timestamp { seconds: -2, nanoseconds: 123456789 } };
    ok(fs::set_times(file, negative, exact));
    ok(fs::file_metadata(duplicate, info));
    assert(info.accessed.seconds == -2 && info.accessed.nanoseconds == 123456789);
    assert(info.modified.seconds == 2200000000 && info.modified.nanoseconds == 987654321);
    let keep = fs::TimeUpdate { value: fs::Timestamp { seconds: -999, nanoseconds: -999 } };
    let epoch = fs::TimeUpdate { action: fs::TimeAction.Exact };
    ok(fs::set_times(file, keep, epoch)); ok(fs::file_metadata(file, info));
    assert(info.accessed.seconds == -2 && info.accessed.nanoseconds == 123456789);
    assert(info.modified.seconds == 0 && info.modified.nanoseconds == 0);
    ok(fs::set_times(file, fs::TimeUpdate { action: fs::TimeAction.Now }, keep));
    ok(fs::file_metadata(file, info)); assert(info.modified.seconds == 0 && info.accessed.seconds > 0);
    let invalid = fs::TimeUpdate { action: fs::TimeAction.Exact, value: fs::Timestamp { nanoseconds: 1000000000 } };
    assert(fs::set_times(file, invalid, keep).error == fs::Error.InvalidInput);
    assert(fs::set_permissions(file, 4096).error == fs::Error.InvalidInput);
    assert(fs::set_owner(file, -2, -1).error == fs::Error.InvalidInput);
    assert(fs::set_owner(file, -1, 4294967295).error == fs::Error.InvalidInput);
    let after, ae = fs::seek(file, 0, fs::SeekOrigin.Current); ok(ae); assert(after == 3);
    ok(fs::remove_file_at(root, "file"));
    ok(fs::create_file_at(root, "file", "replacement"));
    ok(fs::set_permissions(file, 384)); ok(fs::set_times(file, epoch, exact));
    var path_info = fs::Metadata { .. }; ok(fs::metadata_at(root, "file", path_info));
    ok(fs::file_metadata(duplicate, info)); assert(info.inode != path_info.inode && info.modified.seconds == 2200000000);
    var bytes: u8[>..] = []; let read = fs::read_at(duplicate, 0, 8, bytes); ok(read.status); assert(bytes == "contents");
    ok(fs::sync_file(file, false));
    let wrong = fs::File { context: root.context, id: root.id };
    assert(fs::set_permissions(wrong, 384).error == fs::Error.SystemError);
    assert(fs::set_owner(wrong, -1, -1).error == fs::Error.SystemError);
    assert(fs::set_times(wrong, keep, keep).error == fs::Error.SystemError);
    ok(fs::close_file(file));
    assert(fs::set_permissions(file, 384).error == fs::Error.SystemError);
    assert(fs::set_owner(file, -1, -1).error == fs::Error.SystemError);
    assert(fs::set_times(file, keep, keep).error == fs::Error.SystemError);
    ok(fs::file_metadata(duplicate, info));
    print("held File mode/owner/time changes, readonly access, ignored fields, stale/kind guards and inode lifetime passed");
}
