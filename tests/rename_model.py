#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare rename policies to Linux, then check links, races and outcome bounds."""
import concurrent.futures
import ctypes as c
import errno
import os
from pathlib import Path
import stat
import tempfile
import threading

class Slice(c.Structure):
    _fields_=[('data',c.c_void_p),('len',c.c_int64)]
I=c.c_int64
lib=c.CDLL(os.environ.get('FS_HANDLES_LIBRARY','.build/fs-handles.so'))
for name,args in {'context_create':[], 'context_close':[I], 'root_open':[I,Slice], 'root_close':[I,I],
                  'rename':[Slice,Slice,I], 'root_rename':[I,I,Slice,Slice,I], 'root_read':[I,I,Slice,Slice]}.items():
    f=getattr(lib,'gf_'+name);f.restype=I;f.argtypes=args+[Slice]
libc=c.CDLL(None,use_errno=True)
libc.renameat2.argtypes=[c.c_int,c.c_char_p,c.c_int,c.c_char_p,c.c_uint];libc.renameat2.restype=c.c_int

def raw(value):
    data=os.fsencode(value);buf=c.create_string_buffer(data);return buf,Slice(c.addressof(buf),len(data))
def call(name,*args,fields=4):
    m=(I*fields)(*([165]*fields));code=getattr(lib,'gf_'+name)(*args,Slice(c.addressof(m),fields));return code,list(m)
def ok(value):
    code,m=value;assert code==0 and m[0]==0,(code,m);return m

def setup(base,source,dest):
    base.mkdir();(base/'victim').write_bytes(b'untouched')
    for name,kind in [('source',source),('target',dest)]:
        path=base/name
        if kind=='file':path.write_bytes(name.encode())
        elif kind in ('empty-dir','full-dir'):
            path.mkdir()
            if kind=='full-dir':(path/'inside').write_bytes(name.encode())
        elif kind=='link':path.symlink_to('victim')
        elif kind=='dangling':path.symlink_to('absent')
        elif kind=='fifo':os.mkfifo(path)
        else:assert kind=='absent'

def snapshot(path):
    result={}
    for child in sorted(path.iterdir()):
        mode=child.lstat().st_mode
        if stat.S_ISLNK(mode):value=('link',os.readlink(child))
        elif stat.S_ISDIR(mode):value=('dir',snapshot(child))
        elif stat.S_ISREG(mode):value=('file',child.read_bytes())
        else:assert stat.S_ISFIFO(mode);value=('fifo',)
        result[child.name]=value
    return result

def reference(source,target,no_replace):
    if no_replace:
        c.set_errno(0);rc=libc.renameat2(-100,os.fsencode(source),-100,os.fsencode(target),1)
        return c.get_errno() if rc else 0
    try:os.rename(source,target);return 0
    except OSError as e:return e.errno

