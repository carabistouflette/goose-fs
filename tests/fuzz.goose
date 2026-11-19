// SPDX-License-Identifier: Apache-2.0
// Test-only entry points for the libFuzzer host. Each call owns its values and
// no input reaches the filesystem: only the pure path predicates and the
// InvalidInput branches that return before any native call are exercised.
import fs from "..";
import std;

// Second, split-based implementation of the documented component rule. It is
// deliberately not the library's index scan, so agreement is a real check.
fn component_ok(part: const u8[:]) -> bool {
    if part.len == 0 { return false; }
    if part.len == 1 && part[0] == '.' { return false; }
    return !(part.len == 2 && part[0] == '.' && part[1] == '.');
}
fn contract_valid(path: const u8[:], relative: bool) -> bool {
    if path.len < 1 || path.len > fs::MAX_PATH_BYTES { return false; }
    for c in path { if c == 0 { return false; } }
    var body: const u8[:] = path;
    if relative {
        if path[0] == '/' { return false; }
        if path == "." { return true; }
    } else {
        if path[0] != '/' { return false; }
        if path.len == 1 { return true; }
        body = path[1..];
    }
    var start: i64 = 0;
    for c, i in body {
        if c == '/' {
            if !component_ok(body[start..i]) { return false; }
            start = i + 1;
        }
    }
    return component_ok(body[start..]);
}
fn extended(source: const u8[:], suffix: const u8[:]) -> u8[] {
    var result: u8[>..] = [];
    result.append(source);
    result.append(suffix);
    return result;
}
// Invalid paths with otherwise valid limits must be rejected before native I/O,
// and nonempty outputs must be cleared. Identical-error predicate order is not
// distinguishable through this API. The C host traps any native boundary call.
fn invalid_priority(path: const u8[:]) {
    var bytes: u8[>..] = [];
    bytes.push(0xa5);
    assert(fs::read(path, 0, bytes).error == fs::Error.InvalidInput && bytes.len == 0);
    var entries: fs::Entry[>..] = [];
    entries.push(fs::Entry { .. });
    assert(fs::list(path, 0, 0, entries).error == fs::Error.InvalidInput && entries.len == 0);
    var info = fs::Metadata { .. };
    assert(fs::metadata(path, info).error == fs::Error.InvalidInput);
    assert(fs::create_file(path, "").error == fs::Error.InvalidInput);
    assert(fs::remove_file(path).error == fs::Error.InvalidInput);
}
export fn fuzz_check(source: const u8[:]) -> i64 {
    let absolute = fs::valid_path(source);
    let relative = fs::valid_relative(source);
    assert(absolute == contract_valid(source, false));
    assert(relative == contract_valid(source, true));
    if relative { assert(source[0] != '/'); }
    if absolute {
        assert(source.len <= fs::MAX_PATH_BYTES && source[0] == '/');
        assert(find(source, "\0") < 0);
        if source.len > 1 {
            assert(absolute == fs::valid_components(source, 1));
            assert(absolute == fs::valid_relative(source[1..]));
        }
        // Appending one ordinary component preserves validity; a trailing
        // separator or a dot component never does.
        if source != "/" && source.len + 2 <= fs::MAX_PATH_BYTES {
            assert(fs::valid_path(extended(source, "/x")));
        }
        if source.len + 1 <= fs::MAX_PATH_BYTES { assert(!fs::valid_path(extended(source, "/"))); }
        if source.len + 3 <= fs::MAX_PATH_BYTES { assert(!fs::valid_path(extended(source, "/."))); }
        if source.len + 4 <= fs::MAX_PATH_BYTES { assert(!fs::valid_path(extended(source, "/.."))); }
    } else {
        invalid_priority(source);
    }
    return 0;
}
// The C host uses this only to prove Goose failures reach libFuzzer and save
// the exact triggering input before the actual campaign starts.
export fn fuzz_assertion_probe(value: i64) { assert(value != 0); }
fn main() {}
