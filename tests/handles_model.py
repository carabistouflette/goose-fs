#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent OS oracle for retained handles, limits and concurrent stale tokens."""
import concurrent.futures
import ctypes as c
import errno
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import threading

class Slice(c.Structure):
    _fields_ = [('data', c.c_void_p), ('len', c.c_int64)]

lib = c.CDLL(os.environ.get('FS_HANDLES_LIBRARY', '.build/fs-handles.so'))
I = c.c_int64
for name, args in {
    'context_create': [], 'context_close': [I],
    'file_open': [I, Slice, I, I], 'file_close': [I, I], 'file_duplicate': [I, I],
    'file_read': [I, I, Slice, I, c.c_bool],
    'file_write': [I, I, Slice, I, c.c_bool, c.c_bool],
    'file_seek': [I, I, I, I], 'file_truncate': [I, I, I],
    'file_sync': [I, I, c.c_bool], 'file_metadata': [I, I],
}.items():
    fn = getattr(lib, 'gf_'+name); fn.restype = I; fn.argtypes = args + [Slice]

def invoke(name, *args, fields=3):
    meta = (I*fields)(*([165]*fields))
    code = getattr(lib, 'gf_'+name)(*args, Slice(c.addressof(meta), fields))
    return code, list(meta)

def context():
    code, meta = invoke('context_create'); assert code == 0 and meta[0] == 0
    return meta[1]

def close_context(ctx):
    code, meta = invoke('context_close', ctx); assert code == 0 and meta == [0,0,0]

def open_file(ctx, path, options=0, permissions=0o600):
    raw = os.fsencode(path); data = c.create_string_buffer(raw)
    return invoke('file_open', ctx, Slice(c.addressof(data),len(raw)), options, permissions)

def opened(ctx, path, options=0):
    code, meta = open_file(ctx,path,options); assert code == 0 and meta[0] == 0,(code,meta,path)
    return meta[1]

def read(ctx, file, count, offset=0, positioned=True):
    data = c.create_string_buffer(count+2); data[0] = b'!'; data[count+1] = b'!'
    code, meta = invoke('file_read',ctx,file,Slice(c.addressof(data)+1,count),offset,positioned)
    assert data[0] == data[count+1] == b'!'
    return code,meta,bytes(data)[1:1+meta[1]]

def write(ctx, file, data, offset=0, positioned=False, all=False):
    raw = c.create_string_buffer(data)
    return invoke('file_write',ctx,file,Slice(c.addressof(raw),len(data)),offset,positioned,all)

def ok(value):
    code, meta = value; assert code == 0 and meta[0] == 0,(code,meta)
    return meta

def descriptors():
    return len(os.listdir('/proc/self/fd'))

