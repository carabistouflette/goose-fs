#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run a public-interface program in a private disposable filesystem fixture."""
import os
import subprocess
import sys
import tempfile
api = len(sys.argv) > 1 and sys.argv[1] == '--api'
command = sys.argv[2:] if api else sys.argv[1:]
with tempfile.TemporaryDirectory(prefix='goose-fs-') as root:
    if api:
        os.symlink('absent', root+'/dangling')
        os.mkdir(root+'/denied')
        with open(root+'/denied/child', 'wb') as f: f.write(b'private')
        os.chmod(root+'/denied', 0)
        os.mkdir(root+'/adversarial')
        os.mkdir(root+'/adversarial/subdir')
        with open(root+'/adversarial/target', 'wb') as f: f.write(b'protected')
        os.symlink('target', root+'/adversarial/link')
        os.symlink('adversarial', root+'/ancestor')
        os.mkfifo(root+'/adversarial/fifo')
        os.mkdir(root+'/binary')
        for name in [b'line\nbreak', b'\xff\xfe', b'x'*255]:
            with open(os.fsencode(root)+b'/binary/'+name, 'wb') as f: f.write(b'bytes')
        with open(root+'/maximum', 'wb') as f: f.write(b'\x00\xff'*524288)
    try:
        subprocess.run([*command, root], check=True, timeout=60)
    finally:
        if api: os.chmod(root+'/denied', 0o700)
