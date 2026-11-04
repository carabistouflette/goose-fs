#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Record seven raw samples per public-interface workload; no timing threshold."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--goose', required=True)
p.add_argument('--cc', required=True)
p.add_argument('--timeout', type=float, default=3600, help='benchmark timeout in seconds')
p.add_argument('--iterations', type=int, default=100)
a = p.parse_args()
if not a.timeout > 0: p.error('timeout must be positive')
if not 1 <= a.iterations <= 1000000: p.error('iterations must be 1..1000000')
def output(args): return subprocess.check_output(args, cwd=ROOT, text=True, timeout=30).strip()
with tempfile.TemporaryDirectory(prefix='goose-fs-bench-') as temp:
    root = Path(temp)
    for name, size in [('empty',0), ('small',64), ('large',65536), ('maximum',1048576)]:
        (root/name).write_bytes(b'x'*size)
    filesystem = output(['stat', '-f', '-c', '%T', str(root)])
    deep = root.joinpath(*(['d']*12)); deep.mkdir(parents=True); (deep/'small').write_bytes(b'x'*64)
    for name, count in [('narrow',1), ('wide',1000)]:
        (root/name).mkdir()
        for i in range(count): (root/name/f'entry-{i:04d}').touch()
    raw = subprocess.check_output([str(ROOT/'.build/bench'), str(root), str(a.iterations)], cwd=ROOT, text=True, timeout=a.timeout)
rows = []
for line in raw.splitlines():
    workload, sample, ns, checksum = line.split()
    rows.append(dict(workload=workload, sample=int(sample), ns_per_call=int(ns), checksum=int(checksum)))
assert len(rows) == 112
metadata = dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                platform=platform.platform(), machine=platform.machine(), cpu=platform.processor(), filesystem=filesystem,
                cpu_info=Path('/proc/cpuinfo').read_text().split('\n\n')[0],
                goose=output([a.goose,'--version']), goose_revision=(ROOT/'GOOSE_REVISION').read_text().strip(),
                cc=output([a.cc,'--version']), flags=['-O2'], iterations=a.iterations,
                source_revision=output(['git','rev-parse','HEAD']),
                source_dirty=bool(output(['git','status','--porcelain'])), samples=rows)
(ROOT/'.build/bench.json').write_text(json.dumps(metadata, indent=2)+'\n')
print(f'Wrote {len(rows)} samples to .build/bench.json')
