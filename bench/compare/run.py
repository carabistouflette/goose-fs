#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Shuffled native-API task-cost comparison; policies intentionally remain visible."""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import subprocess
import tempfile
from provenance import ROOT, RUNNERS, runtime_settings, sha256, sources, toolchains
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--goose',required=True)
p.add_argument('--cc',default='gcc')
p.add_argument('--rust-toolchain',default='1.99.1')
p.add_argument('--iterations',type=int,default=100)
p.add_argument('--rounds',type=int,default=3)
p.add_argument('--seed',type=int,default=20261104)
p.add_argument('--timeout',type=float,default=300)
p.add_argument('--output',type=Path,default=ROOT/'.build/compare/native-api.json')
a=p.parse_args()
if not 1<=a.iterations<=1000000: p.error('iterations must be1..1000000')
if not 1<=a.rounds<=100: p.error('rounds must be1..100')
if not math.isfinite(a.timeout) or a.timeout<=0: p.error('timeout must be finite and positive')
runners=list(RUNNERS)
paths={name:ROOT/'.build/compare'/name for name in runners}
for path in paths.values():
    if not path.is_file(): p.error(f'missing binary {path}; run bench/compare/build.py')
try:
    build=json.loads((ROOT/'.build/compare/build.json').read_text())
except (OSError,ValueError) as error:
    p.error(f'missing/invalid build manifest; rebuild runners: {error}')
def verify_build():
    if (build.get('schema')!=1 or build.get('source_sha256')!=sources()
        or build.get('binaries_sha256')!={name:sha256(path) for name,path in paths.items()}
        or build.get('toolchains')!=toolchains(str(Path(a.goose).resolve()),a.cc,a.rust_toolchain)):
        p.error('build source, binary or toolchain mismatch; rebuild runners with the requested toolchains')
verify_build()
runtime=runtime_settings()
read_sizes=[0,64,4096,65536,1048576]
list_sizes=[0,1,128,4096]
expected={}
for size in read_sizes:
    value=size+(13+((size-1)*17+13)%251 if size else 0)
    for mode in ['fresh','reuse','retained']: expected[f'read-{mode}-{size}']=value
for count in list_sizes:
    expected[f'list-sorted-{count}']=sum(159+i%10 for i in range(count))
expected.update({'metadata-file':65,'is-dir':1})
def capture(args): return subprocess.check_output(args,cwd=ROOT,text=True,timeout=30).strip()
def execute(name,root,iterations):
    result=subprocess.run([str(paths[name]),str(root),str(iterations)],cwd=ROOT,capture_output=True,text=True,check=True,timeout=a.timeout)
    rows=[];seen=set();rss=None
    for line in result.stdout.splitlines():
        if line.startswith('MEMORY\t'):
            found=re.fullmatch(r'MEMORY\tVmHWM:\s+(\d+)\s+kB',line)
            assert found and rss is None,line
            rss=int(found[1]);continue
        workload,sample,ns,checksum,state=line.split('\t')
        key=(workload,int(sample))
        assert workload in expected and key not in seen and 0<=int(sample)<7,key
        seen.add(key)
        unsupported=name=='goose-stdlib' and (workload=='metadata-file' or workload.startswith('read-retained-'))
        assert state==('unsupported' if unsupported else 'ok'),(name,line)
        assert int(ns)>=0 and int(checksum)==(0 if unsupported else expected[workload]*iterations),(name,line)
        rows.append(dict(workload=workload,sample=int(sample),ns_per_call=None if unsupported else int(ns),checksum=int(checksum),state=state))
    assert len(seen)==len(expected)*7 and rss is not None,(name,len(seen),rss,result.stderr)
    return rows,rss
samples=[];batches=[];rng=random.Random(a.seed);load_start=os.getloadavg()
with tempfile.TemporaryDirectory(prefix='goose-fs-compare-') as temp:
    root=Path(temp)
    fixture_hashes={}
    for size in read_sizes:
        content=bytes((i*17+13)%251 for i in range(size))
        (root/f'read-{size}').write_bytes(content)
        fixture_hashes[f'read-{size}']=hashlib.sha256(content).hexdigest()
    for count in list_sizes:
        folder=root/f'list-{count}';folder.mkdir()
        names=[f'entry-{i:04d}' for i in range(count)];rng.shuffle(names)
        for name in names: (folder/name).touch()
        fixture_hashes[f'list-{count}']=hashlib.sha256(b'\0'.join(n.encode() for n in sorted(names))).hexdigest()
    filesystem=capture(['stat','-f','-c','%T',str(root)])
    # Full content and ordered-name validation happens in every runner outside timers.
    for name in runners: execute(name,root,1)
    for round_id in range(a.rounds):
        order=runners.copy();rng.shuffle(order)
        for position,name in enumerate(order):
            rows,rss=execute(name,root,a.iterations)
            batches.append(dict(round=round_id,position=position,runner=name,peak_rss_kib=rss))
            for row in rows: samples.append(dict(round=round_id,position=position,runner=name,**row))
            print(f'round {round_id+1}/{a.rounds}: {name} complete',flush=True)
verify_build()
metadata=dict(profile='native-public-api-task-costs',timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    source_revision=capture(['git','rev-parse','HEAD']),source_dirty=bool(capture(['git','status','--porcelain'])),
    build=build,runtime_settings=runtime,
    platform=platform.platform(),cpu_info=Path('/proc/cpuinfo').read_text().split('\n\n')[0],filesystem=filesystem,
    cpu_affinity=sorted(os.sched_getaffinity(0)),loadavg_start=load_start,loadavg_end=os.getloadavg(),
    iterations=a.iterations,rounds=a.rounds,seed=a.seed,fixtures_sha256=fixture_hashes,
    listing_limits={'goose-fs':{'byte_limit':1048576,'entry_limit':4096}},
    metadata_consumption='All callers test regular kind and size; Rust/Go additionally retain full native metadata objects, Goose may elide unused wrapper fields.',
    policies={
      'goose-fs':'absolute strict paths; all-component nofollow; bounded regular reads; clear-on-error; retained read_at holds Context+entry read locks; owned sorted entries plus kind hints; nofollow metadata',
      'goose-stdlib':'cwd-compatible paths; follows links; unbounded append-to-builder whole read reset by runner; sorted newline names; no general metadata',
      'rust':'std::fs::read fresh; File+read_to_end reused; retained FileExt::read_at; std::fs::read_dir+owned OsString sort; symlink_metadata; Path::is_dir; normal link-following traversal',
      'go':'os.ReadFile fresh; os.Open+File.Read reused; retained File.ReadAt; os.ReadDir sorted DirEntry; os.Lstat; os.Stat; normal link-following traversal'},
    limitation='Trusted stable ASCII fixtures; public native API semantics differ. Not an equal-security ranking. No durability/cold-storage/concurrency claim. Whole-process batches shuffled; allocator state retained between workloads. Timed checksums consume length and endpoint bytes; independent full-content/ordered-name preflight outside timers. Fresh timed reads do not receive a full-content postcheck. VmHWM sampled after all workloads includes validation and retained sinks; not per-operation memory or allocations.',
    samples=samples,batches=batches)
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(metadata,indent=2)+'\n')
print(f'Wrote {len(samples)} samples to {a.output}')
