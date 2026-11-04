#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare native locks with independent open descriptions in separate processes."""
import ctypes as c
import errno
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tempfile

class Slice(c.Structure):
    _fields_=[('data',c.c_void_p),('len',c.c_int64)]
I=c.c_int64
lib=c.CDLL(os.environ.get('FS_HANDLES_LIBRARY','.build/fs-handles.so'))
for name,args in {'context_create':[],'context_close':[I],'file_open':[I,Slice,I,I],
                  'file_close':[I,I],'file_duplicate':[I,I],'file_try_lock':[I,I,I]}.items():
    fn=getattr(lib,'gf_'+name);fn.restype=I;fn.argtypes=args+[Slice]
lib.gf_lock_contended.restype=c.c_bool;lib.gf_lock_contended.argtypes=[I]
def call(name,*args):
    out=(I*3)(); code=getattr(lib,'gf_'+name)(*args,Slice(c.addressof(out),3))
    return code,list(out)
def ok(value):
    code,meta=value;assert code==0 and meta[0]==0,(code,meta)
    return meta[1]
def opened(ctx,path):
    raw=os.fsencode(path);buf=c.create_string_buffer(raw)
    return ok(call('file_open',ctx,Slice(c.addressof(buf),len(raw)),2,0o600))
def lock(ctx,file,mode): return call('file_try_lock',ctx,file,mode)
child='''import fcntl,os,sys
fd=os.open(sys.argv[1],os.O_RDWR|os.O_CLOEXEC)
try:
 fcntl.flock(fd,(fcntl.LOCK_SH if sys.argv[2]=='shared' else fcntl.LOCK_EX)|fcntl.LOCK_NB)
 print('acquired')
except BlockingIOError: print('contended')
finally: os.close(fd)
'''
def external(path,mode,expected):
    result=subprocess.check_output([sys.executable,'-c',child,str(path),mode],text=True,timeout=10)
    assert result.strip()==expected,(mode,result,expected)
with tempfile.TemporaryDirectory(prefix='goose-fs-locks-') as root:
    path=Path(root)/'file';path.write_bytes(b'data')
    ctx=ok(call('context_create'));one=opened(ctx,path);two=opened(ctx,path)
    for mode in [1,2]:
        ok(lock(ctx,one,mode))
        external(path,'shared','acquired' if mode==1 else 'contended')
        external(path,'exclusive','contended')
        code,meta=lock(ctx,two,2);assert code==4 and lib.gf_lock_contended(meta[0]) and meta[1:]==[0,0]
        ok(lock(ctx,one,0));external(path,'exclusive','acquired')
    ok(lock(ctx,one,1));ok(lock(ctx,two,1))
    code,meta=lock(ctx,one,2);assert code==4 and lib.gf_lock_contended(meta[0])
    # Always reacquire after a failed conversion before relying on old protection.
    ok(lock(ctx,one,1));ok(lock(ctx,two,0));external(path,'exclusive','contended')
    duplicate=ok(call('file_duplicate',ctx,one));ok(lock(ctx,duplicate,0))
    external(path,'exclusive','acquired')
    ok(lock(ctx,one,2));ok(call('file_close',ctx,one));external(path,'exclusive','contended')
    ok(call('file_close',ctx,duplicate));external(path,'exclusive','acquired')
    assert lock(ctx,one,2)==(4,[errno.EBADF,0,0])
    assert lock(ctx,two,3)==(1,[0,0,0])
    ok(lock(ctx,two,2));ok(call('context_close',ctx));external(path,'exclusive','acquired')
    assert lock(ctx,two,0)==(4,[errno.EBADF,0,0])
for value in [errno.EAGAIN,errno.EWOULDBLOCK]: assert lib.gf_lock_contended(value)
for value in [0,errno.EACCES,errno.EBADF,errno.ENOLCK,errno.EINTR]: assert not lib.gf_lock_contended(value)
print('independent-process shared/exclusive lock, conversion, duplicate and last-close oracle passed')
