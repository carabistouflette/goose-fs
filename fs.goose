// SPDX-License-Identifier: Apache-2.0
namespace fs;
import std;

enum Error { None, InvalidInput, LimitExceeded, NotRegular, SystemError }
enum Kind { Unknown, File, Directory, Symlink, Other }
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
    out.clear();
    if !valid_path(path) || limit < 0 || limit > MAX_BYTES { return Status { error: Error.InvalidInput }; }
    out.resize(limit, 0);
    var meta: i64[3] = [0, 0, 0];
    let code = native_call(0, path, "", 0, out[..], meta[..]);
    out.resize(meta[1]);
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
