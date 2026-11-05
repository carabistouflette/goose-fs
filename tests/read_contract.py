#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Decision-rule regression checks plus optional real recorder smoke/rejections."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bench/read-contract'))
from analyze import analyze,CASES
from build import LABELS
from measure import record_process

def records():
    result=[]
    for attempt in (1,2):
        rows=[dict(round=r,case=c,variant=n,sample=s,ns=100 if n.startswith('fs') else 120)
              for r in range(5) for c in CASES for n in LABELS for s in range(7)]
        result.append(dict(attempt=attempt,status='complete',smoke=False,build_manifest_sha256='frozen',rounds=5,count=200,samples_per_process=7,cpu=6,rows=rows))
    return result
class Rules(unittest.TestCase):
    def test_ratio_direction_and_both_records(self):
        r=records();self.assertEqual(set(analyze(r)['labels'].values()),{'qualifying FS lead'})
        for row in r[1]['rows']:
            if row['variant'].startswith('fs'):row['ns']=140
        self.assertEqual(set(analyze(r)['labels'].values()),{'inconclusive'})
    def test_symmetric_controls_and_every_language(self):
        for name in LABELS:
            for value in (50,160):
                r=records()
                for row in r[0]['rows']:
                    if row['variant']==name:row['ns']=value
                self.assertEqual(set(analyze(r)['labels'].values()),{'inconclusive'})
    def test_all_four_cross_replica_ratios(self):
        r=records()
        for rec in r:
            for row in rec['rows']:
                if row['variant']=='go2':row['ns']=109
                if row['variant']=='go1':row['ns']=110
        self.assertEqual(set(analyze(r)['labels'].values()),{'inconclusive'})
    def test_failed_or_replaced_attempts_rejected(self):
        for field,value in [('status','failed'),('smoke',True),('attempt',3),('build_manifest_sha256','other'),('count',201)]:
            r=records();r[1][field]=value
            with self.assertRaises(AssertionError):analyze(r)
    def test_missing_duplicate_and_unknown_rows(self):
        for mode in ('missing','duplicate','unknown'):
            r=records()
            if mode=='missing':r[0]['rows'].pop()
            elif mode=='duplicate':r[0]['rows'][-1]=copy.deepcopy(r[0]['rows'][0])
            else:r[0]['rows'][0]['case']='unexpected'
            with self.assertRaises(AssertionError):analyze(r)
    def test_timeout_retains_partial_binary_streams(self):
        events=[]
        cmd=[sys.executable,'-c',"import os,time;os.write(1,bytes([255,0]));os.write(2,bytes([128,1]));time.sleep(5)"]
        with self.assertRaises(subprocess.TimeoutExpired):record_process(cmd,{},events.append,timeout=0.3)
        self.assertEqual(len(events),1);self.assertTrue(events[0]['timeout'])
        self.assertEqual(bytes.fromhex(events[0]['stdout_hex']),bytes([255,0]))
        self.assertEqual(bytes.fromhex(events[0]['stderr_hex']),bytes([128,1]))
    def test_thresholds_are_cell_local(self):
        r=records()
        for row in r[1]['rows']:
            if row['case']=='tiny' and row['variant']=='rust2':row['ns']=150
        labels=analyze(r)['labels'];self.assertEqual(labels['tiny'],'inconclusive');self.assertEqual(labels['page'],'qualifying FS lead')

def smoke(build):
    command=[sys.executable,str(ROOT/'bench/read-contract/measure.py'),'--build-dir',str(build),'--attempt','1','--smoke','--cpu',str(min(os.sched_getaffinity(0)))]
    subprocess.run(command,check=True,timeout=300)
    record=json.loads((build/'smoke-1.json').read_text());assert record['status']=='complete' and len(record['rows'])==462
    digest=(build/'smoke-1.jsonl').read_bytes()
    assert subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
    assert (build/'smoke-1.jsonl').read_bytes()==digest
    assert subprocess.run([sys.executable,'-O',*command[1:]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
    original=json.loads((build/'build.json').read_text())
    with tempfile.TemporaryDirectory(prefix='read-contract-rejections-',dir=ROOT/'.build') as tmp:
        out=Path(tmp)
        for name in (*original['binaries_sha256'],*original['fault_binaries_sha256']):
            os.link(build/name,out/name)
        mutations=(('source_dirty',True),('profile','wrong'),('replica_pairs',[]),('identical_executables',False),('sections_sha256',{n:{'text':'0'*64,'rodata':'0'*64} for n in LABELS}))
        for i,(key,value) in enumerate(mutations):
            manifest=copy.deepcopy(original);manifest[key]=value
            (out/'build.json').write_text(json.dumps(manifest))
            cmd=[sys.executable,str(ROOT/'bench/read-contract/measure.py'),'--build-dir',str(out),'--attempt','1','--smoke','--cpu',str(min(os.sched_getaffinity(0)))]
            assert subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
            assert json.loads((out/'smoke-1.json').read_text())['status']=='failed'
            assert (out/'smoke-1.jsonl').is_file()
            # Each is an independent nonqualifying rejection fixture, not an
            # eligible measurement attempt. Archive before the next mutation.
            (out/'smoke-1.json').rename(out/f'rejected-{i}.json')
            (out/'smoke-1.jsonl').rename(out/f'rejected-{i}.jsonl')
    print('Recorder smoke, overwrite/-O gates and failed-eligibility retention passed')

if __name__=='__main__':
    if not __debug__:raise SystemExit('Python optimization disables validation')
    p=argparse.ArgumentParser();p.add_argument('--build-dir',type=Path);a=p.parse_args()
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    if not result.wasSuccessful():raise SystemExit(1)
    if a.build_dir:smoke(a.build_dir.resolve())
