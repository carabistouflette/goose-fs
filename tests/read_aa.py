#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Actual-child resource/supervisor checks and finite diagnostic rule regressions."""
import argparse
import copy
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bench/read-aa'))
from record import PROFILE,CASES,BATCHES,iterations,run_supervised,append
from collect import observe,FIELDS
from analyze import analyze as analyze_raw,expected
from build import LABELS,PAIRS

def records():
    result=[]
    for attempt in (1,2):
        before={k:0.0 if k in FIELDS[:2] else 0 for k in FIELDS}
        after={k:0.01 if k in FIELDS[:2] else 1 for k in FIELDS}
        resources=dict(before=before,after=after,delta=after.copy(),parent_wall_ns=30000000)
        cases=[dict(name=c,path=(f'/fixture/{c}').encode().hex(),data=expected(c)[0],limit=64 if c=='tiny' else 1048576,code=0,counts={b:iterations(c,b) for b in BATCHES},**({'mode':'fresh'} if c=='fresh-max' else {})) for c in CASES]
        build=dict(identical_executables=True,identical_sections=True,replica_pairs=[list(p) for p in PAIRS],binaries_sha256={n:n.rstrip('12') for n in LABELS},sections_sha256={n:dict(text=n.rstrip('12'),rodata=n.rstrip('12')) for n in LABELS})
        r=dict(schema=1,profile=PROFILE,record_id=f'record-{attempt}',attempt=attempt,status='complete',smoke=False,cpu=6,taskset=dict(path='/usr/bin/taskset',sha256='fixture',version='fixture'),build_directory='/private',launcher_affinity=[6],rounds=3,samples_per_process=7,creation_seed=62501,process_seed=62602+attempt,
            preflight=dict(release=288,faults=132),postflight=dict(release=288,faults=132),build=build,build_manifest_sha256='frozen',cases=cases,processes=[],rows=[])
        rng=random.Random(r['process_seed'])
        for round_number in range(3):
            order=[(c,b,n) for c in CASES for b in BATCHES for n in LABELS];rng.shuffle(order)
            for position,(c,b,n) in enumerate(order):
                count=iterations(c,b);ns=100;checksum=expected(c)[1]*count
                stdout=''.join(f'{i}\t{ns}\t{checksum}\n' for i in range(7)).encode().hex()
                case=next(x for x in cases if x['name']==c)
                p=dict(kind='process',round=round_number,position=position,case=c,batch=b,variant=n,count=count,returncode=0,stdout_hex=stdout,stderr_hex='',binary_sha256=build['binaries_sha256'][n],resources=copy.deepcopy(resources),
                    command=['/usr/bin/taskset','-c','6','/private/aa-active-runner','fresh' if c=='fresh-max' else 'measure',f'/fixture/{c}',str(case['limit']),'0',f'{count:05d}'])
                r['processes'].append(p)
                r['rows'] += [dict(round=round_number,position=position,case=c,batch=b,variant=n,count=count,sample=i,ns=ns,checksum=checksum) for i in range(7)]
        r['finished']='finished';result.append(r)
    return result

def launchers():return [[dict(kind='start',profile=PROFILE,attempt=i,smoke=False),dict(kind='finish',record_id=f'record-{i}',status='complete',returncode=0,stderr_hex='')] for i in (1,2)]
OUTER=dict(tool_exit_codes={'1':0,'2':0})

def journals(records):
    out=[]
    for r in records:
        header={k:r[k] for k in ('schema','profile','record_id','attempt','smoke','cpu','build_directory','launcher_affinity','rounds','samples_per_process','creation_seed','process_seed','taskset')};header['status']='started'
        out.append([dict(kind='start',record=header),dict(kind='eligibility',build=r['build'],build_manifest_sha256=r['build_manifest_sha256']),dict(kind='preflight',checks=r['preflight'],cases=r['cases']),*copy.deepcopy(r['processes']),dict(kind='finish',status=r['status'],row_count=len(r['rows']),finished=r['finished'])])
    return out

def analyze(r,j,o):return analyze_raw(r,j,o,journals(r))

