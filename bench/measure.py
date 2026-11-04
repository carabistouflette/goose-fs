#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Record raw warm-cache samples, optionally interleaving a preserved baseline."""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--goose', required=True)
p.add_argument('--cc', required=True)
p.add_argument('--timeout', type=float, default=3600, help='timeout per benchmark batch in seconds')
p.add_argument('--iterations', type=int, default=100)
p.add_argument('--binary', type=Path, default=ROOT/'.build/bench')
p.add_argument('--baseline', type=Path)
p.add_argument('--baseline-revision', help='source revision of the preserved baseline binary')
p.add_argument('--rounds', type=int, default=3)
p.add_argument('--output', type=Path, default=ROOT/'.build/bench.json')
a = p.parse_args()
if not math.isfinite(a.timeout) or a.timeout <= 0: p.error('timeout must be finite and positive')
if not 1 <= a.iterations <= 1000000: p.error('iterations must be 1..1000000')
if not 1 <= a.rounds <= 100: p.error('rounds must be 1..100')
if a.baseline and not a.baseline_revision: p.error('--baseline requires --baseline-revision')
def output(args): return subprocess.check_output(args, cwd=ROOT, text=True, timeout=30).strip()
binaries = {'candidate': a.binary.resolve()}
if a.baseline: binaries['baseline'] = a.baseline.resolve()
load_start = os.getloadavg()
rows = []
reference = None
with tempfile.TemporaryDirectory(prefix='goose-fs-bench-') as temp:
    root = Path(temp)
    for name, size in [('empty',0), ('small',64), ('large',65536), ('maximum',1048576)]:
        (root/name).write_bytes(b'x'*size)
    filesystem = output(['stat', '-f', '-c', '%T', str(root)])
    deep = root.joinpath(*(['d']*12)); deep.mkdir(parents=True); (deep/'small').write_bytes(b'x'*64)
    for name, count in [('narrow',1), ('wide',1000)]:
        (root/name).mkdir()
        for i in range(count): (root/name/f'entry-{i:04d}').touch()
    for round_id in range(a.rounds if a.baseline else 1):
        order = ['baseline', 'candidate'] if a.baseline else ['candidate']
        if round_id % 2: order.reverse()
        for variant in order:
            raw = subprocess.check_output([str(binaries[variant]), str(root), str(a.iterations)],
                                          cwd=ROOT, text=True, timeout=a.timeout)
            batch = []
            signatures = {}
            for line in raw.splitlines():
                workload, sample, ns, checksum = line.split()
                key = (workload, int(sample))
                assert key not in signatures and 0 <= int(sample) < 7
                assert int(ns) >= 0
                signatures[key] = int(checksum)
                batch.append(dict(variant=variant, round=round_id, workload=workload,
                                  sample=int(sample), ns_per_call=int(ns), checksum=int(checksum)))
            assert len(batch) == 105 and len({r['workload'] for r in batch}) == 15
            if reference is None: reference = signatures
            assert signatures == reference, 'baseline/candidate workloads or checksums differ'
            rows.extend(batch)
metadata = dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                platform=platform.platform(), machine=platform.machine(), cpu=platform.processor(), filesystem=filesystem,
                cpu_info=Path('/proc/cpuinfo').read_text().split('\n\n')[0],
                goose=output([a.goose,'--version']), goose_revision=(ROOT/'GOOSE_REVISION').read_text().strip(),
                cc=output([a.cc,'--version']), flags=['-O2'], iterations=a.iterations,
                source_revision=output(['git','rev-parse','HEAD']), baseline_revision=a.baseline_revision,
                binary_sha256={name: hashlib.sha256(path.read_bytes()).hexdigest() for name,path in binaries.items()},
                harness_sha256=hashlib.sha256((ROOT/'bench/bench.goose').read_bytes()).hexdigest(),
                loadavg_start=load_start, loadavg_end=os.getloadavg(),
                cpu_affinity=sorted(os.sched_getaffinity(0)),
                source_dirty=bool(output(['git','status','--porcelain'])), samples=rows)
a.output.write_text(json.dumps(metadata, indent=2)+'\n')
print(f'Wrote {len(rows)} samples to {a.output}')
