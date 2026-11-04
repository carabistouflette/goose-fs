// SPDX-License-Identifier: Apache-2.0
namespace fs;
import std;

enum Error { None, InvalidInput, LimitExceeded, NotRegular, SystemError }
enum Kind { Unknown, File, Directory, Symlink, Other, Fifo, Socket, CharacterDevice, BlockDevice }
struct Status { error: Error = Error.None, os_error: i64 = 0 }
struct Entry { kind: Kind = Kind.Unknown, name: u8[] }
const MAX_PATH_BYTES = 4095;
const MAX_BYTES = 1048576;
const MAX_ENTRIES = 4096;
extern fn native_call(op: i64, path: const u8[:], data: const u8[:], entries: i64,
                      out: u8[:], meta: i64[:]) -> i64 = "gf_call";

fn valid_path(path: const u8[:]) -> bool {
    if path.len < 1 || path.len > MAX_PATH_BYTES || path[0] != '/' { return false; }
    var start: i64 = 1;
    for c, i in path {
        if c == 0 { return false; }
        if i > 0 && c == '/' {
            let n = i - start;
            if n == 0 || (n == 1 && path[start] == '.') ||
               (n == 2 && path[start] == '.' && path[start + 1] == '.') { return false; }
            start = i + 1;
        }
    }
    if path.len == 1 { return true; }
    let n = path.len - start;
    return n > 0 && !(n == 1 && path[start] == '.') &&
           !(n == 2 && path[start] == '.' && path[start + 1] == '.');
}
fn status(code: i64, os_error: i64) -> Status {
    let error = if code == 0 { Error.None } else if code == 1 { Error.InvalidInput }
                else if code == 2 { Error.LimitExceeded } else if code == 3 { Error.NotRegular }
                else { Error.SystemError };
    return Status { error: error, os_error: os_error };
}
fn read(path: const u8[:], limit: i64, out: u8[>..]&) -> Status {
    if !valid_path(path) || limit < 0 || limit > MAX_BYTES {
        out.clear();
        return Status { error: Error.InvalidInput };
    }
    // Existing bytes are initialized already. Only growth needs initialization.
    out.resize(limit, 0);
    var meta: i64[3] = [0, 0, 0];
    let code = native_call(0, path, "", 0, out[..], meta[..]);
    if code == 0 { out.resize(meta[1]); } else { out.clear(); }
    return status(code, meta[0]);
}
fn list(path: const u8[:], byte_limit: i64, entry_limit: i64, out: Entry[>..]&) -> Status {
    out.clear();
    if !valid_path(path) || byte_limit < 0 || byte_limit > MAX_BYTES ||
       entry_limit < 0 || entry_limit > MAX_ENTRIES { return Status { error: Error.InvalidInput }; }
    var packed: u8[>..] = [];
    packed.resize(byte_limit, 0);
    var meta: i64[3] = [0, 0, 0];
    let code = native_call(1, path, "", entry_limit, packed[..], meta[..]);
    if code != 0 { return status(code, meta[0]); }
    var pos: i64 = 0;
    for _ in meta[2] {
        let tag = packed[pos]; pos++;
        let kind = if tag == 1 { Kind.File } else if tag == 2 { Kind.Directory }
                   else if tag == 3 { Kind.Symlink } else if tag == 4 { Kind.Other } else { Kind.Unknown };
        let start = pos;
        while pos < meta[1] && packed[pos] != 0 { pos++; }
        out.push(Entry { kind: kind, name: owned_name(packed[start..pos]) });
        pos++;
    }
    return Status { .. };
}
fn mutate(op: i64, path: const u8[:], data: const u8[:]) -> Status {
    if !valid_path(path) || path.len == 1 || data.len > MAX_BYTES { return Status { error: Error.InvalidInput }; }
    var meta:   i64[3] = [0, 0, 0];
    var unused: u8[0]  = [];
    let code = native_call(op, path, data, 0, unused[..], meta[..]);
    return status(code, meta[0]);
}
fn create_file(path: const u8[:], data: const u8[:]) -> Status { return mutate(2, path, data); }
fn create_dir(path: const u8[:]) -> Status { return mutate(3, path, ""); }
fn remove_file(path: const u8[:]) -> Status { return mutate(4, path, ""); }
fn remove_empty_dir(path: const u8[:]) -> Status { return mutate(5, path, ""); }

fn owned_name(source: const u8[:]) -> u8[] {
    var result: u8[>..] = [];
    result.append(source);
    return result;
}