class Rules(unittest.TestCase):
    def test_qualified_and_each_long_pair_both_records(self):
        self.assertEqual(analyze(records(),launchers(),OUTER)['assessment'],'long-batch controls qualified at this checkpoint')
        for n in LABELS:
            r=records()
            for p in r[1]['processes']:
                if p['variant']==n and p['batch']=='long' and p['case']=='tiny':
                    raw=bytes.fromhex(p['stdout_hex']).decode().replace('\t100\t','\t110\t');p['stdout_hex']=raw.encode().hex()
            for row in r[1]['rows']:
                if row['variant']==n and row['batch']=='long' and row['case']=='tiny':row['ns']=110
            self.assertEqual(analyze(r,launchers(),OUTER)['assessment'],'inconclusive for broader optimization')
    def test_completion_status_cannot_be_inferred(self):
        for status in (143,None,1):
            outer=copy.deepcopy(OUTER);outer['tool_exit_codes']['2']=status
            self.assertFalse(analyze(records(),launchers(),outer)['completion_gate'])
        for mode in ('missing','failed','nonzero','wrong_record'):
            j=launchers()
            if mode=='missing':j[1]=j[1][:1]
            elif mode=='failed':j[1][-1]['status']='failed'
            elif mode=='nonzero':j[1][-1]['returncode']=7
            else:j[1][-1]['record_id']='record-1'
            self.assertFalse(analyze(records(),j,OUTER)['completion_gate'])
    def test_corrupt_stream_counter_schedule_and_duplicate_rows_rejected(self):
        for mode in ('counter','stream','schedule','row','limit','status','argv'):
            r=records()
            if mode=='counter':r[0]['processes'][0]['resources']['delta']['ru_nvcsw']=2
            elif mode=='stream':r[0]['processes'][0]['stdout_hex']='00'
            elif mode=='schedule':r[0]['processes'][0]['position']=2
            elif mode=='limit':r[0]['processes'][0]['command'][6]='1'
            elif mode=='status':r[0]['processes'][0]['command'][7]='4'
            elif mode=='argv':r[0]['processes'][0]['command'].append('extra')
            else:r[0]['rows'][-1]=copy.deepcopy(r[0]['rows'][0])
            with self.assertRaises((AssertionError,ValueError)):analyze(r,launchers(),OUTER)
    def test_worker_journal_cannot_be_missing_truncated_or_contradictory(self):
        for mode in ('missing','truncated','start','process','eligibility','preflight','finish'):
            r=records();j=journals(r)
            if mode=='missing':j[1]=[]
            elif mode=='truncated':j[1].pop()
            elif mode=='start':j[1][0]['record'].pop('record_id')
            elif mode=='process':j[1][3]['count']=1
            elif mode=='eligibility':j[1][1]['build_manifest_sha256']='other'
            elif mode=='preflight':j[1][2]['checks']={}
            else:j[1][-1]['status']='failed'
            self.assertFalse(analyze_raw(r,launchers(),OUTER,j)['completion_gate'])

