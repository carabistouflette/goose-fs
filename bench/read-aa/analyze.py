#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate complete A/A evidence and report uncorrected replica controls."""
import argparse
from functools import lru_cache
import hashlib
import json
import math
import os
import random
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from record import PROFILE,CASES,BATCHES,iterations
from build import LABELS,PAIRS
from collect import FIELDS
from conformance import pattern

@lru_cache
def expected(case):
    size=1048576 if case=='fresh-max' else 64
    data=pattern(size)
    return hashlib.sha256(data).hexdigest(),len(data)+data[0]+data[-1]+1

def resource_check(value):
    assert set(value)=={'before','after','delta','parent_wall_ns'}
    assert type(value['parent_wall_ns']) is int and value['parent_wall_ns']>0
    for name in ('before','after','delta'):
        assert set(value[name])==set(FIELDS)
        assert all(type(v) in (float,int) and math.isfinite(v) and v>=0 for v in value[name].values())
        assert all(type(value[name][k]) is int for k in FIELDS[2:])
    assert all(value['after'][k]-value['before'][k]==value['delta'][k] for k in FIELDS)

def worker_journal_matches(record,journal):
    if len(journal)!=len(record.get('processes',[]))+4:return False
    if [e.get('kind') for e in journal]!=['start','eligibility','preflight']+['process']*len(record.get('processes',[]))+['finish']:return False
    start={k:v for k,v in record.items() if k not in ('build','build_manifest_sha256','preflight','postflight','cases','rows','processes','finished','error')}
    start['status']='started'
    if journal[0]!=dict(kind='start',record=start):return False
    if journal[1]!=dict(kind='eligibility',build=record['build'],build_manifest_sha256=record['build_manifest_sha256']):return False
    if journal[2]!=dict(kind='preflight',checks=record['preflight'],cases=record['cases']):return False
    if journal[3:-1]!=record['processes']:return False
    return journal[-1]==dict(kind='finish',status=record['status'],row_count=len(record['rows']),finished=record['finished'])

def load_journal(path):
    if not path.exists():return []
    try:return [json.loads(s) for s in path.read_text().splitlines()]
    except json.JSONDecodeError:return []

