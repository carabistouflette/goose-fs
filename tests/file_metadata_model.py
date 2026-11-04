#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Differential held-inode metadata setters, lifetimes, numeric edges and bounds."""
import ctypes as c
import errno
import itertools
import os
from pathlib import Path
import resource
import tempfile

class Slice(c.Structure):
    _fields_=[('data',c.c_void_p),('len',c.c_int64)]
class Timespec(c.Structure):
    _fields_=[('seconds',c.c_int64),('nanos',c.c_int64)]
I=c.c_int64
lib=c.CDLL(os.environ.get('FS_HANDLES_LIBRARY','.build/fs-handles.so'))
for name,args in {'context_create':[], 'context_close':[I], 'file_open':[I,Slice,I,I], 'file_close':[I,I],
                  'file_duplicate':[I,I], 'root_open':[I,Slice], 'file_metadata':[I,I],
                  'file_set_permissions':[I,I,I], 'file_set_owner':[I,I,I,I],
                  'file_set_times':[I,I,I,I,I,I,I,I], 'file_seek':[I,I,I,I]}.items():
    f=getattr(lib,'gf_'+name);f.restype=I;f.argtypes=args+[Slice]
libc=c.CDLL(None,use_errno=True)
libc.fchmod.argtypes=[c.c_int,c.c_uint];libc.fchmod.restype=c.c_int
libc.fchown.argtypes=[c.c_int,c.c_uint,c.c_uint];libc.fchown.restype=c.c_int
libc.futimens.argtypes=[c.c_int,c.POINTER(Timespec)];libc.futimens.restype=c.c_int
KEEP=(1<<30)-2;NOW=(1<<30)-1

def raw(value):
    data=os.fsencode(value);buf=c.create_string_buffer(data);return buf,Slice(c.addressof(buf),len(data))
def call(name,*args,fields=3):
    m=(I*fields)(*([165]*fields));code=getattr(lib,'gf_'+name)(*args,Slice(c.addressof(m),fields));return code,list(m)
def ok(value):
    code,m=value;assert code==0 and m[0]==0,(code,m);return m

def info(ctx,file):return ok(call('file_metadata',ctx,file,fields=18))
def reference(operation,*args):
    c.set_errno(0);rc=getattr(libc,operation)(*args);return c.get_errno() if rc else 0

def same_error(value,error):
    assert value==((4,[error,0,0]) if error else (0,[0,0,0])),(value,error)

