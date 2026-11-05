// SPDX-License-Identifier: Apache-2.0
import fs from "..";
import std;
import os;
fn ok(s: fs::Status) { assert(s.error == fs::Error.None && s.os_error == 0); }
fn main() {
    let argv = args(); assert(argv.len == 3);
    let context, ce = fs::create_context(); ok(ce);
    let root, re = fs::open_root(context, argv[1]); ok(re);
    var out: u8[>..] = [];
    for n in [1, 2, 254, 255, 256, 257, 511, 512, 513, 4095] {
        if n == 4095 && argv[2] == "short" { continue; }
        let name = str("n", n); let path = str(argv[1], "/", name);
        var expected: u8[>..] = []; expected.resize(n, 'x');
        for limit in [0, n - 1, n, n + 1, fs::MAX_BYTES] {
            let a = fs::read_link(path, limit, out);
            if limit < n { assert(a.error == fs::Error.LimitExceeded && a.os_error == 0 && out.len == 0); }
            else { ok(a); assert(out == expected); }
            let b = fs::read_link_at(root, name, limit, out);
            if limit < n { assert(b.error == fs::Error.LimitExceeded && b.os_error == 0 && out.len == 0); }
            else { ok(b); assert(out == expected); }
        }
        var alias: u8[>..] = []; alias.append(path); ok(fs::read_link(alias[..], n, alias)); assert(alias == expected);
        alias.clear(); alias.append(name); ok(fs::read_link_at(root, alias[..], n, alias)); assert(alias == expected);
    }
    let binary: u8[] = ['.', '.', '/', 255, '\n'];
    ok(fs::read_link_at(root, "binary", 5, out)); assert(out == binary);
    ok(fs::read_link_at(root, "nested/link", 32, out)); assert(out == "../missing");
    for name in ["file", "nested", ".", "missing", "ancestor/link"] {
        var failure_out: u8[>..] = []; failure_out.append("sentinel");
        assert(fs::read_link_at(root, name, 32, failure_out).error == fs::Error.SystemError && failure_out.len == 0);
        failure_out.append("sentinel");
        let path: u8[>..] = if name == "." { str(argv[1]) } else { str(argv[1], "/", name) };
        assert(fs::read_link(path, 32, failure_out).error == fs::Error.SystemError && failure_out.len == 0);
    }
    for bad in ["", "..", "../x", "/x", "x/..", "x/./y", "x//y", "x/", "x\0y"] {
        var failure_out: u8[>..] = []; failure_out.append("sentinel");
        assert(fs::read_link_at(root, bad, 32, failure_out).error == fs::Error.InvalidInput && failure_out.len == 0);
    }
    for limit in [-1, fs::MAX_BYTES + 1] {
        var failure_out: u8[>..] = []; failure_out.append("sentinel");
        assert(fs::read_link_at(root, "n1", limit, failure_out).error == fs::Error.InvalidInput && failure_out.len == 0);
        failure_out.append("sentinel");
        assert(fs::read_link(str(argv[1], "/n1"), limit, failure_out).error == fs::Error.InvalidInput && failure_out.len == 0);
    }
    let raw_name: u8[] = [255, '\n'];
    ok(fs::read_link_at(root, raw_name, 32, out)); assert(out == "/outside/absent");
    ok(fs::read_link_at(root, "cycle", 32, out)); assert(out == "cycle");
    let file, fe = fs::open_file_at(root, "file", fs::OpenOptions { .. }); ok(fe);
    let wrong = fs::Root { context: context, id: file.id };
    assert(fs::read_link_at(wrong, "n1", 2, out).error == fs::Error.SystemError && out.len == 0);
    let held, he = fs::open_root_at(root, "nested"); ok(he);
    let renamed = fs::rename(str(argv[1], "/nested"), str(argv[1], "/moved"), fs::RenameOptions { .. }); ok(renamed.status);
    ok(fs::read_link_at(held, "link", 32, out)); assert(out == "../missing");
    ok(fs::read_link_at(root, "moved/link", 32, out)); assert(out == "../missing");
    ok(fs::close_root(root));
    assert(fs::read_link_at(root, "n1", 2, out).error == fs::Error.SystemError && out.len == 0);
    ok(fs::close_context(context));
    print("bounded read_link/read_link_at bytes, boundaries, aliasing, strict parents and lifetimes passed");
}
