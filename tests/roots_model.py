#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent rooted filesystem oracle, mixed kinds/caps and long traversal."""
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
    _fields_=[('data',c.c_void_p),('len',c.c_int64)]
I=c.c_int64
lib=c.CDLL(os.environ.get('FS_HANDLES_LIBRARY','.build/fs-handles.so'))
for name,args in {
    'context_create':[],'context_close':[I], 'root_open':[I,Slice],
    'root_open_at':[I,I,Slice], 'file_open':[I,Slice,I,I], 'file_open_at':[I,I,Slice,I,I],
    'root_close':[I,I], 'file_close':[I,I], 'file_duplicate':[I,I],
    'root_metadata':[I,I], 'file_metadata':[I,I], 'root_metadata_at':[I,I,Slice],
    'root_read':[I,I,Slice,Slice], 'root_list':[I,I,Slice,Slice,I],
    'root_create':[I,I,Slice,Slice], 'root_mkdir':[I,I,Slice], 'root_unlink':[I,I,Slice,c.c_bool],
    'file_read':[I,I,Slice,I,c.c_bool], 'file_write':[I,I,Slice,I,c.c_bool,c.c_bool],
    'file_seek':[I,I,I,I], 'file_sync':[I,I,c.c_bool], 'file_truncate':[I,I,I],
    'file_try_lock':[I,I,I],
}.items():
    fn=getattr(lib,'gf_'+name);fn.restype=I;fn.argtypes=args+[Slice]
def raw(data):
    data=os.fsencode(data);buf=c.create_string_buffer(data)
    return buf,Slice(c.addressof(buf),len(data))
def call(name,*args,fields=3):
    out=(I*fields)(*([165]*fields));code=getattr(lib,'gf_'+name)(*args,Slice(c.addressof(out),fields))
    fields_out=list(out)
    if fields==18:
        for index in [2,6,7,8]:fields_out[index]&=(1<<64)-1
    return code,fields_out
def path_call(name,ctx,token,path,*args,fields=3):
    buf,value=raw(path)
    return call(name,ctx,token,value,*args,fields=fields)
def ok(value):
    code,out=value;assert code==0 and out[0]==0,(code,out)
    return out

def open_root(ctx,path):
    buf,value=raw(path);return ok(call('root_open',ctx,value))[1]
def read(ctx,root,path,limit=64):
    buf=c.create_string_buffer(limit+2);buf[0]=b'!';buf[limit+1]=b'!'
    code,out=path_call('root_read',ctx,root,path,Slice(c.addressof(buf)+1,limit))
    assert buf[0]==buf[limit+1]==b'!'
    return code,out,bytes(buf)[1:1+out[1]]
def listing(ctx,root,path,limit=65536,count=4096):
    buf=c.create_string_buffer(limit+2);buf[0]=b'!';buf[limit+1]=b'!'
    code,out=path_call('root_list',ctx,root,path,Slice(c.addressof(buf)+1,limit),count)
    assert buf[0]==buf[limit+1]==b'!'
    entries=[];packed=bytes(buf)[1:1+out[1]];position=0
    if not code:
        for _ in range(out[2]):
            kind=packed[position];assert 0<=kind<=4;position+=1
            end=packed.index(0,position);entries.append(packed[position:end]);position=end+1
        assert position==len(packed)
    return code,out,entries

def create(ctx,root,path,data):
    buf,value=raw(data);return path_call('root_create',ctx,root,path,value)
def f_read(ctx,file):
    buf=c.create_string_buffer(16)
    code,out=call('file_read',ctx,file,Slice(c.addressof(buf),16),0,True)
    return code,out,bytes(buf)[:out[1]]
