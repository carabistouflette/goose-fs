#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Paired warm-cache listing costs, including long names and exact/oversized budgets."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import tempfile
from compare.provenance import goose_stdlib
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tests'))
from listing_fixture import names_for_bytes
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--goose',required=True)
p.add_argument('--cc',default='gcc')
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--baseline-revision',required=True)
p.add_argument('--full',type=Path,required=True)
p.add_argument('--adaptive',type=Path,required=True)
p.add_argument('--rounds',type=int,default=5)
p.add_argument('--iterations',type=int,default=5)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--build-manifest',type=Path,required=True)
a=p.parse_args()
if not 1<=a.rounds<=100 or not 1<=a.iterations<=1000000:p.error('invalid rounds/iterations')
a.output.parent.mkdir(parents=True,exist_ok=True)
def capture(args):return subprocess.check_output(args,cwd=ROOT,text=True,timeout=30).strip()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sources():
    paths=[ROOT/'fs.goose',ROOT/'fs.build',ROOT/'GOOSE_REVISION',*sorted((ROOT/'native').glob('*')),
           ROOT/'bench/listing.goose.in',Path(__file__).resolve(),ROOT/'tests/listing_fixture.py',ROOT/'bench/build-baseline.py',ROOT/'bench/listing-build.py',ROOT/'bench/compare/provenance.py']
    return {str(path.relative_to(ROOT)):digest(path) for path in paths if path.is_file()}
binaries={'baseline':a.baseline.resolve(),'full':a.full.resolve(),'adaptive':a.adaptive.resolve()}
initial_sources=sources();initial_bins={k:digest(v) for k,v in binaries.items()}
build=json.loads(a.build_manifest.read_text())
assert build['sources_sha256']==initial_sources and build['binaries_sha256']==initial_bins
assert build['baseline_revision']==a.baseline_revision
assert build['cc']==capture([a.cc,'--version'])
rendered={name:digest(a.build_manifest.parent/name) for name in build['rendered_sources_sha256']}
assert rendered==build['rendered_sources_sha256']
initial_revision=capture(['git','rev-parse','HEAD']);initial_dirty=bool(capture(['git','status','--porcelain']))
goose=str(Path(a.goose).resolve());compiler_hash=digest(goose)
assert build['goose_sha256']==compiler_hash
assert build['goose_stdlib']==goose_stdlib(goose)
load_start=os.getloadavg();started=datetime.datetime.now(datetime.timezone.utc).isoformat();rows=[];fixtures={}
rng=random.Random(61937)
with tempfile.TemporaryDirectory(prefix='goose-fs-listing-bench-') as temp:
    base=Path(temp);cases=[]
    # One short name costs12 bytes; short4096 uses the same10-byte name family.
    for label,size in [('empty',0),('one',12),('short4096',49152),('prefix255',4080*257),('below64k',65535),('at64k',65536),('above64k',65537),('above128k',131073),('above512k',524289),('max1m',1048576)]:
        path=base/label;path.mkdir()
        names=[f'entry-{i:04d}'.encode() for i in range(4096)] if label=='short4096' else [b'x'*250+f'{i:05d}'.encode() for i in range(4080)] if label=='prefix255' else names_for_bytes(size)
        for name in names:
            fd=os.open(os.fsencode(path)+b'/'+name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        expected=b''.join(n+b'\0' for n in sorted(names))
        fixtures[label]=dict(packed_bytes=size,entries=len(names),sorted_names_sha256=hashlib.sha256(expected).hexdigest())
        signature=len(names)+sum(len(n)+n[0]+n[-1] for n in names)
        for budget in sorted({size,1048576}):
            for api,api_name in enumerate(['absolute','absolute-sorted','root','root-sorted']):
                key=f'{label}/{budget}/{api_name}'
                cases.append((key,path,budget,api,signature))
                # Complete independent filename checks outside every timed series.
                for binary in binaries.values():
                    got=subprocess.check_output([str(binary),str(path),str(budget),str(api),'0'],timeout=30)
                    entries=got.split(b'\0');assert entries.pop()==b''
                    assert (entries if api%2 else sorted(entries))==sorted(names),(binary,key)
    filesystem=capture(['stat','-f','-c','%T',str(base)])
    jobs=[(variant,case) for variant in binaries for case in cases]
    for round_id in range(a.rounds):
        rng.shuffle(jobs)
        for variant,(key,path,budget,api,signature) in jobs:
            raw=subprocess.check_output([str(binaries[variant]),str(path),str(budget),str(api),str(a.iterations)],text=True,timeout=60)
            lines=raw.splitlines();assert len(lines)==7
            for sample,line in enumerate(lines):
                number,ns,checksum=map(int,line.split())
                assert number==sample and ns>=0 and checksum==(sample+1)*a.iterations*signature,(key,line)
                rows.append(dict(variant=variant,round=round_id,workload=key,sample=sample,ns_per_call=ns,checksum=checksum))
        print(f'finished paired round {round_id+1}/{a.rounds}',flush=True)
assert sources()==initial_sources and {k:digest(v) for k,v in binaries.items()}==initial_bins
assert capture(['git','rev-parse','HEAD'])==initial_revision and digest(goose)==compiler_hash
assert capture([a.cc,'--version'])==build['cc']
assert build['goose_stdlib']==goose_stdlib(goose)
assert {name:digest(a.build_manifest.parent/name) for name in rendered}==rendered
metadata=dict(started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              platform=platform.platform(),cpu_info=Path('/proc/cpuinfo').read_text().split('\n\n')[0],filesystem=filesystem,
              cpu_affinity=sorted(os.sched_getaffinity(0)),loadavg_start=load_start,loadavg_end=os.getloadavg(),
              source_revision=initial_revision,source_dirty=initial_dirty,baseline_revision=a.baseline_revision,
              sources_sha256=initial_sources,binaries_sha256=initial_bins,goose=capture([goose,'--version']),
              goose_sha256=compiler_hash,build_manifest=build,goose_revision=(ROOT/'GOOSE_REVISION').read_text().strip(),
              cc=capture([a.cc,'--version']),flags=['-O2'],shuffle_seed=61937,rounds=a.rounds,iterations=a.iterations,
              runtime_environment={key:os.environ.get(key) for key in ['LD_PRELOAD','GLIBC_TUNABLES','MALLOC_CONF']},
              fixtures=fixtures,samples=rows)
a.output.write_text(json.dumps(metadata,indent=2)+'\n')
print(f'Wrote {len(rows)} checked samples to {a.output}')
