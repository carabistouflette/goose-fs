#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare public sorted enumeration with Python's unsigned byte ordering."""
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
rng = random.Random(49137)
for count in [0, 1, 2, 15, 4096]:
    with tempfile.TemporaryDirectory(prefix='goose-fs-sorted-') as root:
        names = [b'a', b'aa', b'ab', b'a-', b'A', b'\x7f', b'\x80', b'\xff', b'line\nbreak', b'carriage\rreturn']
        names = (names + [f'prefix-{i:04d}'.encode() for i in range(count)])[:count]
        rng.shuffle(names)
        for name in names:
            fd = os.open(os.fsencode(root)+b'/'+name, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
            os.close(fd)
        expected = b''.join(name+b'\0' for name in sorted(names))
        for program in sys.argv[1:]:
            result = subprocess.run([str(Path(program).resolve()), root, str(sum(len(n)+2 for n in names)), str(count)],
                                    capture_output=True, check=True, timeout=30)
            assert result.stdout == expected, (count, program, result.stdout[:100])
print('public byte-sorted oracle passed empty/singleton/prefix/binary/4096-entry fixtures')
