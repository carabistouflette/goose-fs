#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Real four-replica recording and fail-closed profile/revision checks."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--goose',required=True);a=p.parse_args()
directory=ROOT/'.build/listing-matched';record=json.loads((directory/'build.json').read_text())
with tempfile.TemporaryDirectory(dir=ROOT/'.build') as t:
    temp=Path(t)
    for name in (*record['binaries_sha256'],*record['rendered_sources_sha256']):shutil.copy2(directory/name,temp/name)
    command=['python3',str(ROOT/'bench/listing-measure.py'),'--matched-comparison','--goose',str(Path(a.goose).resolve()),
        '--cc',record['cc_path'],'--baseline',str(temp/'a1'),'--full',str(temp/'b1'),
        '--baseline-revision',record['variant_revisions']['a1'],'--candidate-revision',record['variant_revisions']['b1'],
        '--rounds','1','--iterations','1','--creation-order','shuffled']
    manifest=temp/'build.json';manifest.write_text(json.dumps(record));output=temp/'valid.json'
    subprocess.run([*command,'--build-manifest',str(manifest),'--output',str(output)],check=True)
    rows=json.loads(output.read_text())['samples'];assert len(rows)==2128 and {r['variant'] for r in rows}=={'a1','a2','b1','b2'}
    for field,value in [('profile','identical-control'),('identical_executables',False),
                        ('identical_sections',False),('sources_sha256',{}),('variant_revisions',{}),
                        ('variant_revisions',dict(record['variant_revisions'],a1=record['variant_revisions']['b1'],b1=record['variant_revisions']['a1'])),
                        ('sections_sha256',dict(record['sections_sha256'],b2={})),
                        ('variant_revisions',dict(record['variant_revisions'],b2='0'*40))]:
        # CI may use one revision in both roles, making a role swap a no-op.
        if value==record.get(field):continue
        bad=copy.deepcopy(record);bad[field]=value;manifest.write_text(json.dumps(bad))
        result=subprocess.run([*command,'--build-manifest',str(manifest),'--output',str(temp/'absent.json')],capture_output=True)
        assert result.returncode!=0 and b'AssertionError' in result.stderr and not (temp/'absent.json').exists(),field
    manifest.write_text(json.dumps(record));wrong=command.copy();wrong[wrong.index('--candidate-revision')+1]='0'*40
    result=subprocess.run([*wrong,'--build-manifest',str(manifest),'--output',str(temp/'wrong.json')],capture_output=True)
    assert result.returncode!=0 and not (temp/'wrong.json').exists()
    redirect=temp/'redirect';shutil.copy2(temp/'b2',redirect);(temp/'b2').unlink();(temp/'b2').symlink_to(redirect)
    result=subprocess.run([*command,'--build-manifest',str(manifest),'--output',str(temp/'symlink.json')],capture_output=True)
    assert result.returncode!=0 and not (temp/'symlink.json').exists()
    (temp/'b2').unlink();shutil.copy2(directory/'b2',temp/'b2')
    for label in ('a2','b2'):
        original=(temp/label).read_bytes();(temp/label).write_bytes(original+b'changed')
        result=subprocess.run([*command,'--build-manifest',str(manifest),'--output',str(temp/'changed.json')],capture_output=True)
        assert result.returncode!=0 and not (temp/'changed.json').exists()
        (temp/label).write_bytes(original)
print('Four-replica checksums, profile/source/revision/eligibility and modified-replica rejection passed')