def fd_count():return len(os.listdir('/proc/self/fd'))
before=fd_count()
with tempfile.TemporaryDirectory(prefix='goose-fs-roots-') as temp:
    base=Path(temp);anchor=base/'anchor';anchor.mkdir();(anchor/'file').write_bytes(b'good')
    (anchor/'nested').mkdir();(anchor/'nested/inside').write_bytes(b'nested')
    for name in [b'line\nbreak',b'\xff\xfe',b'x'*255]:
        fd=os.open(os.fsencode(anchor)+b'/'+name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.write(fd,b'bytes');os.close(fd)
    (anchor/'link').symlink_to('file');(anchor/'dangling').symlink_to('absent')
    (anchor/'parent-link').symlink_to('nested',target_is_directory=True)
    ctx=ok(call('context_create'))[1];root=open_root(ctx,anchor)
    assert read(ctx,root,'file')==(0,[0,4,0],b'good')
    assert read(ctx,root,'nested/inside')==(0,[0,6,0],b'nested')
    assert read(ctx,root,'.')[0:2]==(3,[0,0,0])
    info=ok(call('root_metadata',ctx,root,fields=18));expected=os.stat(anchor)
    assert info[1]==2 and info[6:9]==[expected.st_dev,expected.st_ino,expected.st_nlink]
    for path in ['link','dangling','parent-link']:
        assert ok(path_call('root_metadata_at',ctx,root,path,fields=18))[1]==3
        assert read(ctx,root,path)[0]==4
    assert read(ctx,root,'parent-link/inside')[0]==4
    for _ in range(2):assert sorted(listing(ctx,root,'.')[2])==sorted(os.listdir(os.fsencode(anchor)))
    assert listing(ctx,root,'.',0,0)[0:2]==(2,[0,0,0])
    for path in ['', '/', '/file', '..','../file','nested/../file','nested/.','./file','nested//inside','file/','a\0b']:
        assert read(ctx,root,path)[0:2]==(1,[0,0,0]),path
        code,fields=path_call('root_metadata_at',ctx,root,path,fields=18);assert code==1 and fields==[0]*18
        assert path_call('root_open_at',ctx,root,path)==(1,[0,0,0])
    bad_buf,bad_data=raw(b'bad')
    for name,args in [('root_create',(bad_data,)),('root_mkdir',()),('root_unlink',(False,)),('root_unlink',(True,))]:
        assert path_call(name,ctx,root,'.',*args)==(1,[0,0,0])
    assert path_call('file_open_at',ctx,root,'.',2,0o600)==(1,[0,0,0])
    assert path_call('file_open_at',ctx,root,'.',0,0o600)==(3,[0,0,0])
    buf,value=raw(b'data');small=c.create_string_buffer(8)
    # Every File operation rejects a Root token before changing its lifetime or state.
    file_ops=[('file_close',()),('file_duplicate',()),('file_metadata',()),
              ('file_read',(Slice(c.addressof(small),8),0,True)),
              ('file_write',(value,0,False,True)),('file_seek',(0,0)),
              ('file_truncate',(0,)),('file_sync',(False,)),('file_try_lock',(2,))]
    for name,args in file_ops:
        code,out=call(name,ctx,root,*args,fields=18 if name=='file_metadata' else 3)
        assert code==4 and out[0]==errno.EBADF and out[1:]==[0]*(len(out)-1),(name,code,out)
    ok(call('root_metadata',ctx,root,fields=18))
    file=ok(path_call('file_open_at',ctx,root,'file',2,0o600))[1]
    for name in ['root_close','root_metadata']:
        code,out=call(name,ctx,file,fields=18 if name=='root_metadata' else 3)
        assert code==4 and out[0]==errno.EBADF
    assert read(ctx,file,'.')[0:2]==(4,[errno.EBADF,0,0])
    assert path_call('root_open_at',ctx,file,'.')==(4,[errno.EBADF,0,0])
    assert f_read(ctx,file)[2]==b'good'
    # Root identity survives rename and replacement of its original absolute name.
    moved=base/'moved';anchor.rename(moved);anchor.mkdir();(anchor/'file').write_bytes(b'wrong')
    assert read(ctx,root,'file')[2]==b'good'
    same=ok(path_call('root_open_at',ctx,root,'.'))[1]
    child=ok(path_call('root_open_at',ctx,root,'nested'))[1]
    ok(call('root_close',ctx,root))
    assert read(ctx,same,'file')[2]==b'good' and read(ctx,child,'inside')[2]==b'nested'
    assert read(ctx,root,'file')[0:2]==(4,[errno.EBADF,0,0])
    ok(call('root_close',ctx,same));ok(call('root_close',ctx,child));assert f_read(ctx,file)[2]==b'good'
    ok(call('file_close',ctx,file))
    # Chained capabilities support cumulative paths beyond absolute PATH_MAX.
    root=open_root(ctx,moved);deep=root;cumulative=len(os.fsencode(moved))
    for i in range(20):
        name='d'*230+str(i);ok(path_call('root_mkdir',ctx,deep,name))
        nxt=ok(path_call('root_open_at',ctx,deep,name))[1]
        if deep!=root:ok(call('root_close',ctx,deep))
        deep=nxt;cumulative+=len(name)+1
    assert cumulative>4095
    ok(create(ctx,deep,'leaf',b'deep'));assert read(ctx,deep,'leaf')[2]==b'deep'
    ok(call('root_close',ctx,deep))
    # Parallel independent listings must never share a directory cursor.
    def query(_):
        for _ in range(100):
            assert sorted(listing(ctx,root,'.')[2])==sorted(os.listdir(os.fsencode(moved)))
            assert read(ctx,root,'file')[2]==b'good'
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(query,range(4)))
    # Replace an ancestor directory with an outside symlink between lookup steps.
    race=moved/'race';stash=moved/'stash';outside=base/'outside';outside.mkdir()
    race.mkdir();(race/'leaf').write_bytes(b'safe');(outside/'leaf').write_bytes(b'evil')
    safe=os.stat(race/'leaf');stop=threading.Event();failures=[]
    def swap():
        try:
            while not stop.is_set():
                race.rename(stash);race.symlink_to(outside,target_is_directory=True)
                race.unlink();stash.rename(race)
        except BaseException as error:failures.append(error)
    background=threading.Thread(target=swap);background.start()
    try:
        for i in range(20000):
            code,out,data=read(ctx,root,'race/leaf',4)
            assert (code==0 and data==b'safe') or (code==4 and out[0]!=0 and out[1:]==[0,0]),(code,out,data)
            if i%10==0:
                code,fields=path_call('root_metadata_at',ctx,root,'race/leaf',fields=18)
                assert (code==0 and fields[6:8]==[safe.st_dev,safe.st_ino]) or (code==4 and fields[0]!=0),(code,fields)
    finally:stop.set();background.join()
    assert not failures,failures
    child_script='''import os,sys
expected=tuple(map(int,sys.argv[1:]))
for name in os.listdir('/proc/self/fd'):
 try: s=os.fstat(int(name))
 except OSError: continue
 assert (s.st_dev,s.st_ino)!=expected
'''
    expected=os.stat(moved)
    subprocess.run([sys.executable,'-c',child_script,str(expected.st_dev),str(expected.st_ino)],close_fds=False,check=True)
    ok(call('context_close',ctx))
    assert read(ctx,root,'file')[0:2]==(4,[errno.EBADF,0,0])
    # Mixed cap: Root+4095 Files share the4096 slots, reserved before mutations.
    soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
    assert hard==resource.RLIM_INFINITY or hard>=5000
    resource.setrlimit(resource.RLIMIT_NOFILE,(max(soft,5000),hard))
    try:
        ctx=ok(call('context_create'))[1];root=open_root(ctx,anchor)
        for _ in range(4095):ok(path_call('file_open_at',ctx,root,'file',0,0o600))
        assert path_call('file_open_at',ctx,root,'absent',2|4,0o600)==(2,[0,0,0])
        assert not (anchor/'absent').exists()
        assert path_call('file_open_at',ctx,root,'file',2|32,0o600)==(2,[0,0,0]) and (anchor/'file').read_bytes()==b'wrong'
        assert path_call('root_open_at',ctx,root,'.')==(2,[0,0,0])
        ok(create(ctx,root,'one-shot',b'works'));assert read(ctx,root,'one-shot')[2]==b'works'
        ok(path_call('root_unlink',ctx,root,'one-shot',False))
        ok(call('context_close',ctx))
    finally:resource.setrlimit(resource.RLIMIT_NOFILE,(soft,hard))
assert fd_count()==before,(fd_count(),before)
print('Root OS oracle, mixed-kind/cap guards, renamed identity, parallel cursors and >PATH_MAX traversal passed')
