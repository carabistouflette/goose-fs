// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn reads(label: const u8[:], path: const u8[:], limit: i64, count: i64, expected: fs::Error) {
    var out:      u8[>..] = [];
    var checksum: i64     = 0;
    let warm = fs::read(path, limit, out); assert(warm.error == expected);
    for sample in 7 {
        let start = clock_ns();
        for _ in count {
            let result = fs::read(path, limit, out); assert(result.error == expected);
            checksum += out.len;
            if out.len > 0 { checksum += out[0]; }
        }
        let elapsed = clock_ns() - start;
        print(label, " ", sample, " ", elapsed / count, " ", checksum);
    }
}
fn listing(label: const u8[:], path: const u8[:], byte_limit: i64, count: i64) {
    var out:      fs::Entry[>..] = [];
    var checksum: i64            = 0;
    assert(fs::list(path, byte_limit, fs::MAX_ENTRIES, out).error == fs::Error.None);
    for sample in 7 {
        let start = clock_ns();
        for _ in count {
            assert(fs::list(path, byte_limit, fs::MAX_ENTRIES, out).error == fs::Error.None);
            for e in out { checksum += e.name.len; }
        }
        let elapsed = clock_ns() - start;
        print(label, " ", sample, " ", elapsed / count, " ", checksum);
    }
}
fn main() {
    let argv = args(); assert(argv.len == 3);
    let count, valid = parse_int(argv[2], 10); assert(valid && count > 0 && count <= 1000000);
    let empty = str(argv[1], "/empty"); reads("read-empty", empty, 0, count, fs::Error.None);
    let small = str(argv[1], "/small"); reads("read-small", small, 64, count, fs::Error.None);
    let large = str(argv[1], "/large"); reads("read-64k", large, 65536, count, fs::Error.None);
    let maximum = str(argv[1], "/maximum"); reads("read-1m", maximum, fs::MAX_BYTES, count, fs::Error.None);
    reads("read-overflow", small, 63, count, fs::Error.LimitExceeded);
    let deep = str(argv[1], "/d/d/d/d/d/d/d/d/d/d/d/d/small"); reads("read-deep", deep, 64, count, fs::Error.None);
    let narrow = str(argv[1], "/narrow"); listing("list-one", narrow, 12, count);
    listing("list-one-max-buffer", narrow, fs::MAX_BYTES, count);
    let wide = str(argv[1], "/wide"); listing("list-1000", wide, 12000, count);
    listing("list-1000-max-buffer", wide, fs::MAX_BYTES, count);
}
