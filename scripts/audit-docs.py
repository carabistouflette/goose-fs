#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify the source bridge and derive descriptive dispersion; no timing runs."""
import argparse
import hashlib
from functools import lru_cache
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
if not __debug__:raise SystemExit('Python optimization disables validation')
ROOT=Path(__file__).resolve().parent.parent
BASE='60cec1e1956962772fff6091b4c7ff1876533f9e'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(data):return hashlib.sha256(data).hexdigest()
def require(ok,message):
    if not ok:raise SystemExit(message)
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--goose',help='also require the recorded local compiler/dependency identities')
p.add_argument('--output',type=Path,required=True)
p.add_argument('--dispersion',type=Path,required=True)
a=p.parse_args()
require(a.output.resolve()!=a.dispersion.resolve(),'Audit and dispersion outputs must be distinct')
public={ROOT/'docs/announcement-audit.json',ROOT/'docs/performance-dispersion.json'}
build=ROOT/'.build'
require(not build.is_symlink() and build.resolve()==build,'Private .build must not redirect to another directory')
for destination in (a.output.resolve(),a.dispersion.resolve()):
    require(destination in public or build in destination.parents,'Output must be one of the two derived docs files or inside this checkout .build; source/history writes are forbidden')
production=['fs.goose','fs.build','GOOSE_REVISION',*git('ls-tree','-r','--name-only',BASE,'native').decode().splitlines()]
require(all((ROOT/f).read_bytes()==git('show',f'{BASE}:{f}') for f in production),'Production changed; the documentation-only bridge no longer applies')
latest=ROOT/'bench/results/2026-11-05-read-link'
r=json.loads((latest/'pass-1.json').read_text());bridge=[]
for name,expected in r['build']['source_sha256'].items():
    actual=sha((ROOT/name).read_bytes())
    require(actual==expected or name.endswith('.md'),f'Compiled/driver input changed: {name}')
    bridge.append(dict(path=name,recorded_sha256=expected,current_sha256=actual,scope='identical' if actual==expected else 'documentation only; not compiled'))
checks=None
if a.goose:
    sys.path.insert(0,str(ROOT/'bench/compare'))
    from provenance import toolchains
    actual=toolchains(str(Path(a.goose).resolve()),'gcc','1.99.1');recorded=r['build']['toolchains']
    checks={k:actual[k]==v for k,v in recorded.items() if k!='goose_stdlib'}
    checks['stdlib_sources']=actual['goose_stdlib']['sources_sha256']==recorded['goose_stdlib']['sources_sha256']
    require(all(checks.values()),'Toolchain differs: recorded numbers do not describe that compiler build')
files=git('ls-tree','-r','--name-only',BASE,'bench/results').decode().splitlines()
raw=[f for f in files if not f.endswith('/README.md')]
require(all((ROOT/f).read_bytes()==git('show',f'{BASE}:{f}') for f in raw),'Historical artifact changed')
def stdlib_locations(value,path=''):
    found=[]
    if isinstance(value,dict):
        for key,item in value.items():
            location=path+'.'+key if path else key
            if key in ('stdlib','goose_stdlib') and isinstance(item,dict) and 'sources_sha256' in item:
                found.append(dict(path=location,matches_current=item['sources_sha256']==r['build']['toolchains']['goose_stdlib']['sources_sha256']))
            elif isinstance(item,dict):found.extend(stdlib_locations(item,location))
    return found
@lru_cache(None)
def changed_checkout(revision):
    changed=[]
    for name in production:
        old=subprocess.run(['git','show',f'{revision}:{name}'],cwd=ROOT,capture_output=True)
        if old.returncode or old.stdout!=(ROOT/name).read_bytes():changed.append(name)
    return changed
def revisions(value,path=''):
    refs=[]
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('samples','rows','processes','batches'):continue
            refs.extend(revisions(item,path+'.'+key if path else key))
    elif isinstance(value,str) and 'revision' in path.lower() and re.fullmatch('[0-9a-f]{40}',value):
        refs.append(dict(path=path,revision=value))
    return refs
