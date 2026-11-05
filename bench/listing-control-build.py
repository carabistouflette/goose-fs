#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independently build identical trusted sources twice at the same paths."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from listing_provenance import ROOT,sources
from compare.provenance import goose_stdlib

if not __debug__:raise SystemExit('benchmark validation requires Python assertions; disable optimization')
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--revision',required=True,help='full trusted library commit')
p.add_argument('--goose',required=True)
p.add_argument('--cc',default='gcc')
p.add_argument('--output-dir',type=Path,default=ROOT/'.build/listing-control')
a=p.parse_args()
if not re.fullmatch('[0-9a-f]{40}',a.revision):p.error('revision must be a full lowercase commit hash')
out=a.output_dir.resolve();allowed=(ROOT/'.build').resolve()
if out==allowed or not out.is_relative_to(allowed):p.error('output directory must be inside this checkout .build directory')
out.mkdir(parents=True,exist_ok=True)
def capture(args):return subprocess.check_output(args,cwd=ROOT,text=True,timeout=30).strip()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def publish(name,data,mode=0o600):
    # Replace output entries without following preexisting file symlinks.
    with tempfile.TemporaryDirectory(prefix='publish-',dir=out) as t:
        staged=Path(t)/'artifact';staged.write_bytes(data);staged.chmod(mode)
        staged.replace(out/name)
compiler=str(Path(a.goose).resolve());cc_path=shutil.which(a.cc)
if not cc_path:p.error('C compiler not found')
cc_path=str(Path(cc_path).resolve())
def tools():return dict(goose_sha256=digest(compiler),goose=capture([compiler,'--version']),
    cc=capture([cc_path,'--version']),cc_sha256=digest(cc_path),stdlib=goose_stdlib(compiler))
with (out/'build.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    manifest=out/'build.json';manifest.unlink(missing_ok=True)
    initial=sources();versions=tools();revision=capture(['git','rev-parse','HEAD'])
    template=(ROOT/'bench/listing.goose.in').read_text()
    calls='\n'.join(f'    if api == {i} {{ result = fs::{name}({prefix}budget, fs::MAX_ENTRIES, entries); }}'
        for i,(name,prefix) in enumerate([('list','path, '),('list_sorted','path, '),
                                        ('list_at','root, ".", '),('list_sorted_at','root, ".", ')]))
    rendered=template.replace('@LISTING_CALLS@',calls)
    entries=subprocess.check_output(['git','ls-tree','-r','-z',a.revision,'--',
        'fs.goose','fs.build','GOOSE_REVISION','native'],cwd=ROOT,timeout=30).split(b'\0')
    exported={}
    for entry in filter(None,entries):
        header,raw=entry.split(b'\t',1);mode,kind,_=header.split()
        name=raw.decode();path=PurePosixPath(name)
        if mode not in (b'100644',b'100755') or kind!=b'blob' or path.is_absolute() or '..' in path.parts:
            raise ValueError('only regular trusted source files can be exported')
        exported[name]=subprocess.check_output(['git','show',f'{a.revision}:{name}'],cwd=ROOT,timeout=30)
    if not {'fs.goose','fs.build','GOOSE_REVISION','native/fs.c','native/fs.h'}<=exported.keys():
        raise ValueError('incomplete source revision')
    hashes={name:hashlib.sha256(data).hexdigest() for name,data in exported.items()}
    binaries={};sections={};logs={}
    with tempfile.TemporaryDirectory(prefix='listing-control-',dir=allowed) as temp:
        build=Path(temp)/'build'
        for label in ('a','b'):
            if build.exists():shutil.rmtree(build)
            build.mkdir(mode=0o700)
            for name,data in exported.items():
                target=build/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            source=build/'bench/runner.goose';source.parent.mkdir();source.write_text(rendered)
            env=dict(os.environ,GOOSE_STDLIB=versions['stdlib']['directory'],GOOSE_HOME=str(build/'home'))
            log=build/'compile.log'
            with log.open('w') as stream:
                compiled=subprocess.run([compiler,'build',str(source),'--cc',cc_path,'-O2','-o',str(build/'runner')],
                               cwd=build,env=env,stdout=stream,stderr=subprocess.STDOUT,check=False,timeout=180)
            publish(f'{label}-build.log',log.read_bytes());logs[label]=digest(log)
            compiled.check_returncode()
            publish(label,(build/'runner').read_bytes(),0o700)
            binaries[label]=digest(out/label)
            subprocess.run(['objcopy','--dump-section',f'.text={build}/text',
                '--dump-section',f'.rodata={build}/rodata',str(out/label),str(build/'probe')],check=True,timeout=30)
            sections[label]={name:digest(build/name) for name in ('text','rodata')}
            assert digest(out/label)==binaries[label]
        build_path=str(build);home_path=str(build/'home')
    publish('runner.goose',rendered.encode())
    assert sources()==initial and tools()==versions and capture(['git','rev-parse','HEAD'])==revision
    record=dict(profile='identical-control',source_revision=revision,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_dirty=bool(capture(['git','status','--porcelain'])),sources_sha256=initial,
        baseline_revision=a.revision,baseline_sources_sha256=hashes,
        binaries_sha256=binaries,sections_sha256=sections,build_logs_sha256=logs,
        rendered_sources_sha256={'runner.goose':digest(out/'runner.goose')},
        goose_sha256=versions['goose_sha256'],goose_stdlib=versions['stdlib'],cc=versions['cc'],
        cc_path=cc_path,cc_sha256=versions['cc_sha256'],goose=versions['goose'],
        flags=['-O2'],build_path=build_path,goose_home=home_path,
        build_environment={key:os.environ.get(key) for key in ('CFLAGS','CPPFLAGS','LDFLAGS','SOURCE_DATE_EPOCH','LD_PRELOAD','GLIBC_TUNABLES','MALLOC_CONF')},
        identical_executables=binaries['a']==binaries['b'],identical_sections=sections['a']==sections['b'])
    publish('build.json',(json.dumps(record,indent=2)+'\n').encode())
    if not record['identical_executables'] or not record['identical_sections']:
        raise SystemExit('A/A builds differ; evidence retained, timing is ineligible')
    print('Independent matched-path A/A executables and measured sections are byte-identical')