before=len(os.listdir('/proc/self/fd'));cases=0
soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
assert hard==resource.RLIM_INFINITY or hard>=5000, 'full resource-table test requires hard RLIMIT_NOFILE >=5000'
resource.setrlimit(resource.RLIMIT_NOFILE,(max(soft,5000),hard))
with tempfile.TemporaryDirectory(prefix='goose-fs-file-meta-') as temp:
    root=Path(temp);a=root/'actual';b=root/'reference';a.write_bytes(b'contents');b.write_bytes(b'contents')
    ctx=ok(call('context_create'))[1];other=ok(call('context_create'))[1]
    pb,ps=raw(a);file=ok(call('file_open',ctx,ps,0,0))[1];duplicate=ok(call('file_duplicate',ctx,file))[1]
    rb,rs=raw(root);directory=ok(call('root_open',ctx,rs))[1];reference_fd=os.open(b,os.O_RDONLY|os.O_CLOEXEC)
    try:
        assert ok(call('file_seek',ctx,file,3,0))[1]==3;assert os.lseek(reference_fd,3,os.SEEK_SET)==3
        for mode in [0,1,0o600,0o640,0o755,0o777,0o2755,0o4755,0o1777,0o7777]:
            error=reference('fchmod',reference_fd,mode);same_error(call('file_set_permissions',ctx,file,mode),error)
            assert info(ctx,duplicate)[3]==(os.fstat(reference_fd).st_mode&0o7777);cases+=1
        initial_uid,initial_gid=os.geteuid(),os.getegid()
        for uid,gid in itertools.product([-1,initial_uid,0,4294967294],[-1,initial_gid,0,4294967294]):
            os.fchown(reference_fd,initial_uid,initial_gid);ok(call('file_set_owner',ctx,file,initial_uid,initial_gid))
            os.fchmod(reference_fd,0o6755);ok(call('file_set_permissions',ctx,file,0o6755))
            error=reference('fchown',reference_fd,uid & 0xffffffff,gid & 0xffffffff)
            same_error(call('file_set_owner',ctx,file,uid,gid),error)
            expected=os.fstat(reference_fd);actual=info(ctx,file)
            assert actual[3:6]==[expected.st_mode&0o7777,expected.st_uid,expected.st_gid];cases+=1
        os.fchown(reference_fd,initial_uid,initial_gid);ok(call('file_set_owner',ctx,file,initial_uid,initial_gid))
        os.fchmod(reference_fd,0o600);ok(call('file_set_permissions',ctx,file,0o600))
        values=[(-2,123456789),(0,0),(2200000000,999999999),(-(1<<63),0),((1<<63)-1,999999999)]
        for accessed_action,modified_action in itertools.product(range(3),repeat=2):
            for seconds,nanos in values:
                os.utime(reference_fd,ns=(10000000001,20000000002))
                ok(call('file_set_times',ctx,file,2,10,1,2,20,2))
                times=(Timespec*2)(Timespec(seconds if accessed_action==2 else 0, nanos if accessed_action==2 else KEEP if accessed_action==0 else NOW),
                                   Timespec(seconds if modified_action==2 else 0,nanos if modified_action==2 else KEEP if modified_action==0 else NOW))
                error=reference('futimens',reference_fd,times)
                # Invalid ignored values demonstrate that Keep/Now do not reinterpret them.
                value=call('file_set_times',ctx,file,accessed_action,seconds,nanos if accessed_action==2 else -(1<<63),
                           modified_action,seconds,nanos if modified_action==2 else (1<<63)-1)
                same_error(value,error);actual=info(ctx,file);expected=os.fstat(reference_fd)
                for action,index,ref_ns in [(accessed_action,9,expected.st_atime_ns),(modified_action,11,expected.st_mtime_ns)]:
                    got=actual[index]*1000000000+actual[index+1]
                    if action==1:assert abs(got-ref_ns)<5000000000
                    else:assert got==ref_ns,(action,seconds,nanos,got,ref_ns)
                cases+=1
        for mode in [-1,4096,0xffffffff]:assert call('file_set_permissions',ctx,file,mode)==(1,[0,0,0])
        for uid,gid in [(-2,-1),(-1,-2),(4294967295,-1),(-1,4294967295)]:assert call('file_set_owner',ctx,file,uid,gid)==(1,[0,0,0])
        for which in range(2):
            for nanos in [-1,1000000000]:
                args=[0,0,0,0,0,0];args[which*3:which*3+3]=[2,0,nanos]
                assert call('file_set_times',ctx,file,*args)==(1,[0,0,0])
        for action in [-1,3,999]:assert call('file_set_times',ctx,file,action,0,0,0,0,0)==(1,[0,0,0])
        assert ok(call('file_seek',ctx,duplicate,0,1))[1]==3 and os.lseek(reference_fd,0,os.SEEK_CUR)==3
        # All aliases and hard links refer to the held original inode after rename/unlink.
        linked=root/'linked';os.link(a,linked);a.rename(root/'moved');a.write_bytes(b'replacement')
        replacement_mode=a.stat().st_mode&0o7777
        ok(call('file_set_permissions',ctx,file,0o640));assert linked.stat().st_mode&0o7777==0o640
        assert a.stat().st_mode&0o7777==replacement_mode
        (root/'moved').unlink();linked.unlink();ok(call('file_set_times',ctx,file,2,-2,0,2,2200000000,1))
        assert info(ctx,duplicate)[11:13]==[2200000000,1] and a.read_bytes()==b'replacement'
        for wrong_ctx,token in [(other,file),(ctx,directory),(ctx,0),(ctx,-1)]:
            assert call('file_set_permissions',wrong_ctx,token,0o600)==(4,[errno.EBADF,0,0])
            assert call('file_set_owner',wrong_ctx,token,-1,-1)==(4,[errno.EBADF,0,0])
            assert call('file_set_times',wrong_ctx,token,0,0,0,0,0,0)==(4,[errno.EBADF,0,0])
        ok(call('file_close',ctx,file))
        assert call('file_set_times',ctx,file,0,0,0,0,0,0)==(4,[errno.EBADF,0,0])
        ok(call('file_set_permissions',ctx,duplicate,0o600))
        # Metadata setters need neither a free retained slot nor another OS fd.
        duplicated=0
        while True:
            code,m=call('file_duplicate',ctx,duplicate)
            if code:assert (code,m)==(2,[0,0,0]);break
            duplicated+=1
        assert duplicated==4094,duplicated # One live File and one Root occupy the other slots.
        held=len(os.listdir('/proc/self/fd'))
        for _ in range(100):
            ok(call('file_set_permissions',ctx,duplicate,0o600));ok(call('file_set_owner',ctx,duplicate,-1,-1))
            ok(call('file_set_times',ctx,duplicate,0,0,0,0,0,0))
        assert len(os.listdir('/proc/self/fd'))==held
    finally:
        os.close(reference_fd);ok(call('context_close',ctx));ok(call('context_close',other))
resource.setrlimit(resource.RLIMIT_NOFILE,(soft,hard))
assert len(os.listdir('/proc/self/fd'))==before
print(f'{cases} held-file syscall oracle cases, numeric edges, alias/unlink lifetime, cursor and full-table metadata passed')