def analyze(records,launches,outer,journals):
    assert len(records)==2 and [r['attempt'] for r in records]==[1,2]
    assert set(outer['tool_exit_codes'])=={'1','2'}
    outer_ok=all(type(v) is int and v==0 for v in outer['tool_exit_codes'].values())
    launch_ok=len(launches)==2 and all(len(j)>=2 and j[0]['kind']=='start' and j[0].get('profile')==PROFILE and j[0].get('attempt')==r['attempt'] and not j[0].get('smoke',True) and j[-1].get('kind')=='finish' and j[-1].get('status')=='complete' and j[-1].get('record_id')==r['record_id'] and type(j[-1].get('returncode')) is int and j[-1]['returncode']==0 and not bytes.fromhex(j[-1]['stderr_hex']) for r,j in zip(records,launches))
    worker_ok=len(journals)==2 and all(r['status']=='complete' and worker_journal_matches(r,j) for r,j in zip(records,journals))
    complete=worker_ok and outer_ok and launch_ok and all(r['status']=='complete' and not r['smoke'] for r in records)
    assert all(type(r['record_id']) is str and r['record_id'] for r in records) and len({r['record_id'] for r in records})==2
    outputs=[]
    for r in records:
        assert r['schema']==1 and r['profile']==PROFILE
        if r['status']!='complete':
            outputs.append(dict(attempt=r['attempt'],status=r['status'],row_count=len(r['rows'])));continue
        assert not r['smoke'] and r['cpu']==6 and r['launcher_affinity']==[6]
        assert (r['rounds'],r['samples_per_process'],r['creation_seed'],r['process_seed'])==(3,7,62501,62602+r['attempt'])
        assert r['preflight']==r['postflight']==dict(release=288,faults=132)
        assert len(r['rows'])==756 and len(r['processes'])==108
        assert r['build']['identical_executables'] and r['build']['identical_sections']
        assert r['build']['replica_pairs']==[list(p) for p in PAIRS]
        assert set(r['build']['binaries_sha256'])==set(LABELS)
        for a,b in PAIRS:
            assert r['build']['binaries_sha256'][a]==r['build']['binaries_sha256'][b]
            assert r['build']['sections_sha256'][a]==r['build']['sections_sha256'][b]
        assert len(r['cases'])==3 and {c['name'] for c in r['cases']}==set(CASES)
        for c in r['cases']:
            assert c['data']==expected(c['name'])[0] and c['code']==0
            assert c['limit']==(64 if c['name']=='tiny' else 1048576)
            assert c.get('mode','measure')==('fresh' if c['name']=='fresh-max' else 'measure')
            assert c['counts']=={b:iterations(c['name'],b) for b in BATCHES}
        seen=set();decoded=[];paths=set();groups={};observations={}
        rng=random.Random(r['process_seed']);planned=[]
        for round_number in range(3):
            order=[(c,b,n) for c in CASES for b in BATCHES for n in LABELS];rng.shuffle(order);planned+=order
        for index,p in enumerate(r['processes']):
            c,b,n=p['case'],p['batch'],p['variant']
            assert c in CASES and b in BATCHES and n in LABELS and p['kind']=='process'
            assert (p['round'],p['position'])==(index//36,index%36) and (c,b,n)==planned[index]
            key=(p['round'],c,b,n)
            assert key not in seen;seen.add(key)
            assert p['returncode']==0 and not bytes.fromhex(p['stderr_hex'])
            assert 'resource_error' not in p and 'timeout' not in p and 'launch_error' not in p
            resource_check(p['resources'])
            assert p['binary_sha256']==r['build']['binaries_sha256'][n]
            command=p['command'];assert len(command)==9;paths.add(command[3])
            assert command[:3]==[r['taskset']['path'],'-c','6'] and command[3]==str(Path(r['build_directory'])/'aa-active-runner')
            assert command[4]==('fresh' if c=='fresh-max' else 'measure')
            assert command[-1]==f'{iterations(c,b):05d}' and p['count']==iterations(c,b)
            case=next(x for x in r['cases'] if x['name']==c)
            assert command[5:8]==[os.fsdecode(bytes.fromhex(case['path'])),str(case['limit']),str(case['code'])]
            parsed=[list(map(int,l.split(b'\t'))) for l in bytes.fromhex(p['stdout_hex']).splitlines()]
            assert len(parsed)==7 and all(len(x)==3 and x[0]==i and x[1]>0 and x[2]==expected(c)[1]*iterations(c,b) for i,x in enumerate(parsed))
            for sample,ns,checksum in parsed:
                row=dict(round=p['round'],position=p['position'],case=c,batch=b,variant=n,count=p['count'],sample=sample,ns=ns,checksum=checksum)
                decoded.append(row);groups.setdefault((c,b,n),[]).append(ns)
            observations.setdefault((c,b,n.rstrip('12')),[]).append(p)
        assert len(paths)==1 and decoded==r['rows']
        cells={}
        for c in CASES:
            cells[c]={}
            for b in BATCHES:
                m={n:statistics.median(groups[c,b,n]) for n in LABELS}
                controls={a.rstrip('1'):max(m[a],m[z])/min(m[a],m[z]) for a,z in PAIRS}
                resources={}
                for language in ('fs','rust','go'):
                    obs=observations[c,b,language]
                    resources[language]=dict(process_count=len(obs),parent_wall_ns=statistics.median(p['resources']['parent_wall_ns'] for p in obs),
                        delta_medians={k:statistics.median(p['resources']['delta'][k] for p in obs) for k in FIELDS})
                cells[c][b]=dict(medians_ns=m,controls=controls,resources=resources)
        outputs.append(dict(attempt=r['attempt'],status='complete',cells=cells))
    if all(r['status']=='complete' for r in records):assert records[0]['build_manifest_sha256']==records[1]['build_manifest_sha256']
    qualified={c:{language:complete and all(o.get('status')=='complete' and o['cells'][c]['long']['controls'][language]<=1.05 for o in outputs) for language in ('fs','rust','go')} for c in CASES}
    all_pass=all(v for x in qualified.values() for v in x.values())
    return dict(records=outputs,completion_gate=complete,long_qualified=qualified,
        worker_journal_gate=worker_ok,assessment='long-batch controls qualified at this checkpoint' if all_pass else 'inconclusive for broader optimization',
        no_correction_or_causal_claim=True,outer_statuses=outer)

if __name__=='__main__':
    if not __debug__:raise SystemExit('Python optimization disables validation')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('records',nargs=2,type=Path);p.add_argument('--outer-statuses',type=Path,required=True);a=p.parse_args()
    records=[json.loads(f.read_text()) for f in a.records]
    paths=[f.parent/f'aa-attempt-launch-{i}.jsonl' for i,f in enumerate(a.records,1)]
    launches=[load_journal(p) for p in paths]
    journals=[load_journal(p.with_suffix('.jsonl')) for p in a.records]
    print(json.dumps(analyze(records,launches,json.loads(a.outer_statuses.read_text()),journals),indent=2))
