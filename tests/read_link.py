#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Private fixtures for the public bounded-symlink interface tests."""
import os
import errno
import subprocess
import sys
import tempfile
with tempfile.TemporaryDirectory(prefix='goose-fs-readlink-') as directory:
    root=os.fsencode(directory)
    longest="long"
    for n in (1,2,254,255,256,257,511,512,513,4095):
        try:os.symlink(b'x'*n,root+f'/n{n}'.encode())
        except OSError as error:
            if n!=4095 or error.errno!=errno.ENAMETOOLONG:raise
            longest="short"
            print('4095-byte real-link fixture unsupported by this filesystem; synthetic bounds still required',flush=True)
    os.symlink(b'../\xff\n',root+b'/binary')
    os.symlink(b'/outside/absent',root+b'/\xff\n')
    os.symlink(b'cycle',root+b'/cycle')
    os.mkdir(root+b'/nested');os.symlink(b'../missing',root+b'/nested/link')
    os.symlink(b'nested',root+b'/ancestor')
    with open(root+b'/file','wb') as f:f.write(b'bytes')
    subprocess.run([*sys.argv[1:],directory,longest],check=True,timeout=90)
