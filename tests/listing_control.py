#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise real A/A recording and fail-closed provenance gates."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
ROOT=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--goose',required=True)
a=p.parse_args();directory=ROOT/'.build/listing-control';manifest=directory/'build.json'
record=json.loads(manifest.read_text())
with tempfile.TemporaryDirectory(dir=ROOT/'.build') as t:
    temp=Path(t)
    command=['python3',str(ROOT/'bench/listing-measure.py'),'--goose',str(Path(a.goose).resolve()),
        '--cc',record['cc_path'],'--identical-control','--baseline',str(directory/'a'),
        '--full',str(directory/'b'),'--baseline-revision',record['baseline_revision'],
        '--rounds','1','--iterations','1','--creation-order','shuffled']
    output=temp/'valid.json'
    subprocess.run([*command,'--build-manifest',str(manifest),'--output',str(output)],check=True)
    rows=json.loads(output.read_text())['samples'];assert len(rows)==1064
    assert {r['variant'] for r in rows}=={'a','b'}
    # Give copied manifests otherwise valid inputs; missing files must not
    # mask a missing gate in a negative test.
    for name in ('a','b',*record['rendered_sources_sha256']):
        shutil.copy2(directory/name,temp/name)
    negative=command.copy()
    negative[negative.index('--baseline')+1]=str(temp/'a')
    negative[negative.index('--full')+1]=str(temp/'b')
    copied=temp/'copied.json';copied.write_text(json.dumps(record))
    subprocess.run([*negative,'--build-manifest',str(copied),'--output',str(temp/'copied-result.json')],check=True)
    for field,value in [('profile','listing'),('identical_executables',False),
                        ('identical_sections',False),('sources_sha256',{})]:
        bad=copy.deepcopy(record);bad[field]=value
        path=temp/'bad.json';path.write_text(json.dumps(bad));target=temp/'absent.json'
        result=subprocess.run([*negative,'--build-manifest',str(path),'--output',str(target)],capture_output=True)
        assert result.returncode!=0 and b'AssertionError' in result.stderr and not target.exists(),field
    (temp/'b').write_bytes((directory/'b').read_bytes()+b'changed')
    valid=temp/'build.json';valid.write_text(json.dumps(record))
    cmd=negative
    result=subprocess.run([*cmd,'--build-manifest',str(valid),'--output',str(temp/'changed.json')],capture_output=True)
    assert result.returncode!=0 and not (temp/'changed.json').exists()
    for script in ('bench/listing-control-build.py','bench/listing-measure.py'):
        result=subprocess.run(['python3','-O',str(ROOT/script),'--help'],capture_output=True)
        assert result.returncode!=0 and b'requires Python assertions' in result.stderr
    target=temp/'symlink-output';target.mkdir();victim=temp/'victim';victim.write_bytes(b'unchanged')
    artifacts=('a','b','a-build.log','b-build.log','runner.goose','build.json')
    for name in artifacts:(target/name).symlink_to(victim)
    subprocess.run(['python3',str(ROOT/'bench/listing-control-build.py'),'--revision',record['baseline_revision'],
        '--goose',str(Path(a.goose).resolve()),'--cc',record['cc_path'],'--output-dir',str(target)],check=True)
    assert victim.read_bytes()==b'unchanged'
    assert all(not (target/name).is_symlink() for name in artifacts)
print('A/A recording and profile/source/eligibility/binary/optimized-Python rejection passed')