before = descriptors()
with tempfile.TemporaryDirectory(prefix='goose-fs-handles-') as temp:
    root = Path(temp); a=root/'a'; b=root/'b'
    a.write_bytes(b'abcdef'); b.write_bytes(b'BBBBBB')
    ctx=context(); file=opened(ctx,a,2)
    assert read(ctx,file,2,positioned=False) == (0,[0,2,0],b'ab')
    assert read(ctx,file,10,4) == (0,[0,2,0],b'ef')
    assert ok(invoke('file_seek',ctx,file,0,1))[1] == 2
    assert read(ctx,file,1,6) == (0,[0,0,1],b'')
    assert read(ctx,file,0,6) == (0,[0,0,0],b'')
    assert ok(write(ctx,file,b'Z',1,True))[1] == 1
    clone=ok(invoke('file_duplicate',ctx,file))[1]
    ok(invoke('file_close',ctx,file))
    assert read(ctx,file,6)[0:2] == (4,[errno.EBADF,0,0])
    assert read(ctx,clone,2,positioned=False) == (0,[0,2,0],b'cd')
    old=os.stat(a); a.rename(root/'moved'); (root/'moved').unlink()
    fields=ok(invoke('file_metadata',ctx,clone,fields=18))
    assert fields[1:6] == [1,6,old.st_mode & 0o7777,old.st_uid,old.st_gid]
    assert fields[6:9] == [old.st_dev,old.st_ino,0]
    ok(invoke('file_truncate',ctx,clone,3)); assert read(ctx,clone,5)[2] == b'aZc'
    # Sparse offsets exercise the 64-bit off_t path without allocating 4 GiB.
    offset=2**32+123
    assert ok(write(ctx,clone,b'x',offset,True))[1] == 1
    assert read(ctx,clone,2,offset-1)[2] == b'\0x'
    ok(invoke('file_truncate',ctx,clone,3))
    for data_only in [False,True]: ok(invoke('file_sync',ctx,clone,data_only))
    for off,count in [(-1,1),(2**63-1,1)]:
        assert read(ctx,clone,count,off)[0] == 1
        assert write(ctx,clone,b'x',off,True)[0] == 1
    assert invoke('file_truncate',ctx,clone,-1)[0] == 1
    assert invoke('file_seek',ctx,clone,0,3)[0] == 1
    # Private ABI overlap is rejected before either region is changed.
    guard=(I*3)(11,22,33)
    assert lib.gf_file_read(ctx,clone,Slice(c.addressof(guard),3),0,True,Slice(c.addressof(guard),3)) == 1
    assert list(guard) == [11,22,33]
    assert lib.gf_file_close(ctx,clone,Slice(None,3)) == 1
    other=context()
    assert read(other,clone,0)[0:2] == (4,[errno.EBADF,0,0])
    close_context(other)
    close_context(ctx)
    assert read(ctx,clone,0)[0:2] == (4,[errno.EBADF,0,0])
    a.write_bytes(b'abcdef')
    ctx=context(); file=opened(ctx,a,2|16)
    assert write(ctx,file,b'x',0,True)[0:2] == (4,[errno.EINVAL,0,0])
    assert ok(write(ctx,file,b'!',all=True))[1] == 1 and a.read_bytes() == b'abcdef!'
    assert ok(write(ctx,file,b'',all=True)) == [0,0,0]
    ro=opened(ctx,a)
    assert write(ctx,ro,b'')[0:2] == (4,[errno.EBADF,0,0])
    wo=opened(ctx,a,1)
    assert read(ctx,wo,0)[0:2] == (4,[errno.EBADF,0,0])
    for options in [3,12,32,16,64,-1]:
        assert open_file(ctx,a,options)[0] == 1
        assert a.read_bytes() == b'abcdef!'
    assert open_file(ctx,a,2,0o1000)[0] == 1
    (root/'link').symlink_to('a'); (root/'parent').symlink_to(root,target_is_directory=True)
    os.mkfifo(root/'fifo')
    assert open_file(ctx,root/'link')[0] == 4
    assert open_file(ctx,root/'parent/a')[0] == 4
    assert open_file(ctx,root/'fifo')[0] == 3
    assert open_file(ctx,root)[0] == 3
    created=root/'created'
    old_umask=os.umask(0o027)
    try:
        create=ok(open_file(ctx,created,2|4,0o666))[1]
        assert os.stat(created).st_mode & 0o777 == 0o640
    finally: os.umask(old_umask)
    assert open_file(ctx,created,2|4)[0] == 4
    ok(invoke('file_close',ctx,create)); close_context(ctx)
    # Concurrent positioned reads/duplicates; ctypes releases the GIL in CDLL calls.
    ctx=context(); file=opened(ctx,a)
    def reader(_):
        for _ in range(300):
            assert read(ctx,file,7) == (0,[0,7,0],b'abcdef!')
            copy=ok(invoke('file_duplicate',ctx,file))[1]
            assert read(ctx,copy,2,2)[2] == b'cd'
            ok(invoke('file_close',ctx,copy))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(reader,range(4)))
    close_context(ctx)
    # Race stale snapshots against close/reuse: success must never read a reused slot's file.
    ctx=context(); state_lock=threading.Lock(); current=[opened(ctx,a),b'abcdef!']
    def churn():
        for i in range(600):
            with state_lock: old=current[0]
            ok(invoke('file_close',ctx,old))
            path,expected=(a,b'abcdef!') if i%2 else (b,b'BBBBBB')
            new=opened(ctx,path)
            with state_lock: current[:]=[new,expected]
    def stale_reader(_):
        for _ in range(1800):
            with state_lock: token,expected=current
            code,meta,data=read(ctx,token,16)
            assert (code == 0 and data == expected) or (code == 4 and meta == [errno.EBADF,0,0]),(code,meta,data,expected)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        tasks=[pool.submit(churn),*(pool.submit(stale_reader,i) for i in range(3))]
        for future in tasks: future.result()
    close_context(ctx)
    # Fixed process-wide caps reject before creation/truncation and recover on cleanup.
    contexts=[context() for _ in range(64)]
    assert invoke('context_create') == (2,[0,0,0])
    for ctx in contexts: close_context(ctx)
    soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
    assert hard == resource.RLIM_INFINITY or hard >= 5000,'need hard fd limit >=5000 to exercise 4096-slot cap'
    resource.setrlimit(resource.RLIMIT_NOFILE,(max(soft,5000),hard))
    c1=context(); c2=context(); handles=[]
    for i in range(4096): handles.append(opened(c1 if i%2 else c2,a))
    assert open_file(c1,root/'must-not-exist',2|4) == (2,[0,0,0])
    assert not (root/'must-not-exist').exists()
    assert open_file(c2,a,2|32) == (2,[0,0,0]) and a.read_bytes() == b'abcdef!'
    assert invoke('file_duplicate',c2,handles[0]) == (2,[0,0,0])
    close_context(c1)
    assert read(c2,handles[0],7)[2] == b'abcdef!'
    new=opened(c2,a,2); ok(invoke('file_close',c2,new)); close_context(c2)
    resource.setrlimit(resource.RLIMIT_NOFILE,(soft,hard))
    # Real kernel EMFILE is a SystemError and a failed reservation is reusable.
    ctx=context(); occupied=[]
    fd_limit=max(32,descriptors()+2)
    if hard != resource.RLIM_INFINITY: fd_limit=min(fd_limit,hard)
    resource.setrlimit(resource.RLIMIT_NOFILE,(fd_limit,hard))
    try:
        # Existing descriptors can have holes or lie above the new soft limit.
        # Fill actual low slots, then free precisely one for the parent lookup.
        while True:
            try: occupied.append(os.open('/dev/null',os.O_RDONLY|os.O_CLOEXEC))
            except OSError as error:
                assert error.errno == errno.EMFILE,error
                break
        assert occupied,'need one descriptor to release for the parent lookup'
        os.close(occupied.pop())
        actual=open_file(ctx,a)
        assert actual == (4,[errno.EMFILE,0,0]),actual
    finally:
        for fd in occupied: os.close(fd)
        resource.setrlimit(resource.RLIMIT_NOFILE,(soft,hard))
    file=opened(ctx,a)
    # exec must not inherit a retained descriptor, independently of descriptor numbers.
    child='''import os,sys
wanted=tuple(map(int,sys.argv[1:])); found=False
for name in os.listdir('/proc/self/fd'):
 try:
  s=os.fstat(int(name)); found |= (s.st_dev,s.st_ino)==wanted
 except OSError: pass
assert not found
'''
    st=os.stat(a)
    subprocess.run([sys.executable,'-c',child,str(st.st_dev),str(st.st_ino)],close_fds=False,check=True)
    close_context(ctx)
assert descriptors() == before,(descriptors(),before)
print('retained-handle OS oracle, concurrency, caps, descriptor exhaustion and exec tests passed')