inventory=[];dispersion=[]
for d in sorted((ROOT/'bench/results').iterdir()):
    if not d.is_dir():continue
    records=[]
    for f in sorted(d.glob('*.json')):
        v=json.loads(f.read_text())
        if not isinstance(v,dict):continue
        revision=v.get('build',{}).get('source_revision') or v.get('source_revision')
        rows=v.get('samples',v.get('rows',[]))
        if not revision or not isinstance(rows,list) or not rows:continue
        maps=stdlib_locations({'build':v.get('build',{}),'build_manifest':v.get('build_manifest',{})})
        records.append(dict(file=f.name,measured_revision=revision,measured_checkout_changed_production_paths=changed_checkout(revision),recorded_revision_references=revisions(v),stdlib_hashes_recorded=bool(maps),stdlib_source_maps=maps))
        groups={};unsupported=0
        for row in rows:
            value=row.get('ns_per_call',row.get('ns'))
            if value is None or row.get('state')=='unsupported':unsupported+=1;continue
            require(isinstance(value,(int,float)) and value>=0,'Invalid numeric observation')
            key=tuple((k,row[k]) for k in ('workload','case','variant','runner','batch') if k in row)
            groups.setdefault(key,{}).setdefault(row['round'],[]).append(value)
        def spread(values):
            q=statistics.quantiles(values,n=4,method='inclusive')
            return dict(means=len(values),minimum=min(values),q1=q[0],median=statistics.median(values),q3=q[2],maximum=max(values))
        cells=[]
        for key,rounds in sorted(groups.items()):
            values=[n for group in rounds.values() for n in group]
            cells.append(dict(cell=dict(key),unit='ns/pair' if any(k=='workload' and (str(v).startswith('create-remove-') or str(v).endswith('-pair')) for k,v in key) else 'ns/call',processes=len(rounds),pooled=spread(values),per_process=[dict(round=i,**spread(x)) for i,x in sorted(rounds.items())]))
        dispersion.append(dict(file=str(f.relative_to(ROOT)),rows=len(rows),unsupported_rows=unsupported,cells=cells))
    inventory.append(dict(profile=d.name,status='source-equivalent on recorded platform/toolchain' if d==latest else 'historical only; no current-main numerical claim',records=records))
@lru_cache(None)
def anchors(path):
    text=path.read_text();result=set(re.findall(r'<[^>]+(?:id|name)=["\']([^"\']+)["\']',text));counts={};fenced=False
    for line in text.splitlines():
        if line.lstrip().startswith(('```','~~~')):fenced=not fenced;continue
        if fenced:continue
        heading=re.match(r'^#{1,6}\s+(.+?)\s*#*$',line)
        if not heading:continue
        slug=re.sub(r'[^\w\s-]','',heading[1].lower()).strip().replace(' ','-')
        n=counts.get(slug,0);counts[slug]=n+1;result.add(slug if not n else f'{slug}-{n}')
    return result
prose=[];link_count=0
for name in sorted(set(git('ls-files','--cached','--others','--exclude-standard').decode().splitlines())):
    if not name.endswith('.md'):continue
    text=(ROOT/name).read_text();prose.append(dict(path=name,sha256=sha(text.encode()),scope='historical result' if name.startswith('bench/results/') else 'audited guide/protocol'))
    for target in re.findall(r'\]\(([^)]+)\)',text):
        target=target.strip('<>')
        if re.match(r'^[a-zA-Z]+:',target) or target.startswith('/') or ' ' in target:continue
        base,separator,fragment=target.partition('#')
        destination=((ROOT/name).parent/base).resolve() if base else ROOT/name
        require(destination.exists() or destination in (a.output.resolve(),a.dispersion.resolve()),f'Broken link: {name}: {target}')
        if fragment and destination.suffix in ('.md','.html'):
            require(fragment in anchors(destination),f'Broken anchor: {name}: {target}')
        link_count+=1

report=dict(task='GL-DOCSFS-01',runtime_revision=BASE,measured_revision=r['source_revision'],production_sha256={f:sha((ROOT/f).read_bytes()) for f in production},source_bridge=bridge,live_toolchain_checks=checks,recorded_toolchains=r['build']['toolchains'],platform=r['platform'],filesystem=r['filesystem'],historical_artifacts_unchanged=len(raw),benchmark_inventory=inventory,prose_inventory=prose,local_links_checked=link_count,limitations=['Current-source bridge is not a new measurement or hermetic executable/sysroot capture','Historical timings remain historical even when an operation body is unchanged','Quantiles/ranges describe recorded means; seven means in a process are not independent process replicas'])
for path,value in ((a.output,report),(a.dispersion,dispersion)):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')
print(f'Checked {len(prose)} prose files, {len(inventory)} profiles, {len(raw)} unchanged artifacts; no timing executed')