before=len(os.listdir('/proc/self/fd'));cases=0
with tempfile.TemporaryDirectory(prefix='goose-fs-rename-') as temp:
    base=Path(temp);ctx=ok(call('context_create',fields=3))[1]
    anchor=base/'anchor';anchor.mkdir();pb,ps=raw(anchor);root=ok(call('root_open',ctx,ps,fields=3))[1]
    def rename(source,target,flags,rooted=True,token=root):
        a,sa=raw(source if rooted else anchor/source);b,sb=raw(target if rooted else anchor/target)
        return call('root_rename',ctx,token,sa,sb,flags) if rooted else call('rename',sa,sb,flags)
    for rooted in [False,True]:
        for source in ['file','empty-dir','full-dir','link','dangling','fifo']:
            for dest in ['absent','file','empty-dir','full-dir','link','dangling','fifo']:
                for flags in range(4):
                    name=f'case-{cases}';actual=anchor/name;expected=base/f'ref-{cases}'
                    setup(actual,source,dest);setup(expected,source,dest)
                    error=reference(expected/'source',expected/'target',flags&1)
                    code,m=rename(f'{name}/source',f'{name}/target',flags,rooted)
                    assert (code,m)==((4,[error,2,0,0]) if error else (0,[0,1,int(bool(flags&2)),0])),(rooted,source,dest,flags,code,m,error)
                    assert snapshot(actual)==snapshot(expected),(rooted,source,dest,flags)
                    cases+=1
        for flags in range(4):
            folder=anchor/f'links-{rooted}-{flags}';folder.mkdir();a=folder/'a';b=folder/'b';a.write_bytes(b'same');os.link(a,b)
            prefix=folder.name
            expected=(4,[errno.EEXIST,2,0,0]) if flags&1 else (0,[0,1,int(bool(flags&2)),0])
            assert rename(f'{prefix}/a',f'{prefix}/b',flags,rooted)==expected
            assert a.exists() and b.exists() and a.stat().st_ino==b.stat().st_ino
            assert rename(f'{prefix}/a',f'{prefix}/a',flags,rooted)==expected
            assert a.read_bytes()==b'same'
    # The same ENOENT has different outcomes before/after the rename attempt.
    for rooted in [False,True]:
        for flags in range(4):
            assert rename('missing','unused',flags,rooted)==(4,[errno.ENOENT,2,0,0])
            assert rename('missing-parent/source','unused',flags,rooted)==(4,[errno.ENOENT,0,0,0])
    # Both path operands preserve arbitrary non-NUL filename bytes.
    for rooted in [False,True]:
        source=b'byte-\xff\n';target=b'byte-\xfe\r'
        fd=os.open(os.fsencode(anchor)+b'/'+source,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,b'bytes');os.close(fd)
        a,sa=raw(source if rooted else os.fsencode(anchor)+b'/'+source)
        b,sb=raw(target if rooted else os.fsencode(anchor)+b'/'+target)
        value=call('root_rename',ctx,root,sa,sb,3) if rooted else call('rename',sa,sb,3)
        assert value==(0,[0,1,1,0])
        fd=os.open(os.fsencode(anchor)+b'/'+target,os.O_RDONLY)
        try:assert os.read(fd,6)==b'bytes'
        finally:os.close(fd)
        os.unlink(os.fsencode(anchor)+b'/'+target)
    # Ancestor links never allow a namespace operation, for either operand.
    outside=base/'outside';outside.mkdir();(outside/'victim').write_bytes(b'outside');(anchor/'parent-link').symlink_to(outside,target_is_directory=True)
    (anchor/'good').write_bytes(b'good')
    for rooted in [False,True]:
        for source,target in [('parent-link/victim','unused'),('good','parent-link/victim')]:
            code,m=rename(source,target,0,rooted)
            assert code==4 and m[0] and m[1:]==[0,0,0]
            assert (outside/'victim').read_bytes()==b'outside' and (anchor/'good').read_bytes()==b'good'
    # No-sync requires write/search permission, not directory read permission.
    if os.geteuid()!=0:
        restricted=anchor/'restricted';restricted.mkdir();(restricted/'source').write_bytes(b'permission')
        restricted.chmod(0o300)
        try:
            for rooted in [False,True]:
                assert rename('restricted/source','restricted/target',0,rooted)==(0,[0,1,0,0])
                assert rename('restricted/target','restricted/source',2,rooted)==(4,[errno.EACCES,0,0,0])
                assert rename('restricted/target','restricted/source',0,rooted)==(0,[0,1,0,0])
        finally:restricted.chmod(0o700)
    # Swapping a parent between a directory and an outside symlink cannot route
    # either operand into the outside directory. Held inside fds avoid following
    # the adversarial name while preparing/inspecting our own fixture.
    for operand in ['source','target']:
        moving=anchor/f'switch-{operand}';saved=anchor/f'saved-{operand}';moving.mkdir()
        inner=os.open(moving,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        for name in ['source','target']:(outside/name).write_bytes(b'protected')
        finished=threading.Event();started=threading.Event();thread_errors=[]
        def swap_parent():
            started.set()
            try:
                while not finished.is_set():
                    os.rename(moving,saved);moving.symlink_to(outside,target_is_directory=True)
                    moving.unlink();os.rename(saved,moving)
            except BaseException as error:
                thread_errors.append(error);finished.set()
        thread=threading.Thread(target=swap_parent);thread.start();started.wait()
        try:
            for _ in range(1000):
                if operand=='source':
                    try:
                        fd=os.open('source',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC,0o600,dir_fd=inner)
                    except FileExistsError:pass
                    else:os.write(fd,b'safe');os.close(fd)
                    value=rename(f'{moving.name}/source','race-result',0)
                else:
                    (anchor/'race-stage').write_bytes(b'safe')
                    value=rename('race-stage',f'{moving.name}/target',0)
                code,m=value
                if code:
                    assert code==4 and m[0] and m[1] in (0,2) and m[2:]==[0,0],value
                else:
                    assert m==[0,1,0,0]
                    if operand=='source':assert (anchor/'race-result').read_bytes()==b'safe'
                    else:
                        fd=os.open('target',os.O_RDONLY|os.O_CLOEXEC,dir_fd=inner)
                        try:assert os.read(fd,8)==b'safe'
                        finally:os.close(fd)
        finally:finished.set();thread.join(timeout=10);assert not thread.is_alive();os.close(inner)
        assert not thread_errors,thread_errors
        assert (outside/'source').read_bytes()==b'protected' and (outside/'target').read_bytes()==b'protected'
    # Exactly one concurrent NoReplace can install a name.
    for i in range(8):(anchor/f'contender-{i}').write_bytes(str(i).encode())
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda i:rename(f'contender-{i}','winner',3),range(8)))
    assert sum(code==0 for code,m in results)==1
    for code,m in results:assert (code,m) in [(0,[0,1,1,0]),(4,[errno.EEXIST,2,0,0])]
    winner=int((anchor/'winner').read_bytes());assert not (anchor/f'contender-{winner}').exists()
    assert all((anchor/f'contender-{i}').exists() for i in range(8) if i!=winner)
    # Readers of replacement see complete immutable inodes, never a missing target.
    payloads=[b'A'*8192,b'B'*8192];(anchor/'published').write_bytes(payloads[0]);barrier=threading.Barrier(2);stop=threading.Event()
    def writer():
        barrier.wait()
        try:
            for i in range(1000):
                (anchor/'next').write_bytes(payloads[i%2]);assert rename('next','published',0)==(0,[0,1,0,0])
        finally:stop.set()
    def reader():
        buf=c.create_string_buffer(8192);pb,ps=raw('published');count=0;barrier.wait()
        while not stop.is_set():
            assert call('root_read',ctx,root,ps,Slice(c.addressof(buf),8192),fields=3)==(0,[0,8192,0])
            assert bytes(buf) in payloads;count+=1
        return count
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        read=pool.submit(reader);write=pool.submit(writer);write.result(timeout=30);assert read.result(timeout=30)>0
    # A cross-filesystem error is surfaced as an uncertain attempt; no copying.
    if os.path.isdir('/dev/shm') and os.access('/dev/shm',os.W_OK):
        with tempfile.TemporaryDirectory(dir='/dev/shm',prefix='goose-fs-rename-') as other:
            if os.stat(other).st_dev!=anchor.stat().st_dev:
                (anchor/'cross').write_bytes(b'cross');a,sa=raw(anchor/'cross');b,sb=raw(Path(other)/'target')
                assert call('rename',sa,sb,0)==(4,[errno.EXDEV,2,0,0]);assert (anchor/'cross').read_bytes()==b'cross' and not (Path(other)/'target').exists()
    for flags in [-1,4,999]:
        a,sa=raw('good');b,sb=raw('unused');assert call('root_rename',ctx,root,sa,sb,flags)==(1,[0,0,0,0])
    assert call('root_close',ctx,root,fields=3)==(0,[0,0,0]);assert rename('good','unused',0)==(4,[errno.EBADF,0,0,0])
    assert call('context_close',ctx,fields=3)==(0,[0,0,0])
assert len(os.listdir('/proc/self/fd'))==before
print(f'{cases} Linux rename oracle cases, link/no-op policies, 2000 parent-swap probes, concurrent publication, uncertain EXDEV and descriptor cleanup passed')
