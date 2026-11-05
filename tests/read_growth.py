#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Growth acceptance-rule checks and optional real eight-runner recorder smoke."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('growth_analysis',ROOT/'bench/read-growth/analyze.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from build import GROWTH_LABELS,BASELINE

def records():
    out=[]
    for a in (1,2):
        rows=[dict(round=r,case=c,variant=n,sample=s,ns=100 if n.startswith('fs') and c=='large-budget' else 120)
              for r in range(5) for c in m.CASES for n in GROWTH_LABELS for s in range(7)]
        out.append(dict(attempt=a,status='complete',smoke=False,profile='bounded-read-growth',build_manifest_sha256='same',build=dict(baseline_revision=BASELINE),cases=[dict(name=c,mode='fresh',count=100) if c=='fresh-max' else dict(name=c) for c in m.CASES],rounds=5,count=2000,samples_per_process=7,cpu=6,rows=rows))
    return out
class Rules(unittest.TestCase):
    def test_target_ratios_and_both_records(self):
        r=records();self.assertEqual(m.analyze_growth(r)['decision'],'eligible for adoption')
        for row in r[1]['rows']:
            if row['case']=='large-budget' and row['variant'].startswith('fs'):row['ns']=115
        self.assertEqual(m.analyze_growth(r)['reason'],'target below threshold')
    def test_every_control_and_fresh_regression_guard(self):
        for n in GROWTH_LABELS:
            r=records()
            for row in r[0]['rows']:
                if row['variant']==n and row['case']=='fresh-max':row['ns']=150
            self.assertEqual(m.analyze_growth(r)['reason'],'inconclusive controls')
        r=records()
        for row in r[0]['rows']:
            if row['variant'].startswith('fs') and row['case']=='fresh-max':row['ns']=127
        self.assertEqual(m.analyze_growth(r)['reason'],'regression guard')
    def test_four_cross_ratios(self):
        r=records()
        for rec in r:
            for row in rec['rows']:
                if row['case']=='large-budget' and row['variant']=='base1':row['ns']=109
                if row['case']=='large-budget' and row['variant']=='base2':row['ns']=110
        self.assertEqual(m.analyze_growth(r)['reason'],'target below threshold')
    def test_fresh_and_reused_mode_counts(self):
        for name,key,value in [('fresh-max','mode','measure'),('fresh-max','count',2000),('tiny','count',100),('tiny','mode','fresh')]:
            r=records()
            next(c for c in r[0]['cases'] if c['name']==name)[key]=value
            with self.assertRaises(AssertionError):m.analyze_growth(r)
    def test_failed_replaced_or_duplicate_records(self):
        for key,value in [('status','failed'),('smoke',True),('attempt',3),('count',200),('profile','bounded-read-contract')]:
            r=records();r[1][key]=value
            with self.assertRaises(AssertionError):m.analyze_growth(r)
        r=records();r[0]['rows'][-1]=copy.deepcopy(r[0]['rows'][0])
        with self.assertRaises(AssertionError):m.analyze_growth(r)

def smoke(build):
    cmd=[sys.executable,str(ROOT/'bench/read-contract/measure.py'),'--matched-growth','--build-dir',str(build),'--attempt','1','--smoke','--cpu',str(min(os.sched_getaffinity(0)))]
    subprocess.run(cmd,check=True,timeout=300)
    r=json.loads((build/'smoke-1.json').read_text());assert r['status']=='complete' and len(r['rows'])==672
    assert {c['name'] for c in r['cases']}==set(m.CASES)
    before=(build/'smoke-1.jsonl').read_bytes()
    processes=[json.loads(line) for line in before.splitlines() if json.loads(line)['kind']=='process']
    assert len(processes)==96 and {p['command'][3] for p in processes}=={str(build/'active-runner')}
    assert all(p['binary_sha256']==r['build']['binaries_sha256'][p['variant']] for p in processes)
    assert subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
    assert (build/'smoke-1.jsonl').read_bytes()==before
    original=json.loads((build/'build.json').read_text())
    with tempfile.TemporaryDirectory(prefix='growth-rejections-',dir=ROOT/'.build') as tmp:
        out=Path(tmp)
        for n in (*original['binaries_sha256'],*original['fault_binaries_sha256']):os.link(build/n,out/n)
        mutations=[('baseline_revision','0'*40,'baseline revision changed'),('variant_library_sha256',{},'variant library bytes changed')]
        for i,(key,value,reason) in enumerate(mutations):
            manifest=copy.deepcopy(original);manifest[key]=value;(out/'build.json').write_text(json.dumps(manifest))
            bad=[sys.executable,str(ROOT/'bench/read-contract/measure.py'),'--matched-growth','--build-dir',str(out),'--attempt','1','--smoke','--cpu',str(min(os.sched_getaffinity(0)))]
            assert subprocess.run(bad,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
            record=json.loads((out/'smoke-1.json').read_text());assert record['status']=='failed' and reason in record['error'],record
            (out/'smoke-1.json').rename(out/f'rejected-{i}.json');(out/'smoke-1.jsonl').rename(out/f'rejected-{i}.jsonl')
    print('Eight-runner recorder, fresh cell and overwrite gate passed')

if __name__=='__main__':
    if not __debug__:raise SystemExit('Python optimization disables validation')
    p=argparse.ArgumentParser();p.add_argument('--build-dir',type=Path);a=p.parse_args()
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    if not result.wasSuccessful():raise SystemExit(1)
    if a.build_dir:smoke(a.build_dir.resolve())