class Children(unittest.TestCase):
    def test_real_cpu_and_sleep_child_resource_scope(self):
        events=[];code="import os,time;end=time.process_time()+0.03\nwhile time.process_time()<end: pass\ntime.sleep(0.03);os.write(1,bytes([255,0]))"
        p=observe([sys.executable,'-c',code],{},events.append)
        self.assertEqual(p.returncode,0);e=events[0]
        self.assertEqual(bytes.fromhex(e['stdout_hex']),bytes([255,0]))
        self.assertGreater(e['resources']['delta']['ru_utime']+e['resources']['delta']['ru_stime'],0.01)
        self.assertGreaterEqual(e['resources']['delta']['ru_nvcsw'],1)
        self.assertGreater(e['resources']['parent_wall_ns'],30000000)
    def test_timeout_retains_partial_binary_stream_and_counters(self):
        events=[];code='import os,time;os.write(1,bytes([255,0]));time.sleep(5)'
        with self.assertRaises(subprocess.TimeoutExpired):observe([sys.executable,'-c',code],{},events.append,timeout=0.3)
        self.assertEqual(bytes.fromhex(events[0]['stdout_hex']),bytes([255,0]));self.assertTrue(events[0]['timeout']);self.assertIn('resources',events[0])
    def test_real_interruption_preserves_binary_prefix(self):
        import child
        import signal
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
        def interrupt(*args):raise KeyboardInterrupt()
        previous=signal.signal(signal.SIGALRM,interrupt)
        try:
            signal.setitimer(signal.ITIMER_REAL,0.3)
            with self.assertRaises(KeyboardInterrupt) as caught:
                child.run_captured([sys.executable,'-c',"import os,time;os.write(1,bytes([0,255])+b'prefix');os.write(2,b'err'+bytes([0]));time.sleep(5)"],10)
            self.assertEqual(caught.exception.stdout,bytes([0,255])+b'prefix')
            self.assertEqual(caught.exception.stderr,b'err'+bytes([0]))
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
            signal.signal(signal.SIGALRM,previous)
    def test_interruption_retains_drained_pipe_tails(self):
        import child
        class Fake:
            returncode=-9
            def __init__(self,*a,**k):self.count=0
            def kill(self):pass
            def communicate(self,**kwargs):
                self.count+=1
                if self.count==1:raise KeyboardInterrupt()
                return b'partial-tail',b'error-tail'
        with unittest.mock.patch.object(child.subprocess,'Popen',Fake):
            with self.assertRaises(KeyboardInterrupt) as caught:child.run_captured(['fixture'],1)
        self.assertEqual(caught.exception.stdout,b'partial-tail')
        self.assertEqual(caught.exception.stderr,b'error-tail')
    def test_timeout_drains_bytes_queued_after_first_communicate(self):
        holder=[]
        class Child:
            def __init__(self,command,**kwargs):self.args=command;self.returncode=None;self.calls=0;self.reaped=False;holder.append(self)
            def __enter__(self):return self
            def __exit__(self,*a):self.wait()
            def communicate(self,*args,**kwargs):
                self.calls+=1
                if self.calls==1:raise subprocess.TimeoutExpired(self.args,0.1,output=b'prefix',stderr=b'err')
                self.reaped=True;self.returncode=-9;return b'prefix-tail',b'err-tail'
            def kill(self):self.returncode=-9
            def wait(self):self.reaped=True;return self.returncode
            def poll(self):return self.returncode
        def counters():
            if holder:self.assertTrue(holder[0].reaped)
            return {k:0.0 if k in FIELDS[:2] else 0 for k in FIELDS}
        events=[]
        with patch('collect.subprocess.Popen',Child),patch('collect.snapshot',counters):
            with self.assertRaises(subprocess.TimeoutExpired):observe(['fixture'],{},events.append,timeout=0.1)
        self.assertEqual(bytes.fromhex(events[-1]['stdout_hex']),b'prefix-tail')
        self.assertEqual(bytes.fromhex(events[-1]['stderr_hex']),b'err-tail')
    def test_supervisor_alarm_retains_partial_stream_and_restores_handlers(self):
        with tempfile.TemporaryDirectory() as tmp:
            events=[];summary=Path(tmp)/'summary'
            previous={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT,signal.SIGALRM)}
            code='import os,time;os.write(1,bytes([255,0]));time.sleep(10)'
            with self.assertRaises(RuntimeError):run_supervised([sys.executable,'-c',code],summary,events.append,timeout=0.3)
            self.assertEqual(bytes.fromhex(events[-1]['stdout_hex']),bytes([255,0]));self.assertEqual(events[-1]['status'],'failed')
            self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
            self.assertEqual({s:signal.getsignal(s) for s in previous},previous)
    def test_completed_marker_nonzero_worker_is_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'summary.json';events=[]
            code='import pathlib,json,sys;pathlib.Path(sys.argv[1]).write_text(json.dumps({"status":"complete"}));sys.exit(7)'
            with self.assertRaises(AssertionError):run_supervised([sys.executable,'-c',code,str(p)],p,events.append)
            self.assertEqual(events[-1]['status'],'failed');self.assertEqual(events[-1]['returncode'],7)
    def test_crashed_worker_redirected_descendant_is_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ready=root/'ready';summary=root/'summary';events=[]
            code="import subprocess,sys,pathlib,json;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);pathlib.Path(sys.argv[1]).write_text(str(p.pid));pathlib.Path(sys.argv[2]).write_text(json.dumps({'status':'complete','record_id':'x'}));sys.exit(7)"
            with self.assertRaises(AssertionError):run_supervised([sys.executable,'-c',code,str(ready),str(summary)],summary,events.append)
            self.assertEqual(events[-1]['returncode'],7);pid=int(ready.read_text())
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                p=Path(f'/proc/{pid}/stat')
                if not p.exists() or p.read_text().rsplit(')',1)[1].split()[0] in ('Z','X'):break
                time.sleep(0.01)
            else:self.fail('owned descendant survived worker crash')
    def test_late_signal_during_completion_stays_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary=Path(tmp)/'summary';events=[]
            code="import pathlib,sys;pathlib.Path(sys.argv[1]).write_text('{\"status\":\"complete\",\"record_id\":\"x\"}')"
            def emit(e):
                events.append(e)
                if e['status']=='complete':os.kill(os.getpid(),signal.SIGTERM)
            with self.assertRaises(RuntimeError):run_supervised([sys.executable,'-c',code,str(summary)],summary,emit)
            self.assertEqual(events[-1]['status'],'failed')
    def test_interrupted_supervisor_owns_only_its_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ready=root/'ready';journal=root/'events';summary=root/'summary'
            child="import os,time,sys,pathlib,subprocess,json;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)']);pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(),p.pid]));time.sleep(10)"
            supervisor="import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from record import run_supervised,append\nf=open(sys.argv[3],'w');run_supervised([sys.executable,'-c',sys.argv[5],sys.argv[2]],Path(sys.argv[4]),lambda e:append(f,e))"
            proc=subprocess.Popen([sys.executable,'-c',supervisor,str(ROOT/'bench/read-aa'),str(ready),str(journal),str(summary),child],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+5
                while not ready.exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(0.01)
                self.assertTrue(ready.exists());pid,descendant=json.loads(ready.read_text())
                os.kill(proc.pid,signal.SIGTERM);proc.communicate(timeout=5)
                self.assertNotEqual(proc.returncode,0)
                event=json.loads(journal.read_text().splitlines()[-1]);self.assertEqual(event['status'],'failed');self.assertEqual(event['returncode'],-signal.SIGKILL)
                with self.assertRaises(ProcessLookupError):os.kill(pid,0)
                state=Path(f'/proc/{descendant}/stat')
                if state.exists():self.assertIn(state.read_text().rsplit(')',1)[1].split()[0],('Z','X'))
            finally:
                if proc.poll() is None:proc.kill();proc.communicate()

class Preservation(unittest.TestCase):
    def test_builder_refuses_reserved_aa_attempt(self):
        (ROOT/'.build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='aa-build-guard-',dir=ROOT/'.build') as tmp:
            out=Path(tmp);(out/'aa-attempt-launch-1.jsonl').write_text('reserved\n');(out/'build.json').write_text('unchanged')
            p=subprocess.run([sys.executable,str(ROOT/'bench/read-contract/build.py'),'--goose',sys.executable,'--output-dir',str(out)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertNotEqual(p.returncode,0);self.assertIn(b'measured attempts already exist',p.stderr)
            self.assertEqual((out/'build.json').read_text(),'unchanged')

def smoke(build):
    cmd=[sys.executable,str(ROOT/'bench/read-aa/record.py'),'--build-dir',str(build),'--attempt','1','--smoke','--cpu',str(min(os.sched_getaffinity(0)))]
    subprocess.run(cmd,check=True,timeout=300)
    r=json.loads((build/'aa-smoke-1.json').read_text());assert r['status']=='complete' and len(r['rows'])==252 and len(r['processes'])==36
    assert all('resources' in p for p in r['processes'])
    launch=build/'aa-smoke-launch-1.jsonl';before=launch.read_bytes()
    assert subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
    assert launch.read_bytes()==before
    assert subprocess.run([sys.executable,'-O',*cmd[1:]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
    print('Supervised smoke/resources/duplicate/-O gates passed')

if __name__=='__main__':
    if not __debug__:raise SystemExit('Python optimization disables validation')
    p=argparse.ArgumentParser();p.add_argument('--build-dir',type=Path);a=p.parse_args()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (Rules,Children,Preservation))
    result=unittest.TextTestRunner().run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    if a.build_dir:smoke(a.build_dir.resolve())
