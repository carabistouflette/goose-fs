// SPDX-License-Identifier: Apache-2.0
import fs from "../..";
import std;
import os;
fn code(s: fs::Status) -> i64 { return if s.error == fs::Error.None { 0 } else if s.error == fs::Error.InvalidInput { 1 } else if s.error == fs::Error.LimitExceeded { 2 } else if s.error == fs::Error.NotRegular { 3 } else { 4 }; }
fn value(bytes: const u8[:]) -> i64 {
    var n = bytes.len;
    if bytes.len > 0 { n += bytes[0] + (bytes[bytes.len - 1] as i64); }
    return n;
}
fn fd_count() -> i64 {
    var packed: u8[>..] = []; assert(list_dir("/proc/self/fd", packed));
    var n:      i64     = 0; for c in packed { if c == '\n' { n++; } }
    return n;
}
fn digit(c: u8) -> u8 {
    if c >= '0' && c <= '9' { return c - '0'; }
    assert(c >= 'a' && c <= 'f'); return c - 'a' + 10;
}
fn fresh_value(path: const u8[:], limit: i64, expected: i64) -> i64 {
    var out: u8[>..] = [];
    assert(code(fs::read(path, limit, out)) == expected);
    if expected != 0 { assert(out.len == 0); }
    return value(out) + expected + 1;
}
fn main() {
    let a = args(); assert(a.len >= 2);
    if a[1] == "probe" || a[1] == "growth" || a[1] == "empty-probe" {
        assert(a.len == 5 && a[2].len % 2 == 0);
        var path: u8[>..] = [];
        for i in (a[2].len / 2) { path.push(digit(a[2][i * 2]) * 16 + digit(a[2][i * 2 + 1])); }
        let limit, lv = parse_int(a[3], 10); let loops, cv = parse_int(a[4], 10);
        assert(lv && cv);
        assert(if a[1] == "growth" { limit >= 0 && limit <= fs::MAX_BYTES && loops >= 0 && loops <= limit } else { loops >= 1 && loops <= 10000 });
        let before = fd_count();
        var out: u8[>..] = []; if a[1] != "empty-probe" { out.append("sentinel"); }
        if a[1] == "growth" { out.resize(limit, 165); out.resize(loops); }
        var s = fs::Status { .. };
        for _ in (if a[1] == "growth" { 1 } else { loops }) {
            if a[1] == "empty-probe" { out = []; }
            s = fs::read(path, limit, out);
        }
        // FAULT_FINISH
        let after = fd_count();
        print(code(s), "\t", s.os_error, "\t", out.len, "\t", before, "\t", after);
        write_stdout(out); return;
    }
    assert(a.len == 6 && (a[1] == "measure" || a[1] == "fresh"));
    let limit, lv = parse_int(a[3], 10); let expected, ev = parse_int(a[4], 10);
    let count, cv = parse_int(a[5], 10);
    assert(lv && ev && cv && count >= 1 && count <= 1000000);
    var out: u8[>..] = [];
    if a[1] == "fresh" { fresh_value(a[2], limit, expected); }
    else { assert(code(fs::read(a[2], limit, out)) == expected); }
    for sample in 7 {
        var sum: i64 = 0; let start = clock_ns();
        if a[1] == "fresh" { for _ in count { sum += fresh_value(a[2], limit, expected); } }
        else {
            for _ in count {
                assert(code(fs::read(a[2], limit, out)) == expected);
                if expected != 0 { assert(out.len == 0); }
                sum += value(out) + expected + 1;
            }
        }
        let elapsed = clock_ns() - start;
        print(sample, "\t", elapsed / count, "\t", sum);
    }
}
