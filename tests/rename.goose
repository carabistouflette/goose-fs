// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn ok(status: fs::Status) { assert(status.error == fs::Error.None && status.os_error == 0); }
fn applied(result: fs::RenameResult, synced: bool) {
    ok(result.status); assert(result.outcome == fs::RenameOutcome.Applied);
    assert(result.parents_synced == synced && result.cleanup_os_error == 0);
}
fn main() {
    let argv = args(); assert(argv.len == 2);
    let context, ce = fs::create_context(); ok(ce); defer fs::close_context(context);
    let root, re = fs::open_root(context, argv[1]); ok(re);
    let source = str(argv[1], "/source"); let target = str(argv[1], "/target");
    ok(fs::create_file(source, "first")); ok(fs::create_file(target, "old"));
    let file, fe = fs::open_file(context, source, fs::OpenOptions { .. }); ok(fe);
    applied(fs::rename(source, target, fs::RenameOptions { .. }), false);
    var bytes: u8[>..] = [];
    ok(fs::read(target, 5, bytes)); assert(bytes == "first");
    let read = fs::read_at(file, 0, 5, bytes); ok(read.status); assert(bytes == "first");
    assert(fs::read(source, 5, bytes).error == fs::Error.SystemError && bytes.len == 0);
    ok(fs::create_file_at(root, "stage", "second"));
    let no_replace = fs::RenameOptions { policy: fs::RenamePolicy.NoReplace };
    let collision = fs::rename_at(root, "stage", "target", no_replace);
    assert(collision.status.error == fs::Error.SystemError && collision.outcome == fs::RenameOutcome.Unknown);
    assert(!collision.parents_synced && collision.cleanup_os_error == 0);
    ok(fs::read_file_at(root, "stage", 6, bytes)); assert(bytes == "second");
    applied(fs::rename_at(root, "stage", "new", fs::RenameOptions { policy: fs::RenamePolicy.NoReplace, sync_parents: true }), true);
    applied(fs::rename_at(root, "new", "new", fs::RenameOptions { .. }), false);
    let same = fs::rename_at(root, "new", "new", no_replace);
    assert(same.status.error == fs::Error.SystemError && same.outcome == fs::RenameOutcome.Unknown);
    ok(fs::create_dir_at(root, "dir")); ok(fs::create_file_at(root, "dir/inside", "held"));
    let child, ch = fs::open_root_at(root, "dir"); ok(ch);
    applied(fs::rename_at(root, "dir", "moved", fs::RenameOptions { sync_parents: true }), true);
    ok(fs::read_file_at(child, "inside", 4, bytes)); assert(bytes == "held");
    for bad in ["", ".", "/", "/x", "..", "x/..", "x//y", "x/", "x\0y"] {
        let from = fs::rename_at(root, bad, "unused", fs::RenameOptions { .. });
        let to = fs::rename_at(root, "new", bad, fs::RenameOptions { .. });
        assert(from.status.error == fs::Error.InvalidInput && from.outcome == fs::RenameOutcome.NotAttempted);
        assert(to.status.error == fs::Error.InvalidInput && to.outcome == fs::RenameOutcome.NotAttempted);
        assert(!from.parents_synced && !to.parents_synced && from.cleanup_os_error == 0 && to.cleanup_os_error == 0);
    }
    for bad in ["", "/", "relative", "/x/../y", "/x//y", "/x/", "/x\0y"] {
        let result = fs::rename(bad, target, fs::RenameOptions { .. });
        assert(result.status.error == fs::Error.InvalidInput && result.outcome == fs::RenameOutcome.NotAttempted);
    }
    let wrong = fs::Root { context: context, id: file.id };
    let wrong_result = fs::rename_at(wrong, "new", "unused", fs::RenameOptions { .. });
    assert(wrong_result.status.error == fs::Error.SystemError && wrong_result.outcome == fs::RenameOutcome.NotAttempted);
    ok(fs::close_root(root));
    let stale = fs::rename_at(root, "new", "unused", fs::RenameOptions { .. });
    assert(stale.status.error == fs::Error.SystemError && stale.outcome == fs::RenameOutcome.NotAttempted && !stale.parents_synced);
    print("public absolute/Root rename, no-replace, sync, no-op, held descriptors and invalid/stale guards passed");
}
