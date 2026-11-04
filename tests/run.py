#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run a public-interface program in a private disposable filesystem fixture."""
import os
import subprocess
import sys
import tempfile
with tempfile.TemporaryDirectory(prefix='goose-fs-') as root:
    if any('api' in x for x in sys.argv[1:]):
        os.mkdir(root+'/adversarial')
        with open(root+'/adversarial/target', 'wb') as f: f.write(b'protected')
        os.symlink('target', root+'/adversarial/link')
        os.symlink('adversarial', root+'/ancestor')
        os.mkfifo(root+'/adversarial/fifo')
    subprocess.run([*sys.argv[1:], root], check=True, timeout=60)
