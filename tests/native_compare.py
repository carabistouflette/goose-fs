#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression checks for finite native-API recording retention (build first)."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parent.parent
compiler=sys.argv[1]
with tempfile.TemporaryDirectory(prefix='goose-fs-recorder-') as tmp:
    directory=Path(tmp)
    def run(path,*extra,optimized=False):
        return subprocess.run([sys.executable,*(['-O'] if optimized else []),'bench/compare/run.py','--goose',compiler,'--iterations','1','--rounds','1','--output',str(path),*extra],cwd=ROOT,capture_output=True,timeout=90)
    output=directory/'complete.json'
    result=run(output);assert result.returncode==0,result.stderr
    record=json.loads(output.read_text());events=[json.loads(x) for x in output.with_suffix('.jsonl').read_text().splitlines()]
    assert record['status']=='complete' and events[0]['kind']=='start' and events[-1]['kind']=='finish'
    processes=[e for e in events if e['kind']=='process'];assert len(processes)==8
    assert all(e['returncode']==0 and not bytes.fromhex(e['stderr_hex']) for e in processes)
    before=hashlib.sha256(output.read_bytes()).hexdigest();journal=output.with_suffix('.jsonl').read_bytes()
    assert run(output).returncode!=0 and hashlib.sha256(output.read_bytes()).hexdigest()==before and output.with_suffix('.jsonl').read_bytes()==journal
    dangling=directory/'dangling.json';target=directory/'absent';dangling.symlink_to(target)
    assert run(dangling).returncode!=0 and dangling.is_symlink() and not target.exists()
    optimized=directory/'optimized.json'
    assert run(optimized,optimized=True).returncode!=0 and not optimized.exists()
    failed=directory/'timeout.json';result=run(failed,'--timeout','0.000001')
    assert result.returncode!=0
    record=json.loads(failed.read_text());events=[json.loads(x) for x in failed.with_suffix('.jsonl').read_text().splitlines()]
    assert record['status']=='failed' and events[-1]['kind']=='failure' and any(e['kind']=='process-failure' for e in events)
    before=failed.read_bytes();assert run(failed).returncode!=0 and failed.read_bytes()==before
print('native recorder completion, exclusive/dangling reservations, timeout retention and -O rejection passed')
