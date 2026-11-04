#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build old library sources with the current benchmark harness for comparison."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--revision', required=True, help='full trusted source commit')
p.add_argument('--goose', required=True)
p.add_argument('--cc', default='gcc')
p.add_argument('--output', type=Path, required=True)
p.add_argument('--harness', type=Path, default=ROOT/'bench/bench.goose', help='current Goose harness importing the library from ..')
a = p.parse_args()
if not re.fullmatch('[0-9a-f]{40}', a.revision): p.error('revision must be a full lowercase commit hash')
compiler = str(Path(a.goose).resolve())
target = a.output.resolve()
(ROOT/'.build').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='baseline-source-', dir=ROOT/'.build') as temp:
    exported = Path(temp)
    native = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', a.revision, '--', 'native'], cwd=ROOT, timeout=30).decode().splitlines()
    for name in ['fs.goose', 'fs.build', *native]:
        path = exported/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(subprocess.check_output(['git', 'show', f'{a.revision}:{name}'], cwd=ROOT, timeout=30))
    (exported/'bench').mkdir()
    (exported/'bench/bench.goose').write_bytes(a.harness.read_bytes())
    subprocess.run([compiler, 'build', str(exported/'bench/bench.goose'), '--cc', a.cc,
                    '-O2', '-o', str(target)], cwd=ROOT, check=True, timeout=120)