struct Timestamp { seconds: i64 = 0, nanoseconds: i64 = 0 }
struct Metadata {
    kind:              Kind      = Kind.Unknown,
    size:              u64       = 0,
    permissions:       u32       = 0,
    uid:               u32       = 0,
    gid:               u32       = 0,
    device:            u64       = 0,
    inode:             u64       = 0,
    links:             u64       = 0,
    accessed:          Timestamp = Timestamp { .. },
    modified:          Timestamp = Timestamp { .. },
    changed:           Timestamp = Timestamp { .. },
    created:           Timestamp = Timestamp { .. },
    created_available: bool      = false,
}
extern fn native_metadata(path: const u8[:], fields: i64[:]) -> i64 = "gf_metadata";
extern fn native_missing(os_error: i64) -> bool = "gf_missing";

// Inspect the final entry itself; never follow a final or ancestor symlink.
fn metadata(path: const u8[:], out: Metadata&) -> Status {
    out = Metadata { .. };
    if !valid_path(path) { return Status { error: Error.InvalidInput }; }
    var fields: i64[18] = [0; 18];
    let code = native_metadata(path, fields[..]);
    if code != 0 { return status(code, fields[0]); }
    let kind = if fields[1] == 1 { Kind.File } else if fields[1] == 2 { Kind.Directory }
               else if fields[1] == 3 { Kind.Symlink } else if fields[1] == 5 { Kind.Fifo }
               else if fields[1] == 6 { Kind.Socket } else if fields[1] == 7 { Kind.CharacterDevice }
               else if fields[1] == 8 { Kind.BlockDevice } else { Kind.Other };
    out = Metadata { kind: kind, size: fields[2] as! u64, permissions: fields[3] as! u32,
        uid:      fields[4] as! u32, gid: fields[5] as! u32, device: fields[6] as! u64,
        inode:    fields[7] as! u64, links: fields[8] as! u64,
        accessed: Timestamp { fields[9], fields[10] }, modified: Timestamp { fields[11], fields[12] },
        changed:  Timestamp { fields[13], fields[14] }, created: Timestamp { fields[15], fields[16] },
        created_available: fields[17] != 0 };
    return Status { .. };
}
fn exists(path: const u8[:]) -> bool, Status {
    var info = Metadata { .. };
    let result = metadata(path, info);
    if result.error == Error.SystemError && native_missing(result.os_error) { return false, Status { .. }; }
    return result.error == Error.None, result;
}
fn is_dir(path: const u8[:]) -> bool, Status {
    var info = Metadata { .. };
    let result = metadata(path, info);
    if result.error == Error.SystemError && native_missing(result.os_error) { return false, Status { .. }; }
    return result.error == Error.None && info.kind == Kind.Directory, result;
}
fn name_before(a: const u8[:], b: const u8[:]) -> bool {
    var i: i64 = 0;
    while i < a.len && i < b.len {
        if a[i] != b[i] { return a[i] < b[i]; }
        i++;
    }
    return a.len < b.len;
}
fn list_sorted(path: const u8[:], byte_limit: i64, entry_limit: i64, out: Entry[>..]&) -> Status {
    out.clear();
    var entries: Entry[>..] = [];
    let result = list(path, byte_limit, entry_limit, entries);
    if result.error != Error.None { return result; }
    var order: (const Entry&)[>..] = [];
    for entry in entries { order.push(entry); }
    sort_entries(order);
    for entry in order { out.push(Entry { kind: entry.kind, name: owned_name(entry.name) }); }
    return Status { .. };
}

fn swap_entries(order: (const Entry&)[:], a: i64, b: i64) {
    let saved: const Entry& = order[a];
    order[a] .= order[b];
    order[b] .= saved;
}
fn sift_entries(order: (const Entry&)[:], start: i64, end: i64) {
    var root = start;
    while root * 2 + 1 < end {
        var child = root * 2 + 1;
        if child + 1 < end && name_before(order[child].name, order[child + 1].name) { child++; }
        if !name_before(order[root].name, order[child].name) { break; }
        swap_entries(order, root, child); root = child;
    }
}
fn sort_entries(order: (const Entry&)[:]) {
    var root = order.len / 2;
    while root > 0 { root--; sift_entries(order, root, order.len); }
    var end = order.len;
    while end > 1 { end--; swap_entries(order, 0, end); sift_entries(order, 0, end); }
}
