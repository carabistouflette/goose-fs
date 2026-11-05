#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Paired warm-cache listing costs, including long names and exact/oversized budgets."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import tempfile
from compare.provenance import goose_stdlib
from listing_provenance import sources
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tests'))
from listing_fixture import names_for_bytes
if not __debug__:raise SystemExit('benchmark validation requires Python assertions; disable optimization')
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--goose',required=True)
p.add_argument('--cc',default='gcc')
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--baseline-revision',required=True)
p.add_argument('--full',type=Path,required=True)
p.add_argument('--adaptive',type=Path)
p.add_argument('--identical-control',action='store_true')
p.add_argument('--rounds',type=int,default=5)
p.add_argument('--iterations',type=int,default=5)
p.add_argument('--creation-order',choices=['natural','shuffled'],default='natural')
p.add_argument('--output',type=Path,required=True)
p.add_argument('--build-manifest',type=Path,required=True)
a=p.parse_args()
if a.identical_control and os.path.lexists(a.output):p.error('control output already exists; choose a new output path')
if not 1<=a.rounds<=100 or not 1<=a.iterations<=1000000:p.error('invalid rounds/iterations')
a.output.parent.mkdir(parents=True,exist_ok=True)
def capture(args):return subprocess.check_output(args,cwd=ROOT,text=True,timeout=30).strip()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
if a.identical_control and a.adaptive is not None:p.error('--adaptive is not used in identical-control mode')
if a.identical_control and a.adaptive is not None:p.error('--adaptive is not used in identical-control mode')
if not a.identical_control and a.adaptive is None:p.error('--adaptive is required outside identical-control mode')
binaries={'a':a.baseline.resolve(),'b':a.full.resolve()} if a.identical_control else {'baseline':a.baseline.resolve(),'full':a.full.resolve(),'adaptive':a.adaptive.resolve()}
control_lock=None
if a.identical_control:
    control_lock=(a.build_manifest.resolve().parent/'build.lock').open('a')
    fcntl.flock(control_lock,fcntl.LOCK_SH)
    assert binaries=={k:a.build_manifest.resolve().parent/k for k in ('a','b')}, 'control binaries must share their manifest directory'
initial_sources=sources();initial_bins={k:digest(v) for k,v in binaries.items()}
build=json.loads(a.build_manifest.read_text())
assert (build.get('profile')=='identical-control')==a.identical_control
if a.identical_control:
    assert build['identical_executables'] and build['identical_sections']
    assert initial_bins['a']==initial_bins['b']
    assert build['cc_sha256']==digest(build['cc_path'])
    assert str(Path(shutil.which(a.cc) or a.cc).resolve())==build['cc_path'], 'C compiler identity mismatch'
assert build['sources_sha256']==initial_sources and build['binaries_sha256']==initial_bins
assert build['baseline_revision']==a.baseline_revision
cc=build['cc_path'] if a.identical_control else a.cc
assert build['cc']==capture([cc,'--version'])
rendered={name:digest(a.build_manifest.parent/name) for name in build['rendered_sources_sha256']}
assert rendered==build['rendered_sources_sha256']
initial_revision=capture(['git','rev-parse','HEAD']);initial_dirty=bool(capture(['git','status','--porcelain']))
goose=str(Path(a.goose).resolve());compiler_hash=digest(goose)
assert build['goose_sha256']==compiler_hash
assert build['goose_stdlib']==goose_stdlib(goose)
load_start=os.getloadavg();started=datetime.datetime.now(datetime.timezone.utc).isoformat();rows=[];fixtures={}
rng=random.Random(61937)
fixture_rng=random.Random(61938)
with tempfile.TemporaryDirectory(prefix='goose-fs-listing-bench-') as temp:
    base=Path(temp);cases=[]
    # One short name costs12 bytes; short4096 uses the same10-byte name family.
    for label,size in [('empty',0),('one',12),('short4096',49152),('prefix255',4080*257),('below64k',65535),('at64k',65536),('above64k',65537),('above128k',131073),('above512k',524289),('max1m',1048576)]:
        path=base/label;path.mkdir()
        names=[f'entry-{i:04d}'.encode() for i in range(4096)] if label=='short4096' else [b'x'*250+f'{i:05d}'.encode() for i in range(4080)] if label=='prefix255' else names_for_bytes(size)
        creation=names.copy()
        if a.creation_order=='shuffled':fixture_rng.shuffle(creation)
        for name in creation:
            fd=os.open(os.fsencode(path)+b'/'+name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        expected=b''.join(n+b'\0' for n in sorted(names))
        fixtures[label]=dict(packed_bytes=size,entries=len(names),sorted_names_sha256=hashlib.sha256(expected).hexdigest(),
                             creation_names_sha256=hashlib.sha256(b'\0'.join(creation)).hexdigest(),unsorted_preflight_sha256={})
        signature=len(names)+sum(len(n)+n[0]+n[-1] for n in names)
        for budget in sorted({size,1048576}):
            for api,api_name in enumerate(['absolute','absolute-sorted','root','root-sorted']):
                key=f'{label}/{budget}/{api_name}'
                cases.append((key,path,budget,api,signature))
                # Complete independent filename checks outside every timed series.
                for variant,binary in binaries.items():
                    got=subprocess.check_output([str(binary),str(path),str(budget),str(api),'0'],timeout=30)
                    if not api%2:fixtures[label]['unsorted_preflight_sha256'][f'{budget}/{api_name}/{variant}']=hashlib.sha256(got).hexdigest()
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
assert capture([cc,'--version'])==build['cc']
assert build['goose_stdlib']==goose_stdlib(goose)
if a.identical_control:assert build['cc_sha256']==digest(build['cc_path'])
assert {name:digest(a.build_manifest.parent/name) for name in rendered}==rendered
metadata=dict(profile='identical-control' if a.identical_control else 'listing-comparison',started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              platform=platform.platform(),cpu_info=Path('/proc/cpuinfo').read_text().split('\n\n')[0],filesystem=filesystem,
              cpu_affinity=sorted(os.sched_getaffinity(0)),loadavg_start=load_start,loadavg_end=os.getloadavg(),
              source_revision=initial_revision,source_dirty=initial_dirty,baseline_revision=a.baseline_revision,
              sources_sha256=initial_sources,binaries_sha256=initial_bins,binaries_paths={k:str(v) for k,v in binaries.items()},goose=capture([goose,'--version']),
              goose_sha256=compiler_hash,build_manifest=build,goose_revision=(ROOT/'GOOSE_REVISION').read_text().strip(),
              cc=capture([cc,'--version']),flags=['-O2'],shuffle_seed=61937,rounds=a.rounds,iterations=a.iterations,
              creation_order=a.creation_order,creation_shuffle_seed=61938,
              runtime_environment={key:os.environ.get(key) for key in ['LD_PRELOAD','GLIBC_TUNABLES','MALLOC_CONF']},
              fixtures=fixtures,samples=rows)
if a.identical_control:
    with a.output.open('x') as stream:stream.write(json.dumps(metadata,indent=2)+'\n')
else:a.output.write_text(json.dumps(metadata,indent=2)+'\n')
print(f'Wrote {len(rows)} checked samples to {a.output}')
