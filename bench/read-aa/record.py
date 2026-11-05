#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Finite same-code scheduling diagnostic with supervised completion journals."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(1,str(Path(__file__).resolve().parents[1]/'read-contract'))
from build import ROOT,LABELS,publish,capture,sha256,runtime_settings
from measure import validate,sha256_bytes
from conformance import fixtures,add_fresh_case,check_release,check_faults
from collect import observe

PROFILE='read-aa-scheduling'
CASES=('tiny','large-budget','fresh-max')
BATCHES=('short','long')

def iterations(case,batch):
    return (100 if batch=='short' else 500) if case=='fresh-max' else (2000 if batch=='short' else 10000)

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def append(stream,event):
    stream.write(json.dumps(event,separators=(',',':'))+'\n');stream.flush();os.fsync(stream.fileno())

def worker(a,out,prefix):
    raw=out/f'{prefix}{a.attempt}.jsonl';summary=out/f'{prefix}{a.attempt}.json';rows=[];processes=[]
    assert not summary.exists() and not summary.is_symlink(),'attempt already exists'
    with raw.open('x') as stream,(out/'build.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        def emit(e):append(stream,e)
        taskset_path=str(Path(shutil.which('taskset')).resolve())
        record=dict(schema=1,profile=PROFILE,record_id=uuid.uuid4().hex,attempt=a.attempt,smoke=a.smoke,status='started',timestamp=utc(),cpu=a.cpu,
            build_directory=str(out),launcher_affinity=sorted(os.sched_getaffinity(0)),rounds=1 if a.smoke else 3,samples_per_process=7,
            creation_seed=62501,process_seed=62602+a.attempt,platform=capture(['uname','-srvmo']),
            runtime_settings=runtime_settings(),python=sys.version,python_executable=sys.executable,
            python_sha256=sha256(sys.executable),taskset=dict(path=taskset_path,sha256=sha256(taskset_path),version=capture([taskset_path,'--version'])),
            resource_scope='RUSAGE_CHILDREN delta; serial waited child, process-wide, not loop-only')
        emit(dict(kind='start',record=record))
        try:
            manifest=json.loads((out/'build.json').read_text());record['build']=manifest
            record['build_manifest_sha256']=sha256(out/'build.json');validate(out,manifest)
            emit(dict(kind='eligibility',build=manifest,build_manifest_sha256=record['build_manifest_sha256']))
            with tempfile.TemporaryDirectory(prefix='read-aa-fixtures-',dir=ROOT/'.build') as tmp:
                cases,extra=fixtures(Path(tmp)/'fixtures');add_fresh_case(cases)
                bins=[out/n for n in LABELS];faults=[out/(n+'-fault') for n in ('fs','rust','go')]
                record['preflight']=dict(release=check_release(bins,cases,extra),faults=check_faults(faults,cases))
                selected=[c for c in cases if c['name'] in CASES]
                assert {c['name'] for c in selected}==set(CASES)
                record['cases']=[{k:(v.hex() if k=='path' else sha256_bytes(v) if k=='data' else v) for k,v in c.items() if k!='count'}|{'counts':{b:1 if a.smoke else iterations(c['name'],b) for b in BATCHES}} for c in selected]
                emit(dict(kind='preflight',checks=record['preflight'],cases=record['cases']))
                rng=random.Random(record['process_seed'])
                for round_number in range(record['rounds']):
                    order=[(c,b,n) for c in selected for b in BATCHES for n in LABELS];rng.shuffle(order)
                    for position,(c,b,n) in enumerate(order):
                        count=1 if a.smoke else iterations(c['name'],b)
                        publish(out,'aa-active-runner',(out/n).read_bytes(),True);exe=out/'aa-active-runner'
                        assert sha256(exe)==manifest['binaries_sha256'][n]
                        command=[taskset_path,'-c',str(a.cpu),str(exe),c.get('mode','measure'),os.fsdecode(c['path']),str(c['limit']),str(c['code']),f'{count:05d}']
                        event=dict(kind='process',round=round_number,position=position,case=c['name'],batch=b,variant=n,
                            count=count,command=command,binary_sha256=manifest['binaries_sha256'][n])
                        proc=observe(command,event,emit);processes.append(event)
                        assert sha256(exe)==manifest['binaries_sha256'][n]
                        assert proc.returncode==0 and not proc.stderr,event
                        parsed=[list(map(int,l.split(b'\t'))) for l in proc.stdout.splitlines()]
                        expected=(len(c['data'])+c['data'][0]+c['data'][-1]+1)*count
                        assert len(parsed)==7 and all(len(r)==3 and r[0]==i and r[1]>0 and r[2]==expected for i,r in enumerate(parsed)),event
                        for sample,ns,checksum in parsed:
                            rows.append(dict(round=round_number,position=position,case=c['name'],batch=b,variant=n,count=count,sample=sample,ns=ns,checksum=checksum))
                record['postflight']=dict(release=check_release(bins,cases,extra),faults=check_faults(faults,cases))
            assert sha256(taskset_path)==record['taskset']['sha256'] and sha256(sys.executable)==record['python_sha256'],'launcher tools changed'
            validate(out,manifest);assert sha256(out/'build.json')==record['build_manifest_sha256']
            record['status']='complete'
        except BaseException as e:
            record.update(status='failed',error=repr(e));emit(dict(kind='failure',error=repr(e)));raise
        finally:
            record.update(rows=rows,processes=processes,finished=utc())
            emit(dict(kind='finish',status=record['status'],row_count=len(rows),finished=record['finished']))
            with summary.open('x') as s:json.dump(record,s,indent=2);s.write('\n')
        print(json.dumps(dict(record=str(summary),status=record['status'],rows=len(rows))))

class LauncherInterrupted(RuntimeError):pass

def interrupted(signum,frame):raise LauncherInterrupted(f'launcher signal {signum}')

def run_supervised(command,summary_path,emit,timeout=900):
    assert signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'launcher requires no preexisting alarm'
    assert signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'launcher requires default child reaping'
    state=dict(interruptible=False,pending=None)
    def on_signal(signum,frame):
        state['pending']=signum
        if state['interruptible']:raise LauncherInterrupted(f'launcher signal {signum}')
    proc=None;cleaned=False
    with tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as errors:
        previous={s:signal.signal(s,on_signal) for s in (signal.SIGTERM,signal.SIGINT,signal.SIGALRM)}
        try:
            # Before proc is assigned, handlers defer interruption rather than
            # unwind Popen with an unknown child. No child signal mask changes.
            proc=subprocess.Popen(command,stdout=output,stderr=errors,start_new_session=True)
            state['interruptible']=True
            if state['pending'] is not None:raise LauncherInterrupted(f"launcher signal {state['pending']}")
            signal.setitimer(signal.ITIMER_REAL,timeout)
            os.waitid(os.P_PID,proc.pid,os.WEXITED|os.WNOWAIT)
            signal.setitimer(signal.ITIMER_REAL,0)
            # WNOWAIT leaves the leader unreaped, reserving its identity even
            # after a crash. Clean descendants before wait() can release its PID.
            state['interruptible']=False
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            cleaned=True;proc.wait();state['interruptible']=True
            if state['pending'] is not None:raise LauncherInterrupted(f"launcher signal {state['pending']}")
            output.seek(0);errors.seek(0);stdout=output.read();stderr=errors.read()
            summary=json.loads(summary_path.read_text())
            assert proc.returncode==0 and summary['status']=='complete',(proc.returncode,stderr)
            emit(dict(kind='finish',timestamp=utc(),status='complete',record_id=summary['record_id'],returncode=proc.returncode,stdout_hex=stdout.hex(),stderr_hex=stderr.hex()))
        except BaseException as e:
            state['interruptible']=False;signal.setitimer(signal.ITIMER_REAL,0)
            if proc is not None and not cleaned:
                # No poll/communicate/wait has reaped this leader yet.
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
            output.seek(0);errors.seek(0)
            emit(dict(kind='finish',timestamp=utc(),status='failed',error=repr(e),returncode=proc.returncode if proc else None,stdout_hex=output.read().hex(),stderr_hex=errors.read().hex()))
            raise
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
            for s,handler in previous.items():signal.signal(s,handler)
    return proc.returncode

def supervise(a,out,prefix):
    launch=out/f'{prefix}launch-{a.attempt}.jsonl'
    if a.attempt==2:assert (out/f'{prefix}launch-1.jsonl').is_file(),'attempt 1 must start first'
    with launch.open('x') as stream,(out/'aa-launch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        command=[sys.executable,str(Path(__file__).resolve()),'--worker','--build-dir',str(out),'--attempt',str(a.attempt),'--cpu',str(a.cpu),*(['--smoke'] if a.smoke else [])]
        append(stream,dict(kind='start',profile=PROFILE,attempt=a.attempt,smoke=a.smoke,timestamp=utc(),command=command))
        code=run_supervised(command,out/f'{prefix}{a.attempt}.json',lambda e:append(stream,e))
        print(json.dumps(dict(status='complete',attempt=a.attempt,launcher_returncode=code)))

def main():
    if not __debug__:raise SystemExit('Python optimization disables validation')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-dir',type=Path,required=True)
    p.add_argument('--attempt',type=int,choices=(1,2),required=True);p.add_argument('--cpu',type=int,default=6)
    p.add_argument('--smoke',action='store_true');p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
    out=a.build_dir.resolve();allowed=(ROOT/'.build').resolve()
    if out==allowed or not out.is_relative_to(allowed) or not out.is_dir():p.error('private build directory required inside this checkout .build')
    if a.cpu not in os.sched_getaffinity(0):p.error('CPU outside caller affinity')
    if not a.smoke and (a.cpu!=6 or os.sched_getaffinity(0)!={6}):p.error('recording requires launcher and children pinned to CPU6')
    prefix='aa-smoke-' if a.smoke else 'aa-attempt-'
    if a.worker:worker(a,out,prefix)
    else:supervise(a,out,prefix)

if __name__=='__main__':main()
