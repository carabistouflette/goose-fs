#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the README examples and check their normal error paths, without timing."""
from pathlib import Path
import subprocess
import sys
import tempfile
if not __debug__:raise SystemExit('Python optimization disables example checks')
ROOT=Path(__file__).resolve().parent.parent
compiler=str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix='goose-fs-examples-') as temporary:
    root=Path(temporary).resolve();data=root/'hello.txt';data.write_bytes(b'hello\n')
    directory=root/'entries';directory.mkdir()
    for name in ('a','b','c'):(directory/name).touch()
    def example(name,path,expected):
        result=subprocess.run([compiler,'run',f'examples/{name}.goose','--',str(path)],cwd=ROOT,capture_output=True,text=True,timeout=90)
        if result.returncode or expected not in result.stdout:raise AssertionError((name,path,expected,result.returncode,result.stdout,result.stderr))
    example('read',data,'read 6 bytes')
    example('stream',data,'read 6 bytes in bounded chunks')
    example('root',directory,'listed 3 owned entries')
    example('read','relative','invalid input')
    example('read',directory,'not a regular file')
    example('read',root/'missing','OS error')
    example('stream','relative','invalid input')
    example('stream',root/'missing','OS error')
    example('root',root/'missing','OS error')
print('README examples: three successful commands and six normal error paths passed')
