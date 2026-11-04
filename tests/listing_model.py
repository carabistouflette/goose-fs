#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check staged native listings and all four public APIs at packed-byte boundaries."""
import ctypes as c
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from listing_fixture import names_for_bytes

class Slice(c.Structure):
    _fields_ = [('data', c.c_void_p), ('len', c.c_int64)]
I = c.c_int64
lib = c.CDLL(os.environ.get('FS_HANDLES_LIBRARY', '.build/fs-handles.so'))
for name, args in {'list':[Slice,I,Slice,I], 'root_list_sized':[I,I,Slice,I,Slice,I],
                   'context_create':[], 'root_open':[I,Slice], 'root_close':[I,I], 'context_close':[I],
                   'call':[I,Slice,Slice,I,Slice], 'root_list':[I,I,Slice,Slice,I]}.items():
    f = getattr(lib, 'gf_'+name); f.restype=I; f.argtypes=args+[Slice]
def raw(value):
    buf=c.create_string_buffer(os.fsencode(value)); return buf,Slice(c.addressof(buf),len(os.fsencode(value)))
def invoke(name,*args,fields=4):
    m=(I*fields)(*([165]*fields)); code=getattr(lib,'gf_'+name)(*args,Slice(c.addressof(m),fields))
    return code,list(m)

def decode(data,count):
    names=[];pos=0
    for _ in range(count):
        assert 0<=data[pos]<=4; end=data.index(0,pos+1); names.append(data[pos+1:end]); pos=end+1
    assert pos==len(data); return sorted(names)

def main():
    before=len(os.listdir('/proc/self/fd'))
    with tempfile.TemporaryDirectory(prefix='goose-fs-listing-') as temp:
        ctx=invoke('context_create',fields=3)[1][1]
        for size in [0,65535,65536,65537,131072,131073,262144,262145,524288,524289,1048575,1048576]:
            path=Path(temp)/str(size);path.mkdir();names=names_for_bytes(size)
            for name in names:
                fd=os.open(os.fsencode(path)+b'/'+name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
            pb,ps=raw(path); db,ds=raw('.')
            rc,rm=invoke('root_open',ctx,ps,fields=3); assert rc==0;root=rm[1]
            for capacity in sorted({0,min(size,65536),size}):
                for rooted in [False,True]:
                    buf=c.create_string_buffer(b'!'*(capacity+2),capacity+2);out=Slice(c.addressof(buf)+1,capacity)
                    code,m=invoke('root_list_sized',ctx,root,ds,size,out,len(names)) if rooted else invoke('list',ps,size,out,len(names))
                    assert buf[0]==buf[capacity+1]==b'!'
                    if capacity<size: assert (code,m)==(5,[0,0,0,size]),(size,capacity,rooted,code,m)
                    else: assert (code,m)==(0,[0,size,len(names),0]); assert decode(bytes(buf)[1:1+size],len(names))==sorted(names)
                    for budget,cap in [(size-1,len(names)),(size,max(0,len(names)-1))] if names else []:
                        actual=min(capacity,budget);out=Slice(c.addressof(buf)+1,actual)
                        value=invoke('root_list_sized',ctx,root,ds,budget,out,cap) if rooted else invoke('list',ps,budget,out,cap)
                        assert value==(2,[0,0,0,0]),(size,capacity,rooted,value)
            # The original tuples never expose the retry result or a fourth slot.
            if size:
                out=Slice(None,0)
                assert invoke('call',1,ps,Slice(None,0),len(names),out,fields=3)==(2,[0,0,0])
                assert invoke('root_list',ctx,root,ds,out,len(names),fields=3)==(2,[0,0,0])
            for program in sys.argv[1:]:
                for api in range(4):
                    for budget,cap,expected in [(size,len(names),0),(1048576,4096,0)]+([(size-1,len(names),2),(1048576,len(names)-1,2)] if names else []):
                        result=subprocess.run([str(Path(program).resolve()),str(path),str(budget),str(cap),str(api),str(expected)],capture_output=True,check=True,timeout=30)
                        if expected: assert not result.stdout
                        else:
                            got=result.stdout.split(b'\0');assert got.pop()==b''
                            assert (got if api%2 else sorted(got))==sorted(names),(size,api)
            assert invoke('root_close',ctx,root,fields=3)==(0,[0,0,0])
            assert invoke('root_list_sized',ctx,root,ds,1048576,Slice(None,0),4096)==(4,[9,0,0,0])
        assert invoke('context_close',ctx,fields=3)==(0,[0,0,0])
    assert len(os.listdir('/proc/self/fd'))==before
    print('staged/native/public listings passed 64KiB..1MiB boundaries, exact/max budgets, limits, stale roots and descriptor balance')
if __name__=='__main__':main()
