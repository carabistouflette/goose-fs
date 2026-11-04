// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn main() {
    let argv = args(); assert(argv.len == 2);
    var data: u8[>..] = []; assert(read_file(argv[1], data));
    var out:  u8[>..] = []; var position: i64 = 0;
    while position < data.len {
        assert(position + 2 <= data.len);
        let length = data[position] + (data[position + 1] as i64) * 256;
        position += 2; assert(length <= data.len - position);
        let path: const u8[:] = data[position..position + length];
        out.push(if fs::valid_path(path) { 1 } else { 0 });
        out.push(if fs::valid_relative(path) { 1 } else { 0 });
        position += length;
    }
    write_stdout(out);
}
