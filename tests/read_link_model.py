#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Differential byte/limit and concurrent final-entry replacement checks."""
import ctypes as c
import errno
import os
from pathlib import Path
import random
import sys
import tempfile
import threading
class Slice(c.Structure):
    _fields_=[('data',c.c_void_p),('length',c.c_int64)]
lib=c.CDLL(sys.argv[1])
for name in ('gf_read_link','gf_root_read_link','gf_context_create','gf_context_close','gf_root_open'):
    getattr(lib,name).restype=c.c_int64
lib.gf_read_link.argtypes=[Slice,c.c_int64,Slice,Slice]
lib.gf_root_read_link.argtypes=[c.c_int64,c.c_int64,Slice,c.c_int64,Slice,Slice]
lib.gf_context_create.argtypes=[Slice];lib.gf_context_close.argtypes=[c.c_int64,Slice]
lib.gf_root_open.argtypes=[c.c_int64,Slice,Slice]
def view(buf,n=None):return Slice(c.addressof(buf),len(buf) if n is None else n)
def fdcount():return len(os.listdir('/proc/self/fd'))
initial=fdcount();m=(c.c_int64*3)();assert lib.gf_context_create(view(m,3))==0;ctx=m[1]
rng=random.Random(65801)
with tempfile.TemporaryDirectory(prefix='goose-fs-links-') as temp:
    directory=Path(temp);base=os.fsencode(temp)
    path=c.create_string_buffer(base);assert lib.gf_root_open(ctx,view(path,len(base)),view(m,3))==0;root=m[1]
    def call(name,limit,relative):
        raw=name if relative else base+b'/'+name
        path=c.create_string_buffer(raw);out=c.create_string_buffer(limit+1);meta=(c.c_int64*3)(99,99,99)
        code=lib.gf_root_read_link(ctx,root,view(path,len(raw)),limit,view(out),view(meta,3)) if relative else lib.gf_read_link(view(path,len(raw)),limit,view(out),view(meta,3))
        return code,meta[0],out.raw[:meta[1]],meta[1],meta[2]
    baseline=fdcount()
    skipped=0
    for iteration in range(500):
        n=rng.choice([1,2,254,255,256,257,511,512,513,4095,rng.randrange(1,4096)])
        target=bytes(rng.randrange(1,256) for _ in range(n))
        try:os.symlink(target,base+b'/next')
        except OSError as error:
            if error.errno!=errno.ENAMETOOLONG:raise
            skipped+=1;continue
        os.replace(base+b'/next',base+b'/link')
        for limit in set((0,n-1,n,n+1,rng.randrange(0,4097))):
            for relative in (False,True):
                result=call(b'link',limit,relative)
                assert result==((0,0,target,n,0) if n<=limit else (2,0,b'',0,0)),(iteration,n,limit,relative,result)
    print(f'Seeded cases: {500-skipped} checked, {skipped} filesystem target-length exclusions',flush=True)
    # Atomic replacement permits either complete target, never a combined value.
    targets=(b'a'*31,b'b'*513);stop=threading.Event();errors=[]
    def writer():
        try:
            while not stop.is_set():
                for value in targets:
                    os.symlink(value,base+b'/next');os.replace(base+b'/next',base+b'/link')
        except BaseException as error:errors.append(error)
    os.unlink(base+b'/link');os.symlink(targets[0],base+b'/link')
    thread=threading.Thread(target=writer);thread.start()
    try:
        for _ in range(1000):
            code,error,data,n,extra=call(b'link',513,True)
            assert code==0 and error==0 and data in targets and n==len(data) and extra==0
    finally:stop.set();thread.join(timeout=10)
    assert not thread.is_alive() and not errors
    assert fdcount()==baseline
assert lib.gf_context_close(ctx,view(m,3))==0 and fdcount()==initial
print('Seeded byte/limit cases +1000 concurrent replacement observations and FD balance passed')
