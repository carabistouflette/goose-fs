#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent byte oracle for the documented Goose path grammar.

Replays a directory of raw path inputs through a built path_grammar target and
compares every verdict with this module's own implementation of the documented
rule. It shares no code with fs.goose, and it is not Rust Path normalization:
the rule is the component grammar in docs/API.md and docs/ROOTS.md.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_PATH_BYTES = 4095


def expected(path, relative):
    """Documented verdict for one raw byte string."""
    if not 1 <= len(path) <= MAX_PATH_BYTES or b'\0' in path:
        return False
    if relative:
        if path == b'.':
            return True
        if path.startswith(b'/'):
            return False
        parts = path.split(b'/')
    else:
        if path == b'/':
            return True
        if not path.startswith(b'/'):
            return False
        parts = path[1:].split(b'/')
    return all(part not in (b'', b'.', b'..') for part in parts)


def main():
    if len(sys.argv) < 3:
        raise SystemExit('usage: path_oracle.py <path-grammar-binary> <corpus-dir>...')
    binary, corpora = Path(sys.argv[1]).resolve(), [Path(arg) for arg in sys.argv[2:]]
    if not binary.is_file():
        raise SystemExit('missing path_grammar binary: ' + str(binary))
    inputs = sorted({path.read_bytes() for corpus in corpora
                     for path in corpus.iterdir() if path.is_file()})
    if not inputs:
        raise SystemExit('empty corpus: nothing to replay')
    for data in inputs:
        if len(data) > 0xFFFF:
            raise SystemExit('corpus input exceeds the 16-bit fixture length')
    fixture = b''.join(len(data).to_bytes(2, 'little') + data for data in inputs)
    with tempfile.NamedTemporaryFile(prefix='goose-fs-path-oracle-') as handle:
        handle.write(fixture)
        handle.flush()
        result = subprocess.run([str(binary), handle.name], capture_output=True, timeout=120)
    if result.returncode != 0:
        raise SystemExit('path_grammar target failed: ' + result.stderr.decode('utf8', 'replace')[-2000:])
    verdicts = result.stdout
    if len(verdicts) != 2 * len(inputs):
        raise SystemExit(f'expected {2 * len(inputs)} verdict bytes, got {len(verdicts)}')
    mismatches = []
    for index, data in enumerate(inputs):
        for offset, relative in ((0, False), (1, True)):
            actual = verdicts[2 * index + offset] == 1
            if actual != expected(data, relative):
                mismatches.append((data, relative, actual))
    print(f'{len(inputs)} corpus inputs, {2 * len(inputs)} verdicts, {len(mismatches)} mismatches')
    for data, relative, actual in mismatches[:10]:
        print(f'  mismatch relative={relative} actual={actual} len={len(data)} input={data[:80]!r}')
    return 1 if mismatches else 0


if __name__ == '__main__':
    sys.exit(main())
