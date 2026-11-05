#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay every retained native-API stream and derive readlink medians."""
import hashlib
import json
from pathlib import Path
import statistics
ROOT=Path(__file__).resolve().parent
if not __debug__:raise SystemExit('Python optimization disables validation')
outer=json.loads((ROOT/'outer-statuses.json').read_text())
assert outer=={'tool_exit_codes':{'1':0,'2':0,'3':0}}
results=[];total=0;unsupported=0;streams=0;source=None;binaries=None
for i in (1,2,3):
 r=json.loads((ROOT/f'pass-{i}.json').read_text());j=[json.loads(x) for x in (ROOT/f'pass-{i}.jsonl').read_text().splitlines()]
 assert r['status']=='complete' and not r['source_dirty'] and not r['build']['source_dirty']
 assert r['source_revision']==r['build']['source_revision']=='4a7b2c178695fb453b4303184303212ee3d85834'
 assert (r['iterations'],r['rounds'],r['seed'],r['cpu_affinity'])==(100,3,65810+i,[6])
 assert len(r['samples'])==3360 and len(r['batches'])==12
 assert r['build']['source_sha256']==j[0]['build']['source_sha256'] and j[0]['kind']=='start'
 assert j[0]['build']==r['build'] and j[-1]==dict(kind='finish',status='complete',samples=3360)
 assert j[0]['arguments']['seed']==65810+i and j[0]['arguments']['iterations']==100 and j[0]['arguments']['rounds']==3
 for path,digest in r['build']['source_sha256'].items():
  assert hashlib.sha256((ROOT.parents[2]/path).read_bytes()).hexdigest()==digest,(path,'source hash')
 if source is None:source=r['build']['source_sha256'];binaries=r['build']['binaries_sha256']
 assert source==r['build']['source_sha256'] and binaries==r['build']['binaries_sha256']
 processes=j[1:-1];assert len(processes)==16 and all(e['kind']=='process' for e in processes)
 decoded=[]
 for index,e in enumerate(processes):
  assert e['returncode']==0 and not bytes.fromhex(e['stderr_hex'])
  assert e['iterations']==(1 if index<4 else 100)
  assert e['command'][-1]==str(e['iterations']) and Path(e['command'][0]).name==e['runner']
  assert len(e['command'])==3
  lines=bytes.fromhex(e['stdout_hex']).decode().splitlines();rows=[];rss=[]
  for line in lines:
   if line.startswith('MEMORY\t'):rss.append(int(line.split()[2]));continue
   w,s,ns,checksum,state=line.split('\t');sample=int(s);ns=int(ns);checksum=int(checksum)
   assert state in ('ok','unsupported') and 0<=sample<7 and ns>=0
   if 'readlink-' in w:
    size=int(w.rsplit('-',1)[1]);assert checksum==(0 if state=='unsupported' else (size+240)*e['iterations'])
   rows.append(dict(workload=w,sample=sample,ns_per_call=None if state=='unsupported' else ns,checksum=checksum,state=state))
  assert len(rows)==280 and len({(x['workload'],x['sample']) for x in rows})==280 and len(rss)==1
  assert len({x['workload'] for x in rows})==40
  if index<4:assert e['runner']==('goose-fs','goose-stdlib','rust','go')[index]
  else:
   b=r['batches'][index-4];assert b['runner']==e['runner'] and (b['round'],b['position'])==((index-4)//4,(index-4)%4)
   assert b['peak_rss_kib']==rss[0]
   decoded.extend(dict(round=b['round'],position=b['position'],runner=e['runner'],**x) for x in rows)
 assert decoded==r['samples']
 cells={}
 for prefix in ('','root-'):
  for size in (64,256,4095):
   workload=f'{prefix}readlink-{size}';cells[workload]={}
   assert r['fixtures_sha256'][f'symlink-{size}']==hashlib.sha256(b'x'*size).hexdigest()
   for name in ('goose-fs','goose-stdlib','rust','go'):
    rows=[x for x in decoded if x['workload']==workload and x['runner']==name]
    assert len(rows)==21
    absent=name=='goose-stdlib' or (name=='rust' and prefix=='root-')
    assert all(x['state']==('unsupported' if absent else 'ok') for x in rows)
    cells[workload][name]=None if absent else statistics.median(x['ns_per_call'] for x in rows)
 results.append(dict(pass_number=i,medians_ns=cells))
 total+=len(decoded);unsupported+=sum(x['state']=='unsupported' for x in decoded);streams+=len(processes)
print(json.dumps(dict(measured_source=r['source_revision'],rows=total,timed_rows=total-unsupported,unsupported_rows=unsupported,
 streams=streams,preflight_streams=12,timed_streams=36,readlink_rows=1512,readlink_timed_rows=945,readlink_unsupported_rows=567,
 passes=results,assessment='descriptive native API task costs; no matched-policy or SOTA claim',external_statuses=outer),indent=2))
