#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Require compiler rejection for inputs borrowed from replaced outputs."""
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parent.parent
CASES = {
    'read-path': '''var out = str("/tmp/path");
        let view: const u8[:] = out[..];
        let s = fs::read(view, 100, out); print(s.os_error);''',
    'list-path': '''var entries: fs::Entry[>..] = [];
        entries.push(fs::Entry { kind: fs::Kind.File, name: "/tmp/path" });
        for entry in entries {
            let s = fs::list(entry.name, 100, 10, entries); print(s.os_error);
        }''',
    'sorted-path': '''var entries: fs::Entry[>..] = [];
        entries.push(fs::Entry { kind: fs::Kind.File, name: "/tmp/path" });
        for entry in entries { let s = fs::list_sorted(entry.name, 100, 10, entries); print(s.os_error); }''',
    'constant': '''let bound .= fs::MAX_BYTES; bound = 1;''',
}
for name, body in CASES.items():
    path = ROOT / '.build' / f'reject-{name}.goose'
    path.write_text('import fs from "..";\nimport std;\nfn main() {\n'+body+'\n}\n')
    result = subprocess.run([sys.argv[1], 'check', str(path)], capture_output=True, text=True, timeout=30)
    assert result.returncode != 0, f'{name}: invalid consumer accepted'
    if name != 'constant':
        assert '§5.1' in result.stderr and ('shrinks' in result.stderr or 'cannot clear' in result.stderr or 'cannot resize' in result.stderr), result.stderr
    else:
        assert 'const' in result.stderr, result.stderr
print('4 ownership/constant rejection cases passed')
