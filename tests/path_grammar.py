#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exhaustive byte grammar agreement between Python spec, Goose and native C."""
import ctypes as c
import itertools
from pathlib import Path
import subprocess
import sys
import tempfile

class Slice(c.Structure):
    _fields_=[('data',c.c_void_p),('len',c.c_int64)]

def expected(path,relative):
    if not 1<=len(path)<=4095 or b'\0' in path:return False
    if relative:
        if path==b'.':return True
        if path.startswith(b'/'):return False
        parts=path.split(b'/')
    else:
        if path==b'/':return True
        if not path.startswith(b'/'):return False
        parts=path[1:].split(b'/')
    return all(part not in [b'',b'.',b'..'] for part in parts)

cases=[bytes(chars) for length in range(8) for chars in itertools.product([0,46,47,97,255],repeat=length)]
for length in [4094,4095,4096]:cases += [b'a'*length,b'/'+b'a'*(length-1),b'a/'*(length//2)+b'a'*(length%2)]
reference=bytes(expected(path,relative) for path in cases for relative in [False,True])
lib=c.CDLL(sys.argv[3]);destination=c.create_string_buffer(4098)
for name in ['gf_path_copy','gf_relative_copy']:
    fn=getattr(lib,name);fn.restype=c.c_bool;fn.argtypes=[Slice,c.c_void_p]
for path in cases:
    source=c.create_string_buffer(path)
    for relative,name in [(False,'gf_path_copy'),(True,'gf_relative_copy')]:
        destination[0]=destination[4097]=b'!'
        actual=getattr(lib,name)(Slice(c.addressof(source),len(path)),c.addressof(destination)+1)
        assert destination[0]==destination[4097]==b'!'
        assert actual==expected(path,relative),(name,path[:80],len(path),actual)
        if actual:assert c.string_at(c.addressof(destination)+1,len(path)+1)==path+b'\0'
with tempfile.NamedTemporaryFile(prefix='goose-fs-path-grammar-') as fixture:
    fixture.write(b''.join(len(path).to_bytes(2,'little')+path for path in cases));fixture.flush()
    for binary in sys.argv[1:3]:
        result=subprocess.check_output([str(Path(binary).resolve()),fixture.name],timeout=60)
        assert result==reference,(binary,len(result),len(reference))
print(f'{len(cases)} exhaustive/boundary paths agree across Python, native C, optimized and debug Goose')
