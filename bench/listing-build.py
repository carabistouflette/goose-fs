#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build three listing variants from one harness and retain measured input hashes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from compare.provenance import goose_stdlib
ROOT=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--goose',required=True)
p.add_argument('--cc',default='gcc')
p.add_argument('--baseline-revision',required=True)
p.add_argument('--output-dir',type=Path,default=ROOT/'.build/listing-pair')
a=p.parse_args()
a.output_dir=a.output_dir.resolve()
def capture(args):return subprocess.check_output(args,cwd=ROOT,text=True,timeout=30).strip()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sources():
    paths=[ROOT/'fs.goose',ROOT/'fs.build',ROOT/'GOOSE_REVISION',*sorted((ROOT/'native').glob('*')),
           ROOT/'bench/listing.goose.in',ROOT/'bench/listing-measure.py',ROOT/'tests/listing_fixture.py',ROOT/'bench/build-baseline.py',ROOT/'bench/compare/provenance.py',Path(__file__).resolve()]
    return {str(path.relative_to(ROOT)):digest(path) for path in paths if path.is_file()}
a.output_dir.mkdir(parents=True,exist_ok=True)
manifest=a.output_dir/'build.json';manifest.unlink(missing_ok=True)
compiler=str(Path(a.goose).resolve());initial_sources=sources();initial_compiler=digest(compiler)
initial_stdlib=goose_stdlib(compiler)
goose_env=dict(os.environ,GOOSE_STDLIB=initial_stdlib['directory'])
cc=capture([a.cc,'--version']);revision=capture(['git','rev-parse','HEAD'])
binaries={key:(a.output_dir/key).resolve() for key in ['baseline','full','adaptive']}
template=(ROOT/'bench/listing.goose.in').read_text()
legacy='\n'.join(f'    if api == {i} {{ result = fs::{name}({prefix}budget, fs::MAX_ENTRIES, entries); }}' for i,(name,prefix) in enumerate([
    ('list','path, '),('list_sorted','path, '),('list_at','root, ".", '),('list_sorted_at','root, ".", ')]))
adaptive='    let options = fs::ListOptions { byte_limit: budget, adaptive: true };\n'+\
    '\n'.join(f'    if api == {i} {{ result = fs::{name}({prefix}options, entries); }}' for i,(name,prefix) in enumerate([
    ('list','path, '),('list_sorted','path, '),('list_at','root, ".", '),('list_sorted_at','root, ".", ')]))
rendered={}
for key in binaries:
    text=template.replace('@LISTING_CALLS@',adaptive if key=='adaptive' else legacy)
    if key!='baseline': text=text.replace('import fs from "..";',f'import fs from {json.dumps(os.path.relpath(ROOT,a.output_dir.resolve()))};')
    source=a.output_dir/f'{key}-source.goose';source.write_text(text)
    subprocess.run([compiler,'format',str(source)],cwd=ROOT,check=True,timeout=30)
    rendered[source.name]=digest(source)
    if key=='baseline':
        command=['python3',str(ROOT/'bench/build-baseline.py'),'--revision',a.baseline_revision,'--goose',compiler,
                 '--cc',a.cc,'--harness',str(source),'--output',str(binaries[key])]
    else: command=[compiler,'build',str(source),'--cc',a.cc,'-O2','-o',str(binaries[key])]
    subprocess.run(command,cwd=ROOT,env=goose_env,check=True,timeout=180)
assert sources()==initial_sources and digest(compiler)==initial_compiler and capture([a.cc,'--version'])==cc
assert goose_stdlib(compiler)==initial_stdlib
assert capture(['git','rev-parse','HEAD'])==revision
old_paths=capture(['git','ls-tree','-r','--name-only',a.baseline_revision,'--','native']).splitlines()
baseline_sources={path:hashlib.sha256(subprocess.check_output(['git','show',f'{a.baseline_revision}:{path}'],cwd=ROOT,timeout=30)).hexdigest() for path in ['fs.goose','fs.build',*old_paths]}
manifest.write_text(json.dumps(dict(sources_sha256=initial_sources,binaries_sha256={k:digest(v) for k,v in binaries.items()},
    baseline_revision=a.baseline_revision,baseline_sources_sha256=baseline_sources,source_revision=revision,
    rendered_sources_sha256=rendered,source_dirty=bool(capture(['git','status','--porcelain'])),goose_sha256=initial_compiler,goose_stdlib=initial_stdlib,cc=cc,flags=['-O2']),indent=2)+'\n')
print(f'Built matched listing variants and {manifest}')
