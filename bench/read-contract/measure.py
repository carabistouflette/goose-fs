#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Record the first two bounded-read attempts; never replace failed controls."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
from build import ROOT,LABELS,PAIRS,capture,inputs,tools,sha256,runtime_settings
from conformance import fixtures,check_release,check_faults

def validate(out,manifest):
    assert manifest['schema']==1 and manifest['profile']=='bounded-read-contract'
    assert not manifest['source_dirty'], 'freeze a clean checkpoint before recording'
    assert manifest['source_revision']==capture(['git','rev-parse','HEAD'])
    assert manifest['sources_sha256']==inputs(), 'source bytes changed'
    assert not capture(['git','status','--porcelain']), 'recording requires a clean checkout'
    assert manifest['replica_pairs']==[list(p) for p in PAIRS]
    assert manifest['identical_executables'] and manifest['identical_sections']
    assert set(manifest['binaries_sha256'])==set(LABELS)
    assert set(manifest['sections_sha256'])==set(LABELS)
    assert set(manifest['fault_binaries_sha256'])=={'fs-fault','rust-fault','go-fault'}
    for group in ('binaries_sha256','fault_binaries_sha256'):
        for n,h in manifest[group].items():
            assert not (out/n).is_symlink() and (out/n).is_file() and sha256(out/n)==h, ('binary changed',n)
    with tempfile.TemporaryDirectory(prefix='read-contract-sections-',dir=out) as tmp:
        for n in LABELS:
            subprocess.run(['objcopy','--dump-section',f'.text={tmp}/text','--dump-section',f'.rodata={tmp}/rodata',str(out/n),str(Path(tmp)/'probe')],check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            assert manifest['sections_sha256'][n]=={k:sha256(Path(tmp)/k) for k in ('text','rodata')}, ('section bytes changed',n)
    for x,y in PAIRS:
        assert manifest['binaries_sha256'][x]==manifest['binaries_sha256'][y]
        assert manifest['sections_sha256'][x]==manifest['sections_sha256'][y]
    t=manifest['toolchains']
    assert tools(t['goose_path'],t['cc_path'],t['rust_toolchain'])==t, 'toolchain changed'
    assert runtime_settings()==manifest['runtime_settings'], 'runtime settings changed'
    assert not os.environ.get('READ_CONTRACT_FAULT')
    assert not os.environ.get('LD_PRELOAD'), 'interposed release timing is ineligible'

def record_process(command,event,emit,timeout=60):
    try:
        proc=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    except subprocess.TimeoutExpired as e:
        event.update(timeout=True,stdout_hex=(e.stdout or b'').hex(),stderr_hex=(e.stderr or b'').hex())
        emit(event);raise
    event.update(returncode=proc.returncode,stdout_hex=proc.stdout.hex(),stderr_hex=proc.stderr.hex())
    emit(event)
    return proc

def main():
    if not __debug__:raise SystemExit('Python optimization disables validation; use ordinary Python')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir',type=Path,default=ROOT/'.build/read-contract')
    p.add_argument('--attempt',type=int,choices=(1,2),required=True)
    p.add_argument('--cpu',type=int,default=6)
    p.add_argument('--smoke',action='store_true',help='separate one-round/count-one recorder check; never performance eligible')
    a=p.parse_args()
    out=a.build_dir.resolve();allowed=(ROOT/'.build').resolve()
    if out==allowed or not out.is_relative_to(allowed):p.error('build directory must be inside this checkout .build')
    if a.cpu not in os.sched_getaffinity(0):p.error('CPU is outside caller affinity')
    if not a.smoke and a.cpu!=6:p.error('this preregistered checkpoint uses CPU6')
    name=('smoke-' if a.smoke else 'attempt-')+str(a.attempt)
    raw=out/(name+'.jsonl');summary=out/(name+'.json')
    if a.attempt==2 and not (out/(('smoke-' if a.smoke else 'attempt-')+'1.jsonl')).is_file():p.error('attempt 1 must be started first')
    if summary.exists() or summary.is_symlink():p.error('attempt already exists')
    rows=[]
    # Exclusive creation reserves the attempt before eligibility/preflight. An
    # interrupted/failed attempt stays present and can never silently be rerun.
    with raw.open('x') as stream, (out/'build.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        def emit(event):
            stream.write(json.dumps(event,separators=(',',':'))+'\n');stream.flush();os.fsync(stream.fileno())
        record=dict(schema=1,profile='bounded-read-contract',attempt=a.attempt,smoke=a.smoke,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),cpu=a.cpu,
            platform=capture(['uname','-srvmo']),creation_seed=62501,process_seed=62502+a.attempt,
            rounds=1 if a.smoke else 5,count=1 if a.smoke else 200,samples_per_process=7,
            runtime_settings=runtime_settings(),status='started')
        emit(dict(kind='start',record=record))
        try:
            manifest=json.loads((out/'build.json').read_text());record['build']=manifest
            record['build_manifest_sha256']=sha256(out/'build.json');validate(out,manifest)
            emit(dict(kind='eligibility',build=manifest,build_manifest_sha256=record['build_manifest_sha256']))
            with tempfile.TemporaryDirectory(prefix='read-contract-measure-',dir=allowed) as tmp:
                cases,extra=fixtures(Path(tmp)/'fixtures')
                binaries=[out/n for n in LABELS]
                fault_bins=[out/(n+'-fault') for n in ('fs','rust','go')]
                record['preflight']=dict(release=check_release(binaries,cases,extra),faults=check_faults(fault_bins,cases))
                record['cases']=[{k:(v.hex() if k=='path' else sha256_bytes(v) if k=='data' else v) for k,v in c.items()} for c in cases]
                emit(dict(kind='preflight',checks=record['preflight'],cases=record['cases']))
                rng=random.Random(record['process_seed'])
                for round_number in range(record['rounds']):
                    order=[(c,n) for c in cases for n in LABELS];rng.shuffle(order)
                    for position,(c,n) in enumerate(order):
                        command=['taskset','-c',str(a.cpu),str(out/n),'measure',os.fsdecode(c['path']),str(c['limit']),str(c['code']),str(record['count'])]
                        event=dict(kind='process',round=round_number,position=position,case=c['name'],variant=n,command=command)
                        proc=record_process(command,event,emit)
                        assert proc.returncode==0 and not proc.stderr, event
                        parsed=[list(map(int,l.split(b'\t'))) for l in proc.stdout.splitlines()]
                        expected_sum=(len(c['data'])+(c['data'][0]+c['data'][-1] if c['data'] else 0)+c['code']+1)*record['count']
                        assert len(parsed)==7 and all(len(r)==3 and r[0]==i and r[1]>0 and r[2]==expected_sum for i,r in enumerate(parsed)), event
                        for sample,ns,checksum in parsed:
                            rows.append(dict(round=round_number,position=position,case=c['name'],variant=n,sample=sample,ns=ns,checksum=checksum))
                record['postflight']=dict(release=check_release(binaries,cases,extra),faults=check_faults(fault_bins,cases))
            validate(out,manifest)
            assert sha256(out/'build.json')==record['build_manifest_sha256']
            record['status']='complete';record['rows']=rows
        except BaseException as e:
            record.update(status='failed',error=repr(e),rows=rows)
            emit(dict(kind='failure',error=repr(e)))
            raise
        finally:
            record['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            emit(dict(kind='finish',status=record['status'],row_count=len(rows),finished=record['finished']))
            with summary.open('x') as f:json.dump(record,f,indent=2);f.write('\n')
        print(json.dumps(dict(record=str(summary),status=record['status'],rows=len(rows))))

def sha256_bytes(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()

if __name__=='__main__':main()
