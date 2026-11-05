#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Common byte-level fixtures and actual-entrypoint conformance/fault checks."""
import errno
import ctypes
import json
import os
from pathlib import Path
import random
import subprocess

PRIMARY = ('empty', 'tiny', 'page', 'chunk', 'max', 'large-budget')
FAULTS = ('short', 'eintr', 'read_eio', 'stat_eio', 'stat_small', 'stat_large',
          'fallback38', 'fallback1', 'walk_close', 'walk_open_close',
          'file_close_eio', 'file_close_eintr', 'read_close_eio', 'read_close_eintr',
          'limit_close_eio', 'limit_close_eintr', 'parent_close', 'reuse_file')

def pattern(n):
    return bytes((i * 17 + 13) % 251 for i in range(n))

def ancestor_symlink_errno():
    # Detect the actual kernel entry-point availability, not a copied resolver.
    libc=ctypes.CDLL(None,use_errno=True)
    how=(ctypes.c_uint64*3)(0x200000|0x10000|0x80000,0,4)
    fd=libc.syscall(ctypes.c_long(437),ctypes.c_int(-100),ctypes.c_char_p(b'/'),ctypes.byref(how),ctypes.c_size_t(24))
    if fd>=0:
        os.close(fd); return errno.ELOOP
    error=ctypes.get_errno()
    assert error in (errno.ENOSYS,errno.EPERM), error
    return errno.ENOTDIR

def fixtures(root):
    root.mkdir(parents=True, exist_ok=False)
    sizes = [0, 64, 4096, 65536, 1048576]
    random.Random(62501).shuffle(sizes)
    for n in sizes:
        (root / f'read-{n}').write_bytes(pattern(n))
    (root/'directory').mkdir()
    (root/'link').symlink_to('read-64')
    (root/'parent-link').symlink_to('directory', target_is_directory=True)
    os.mkfifo(root/'fifo')
    deep = root
    for i in range(12):
        deep /= f'level-{i:02d}'
        deep.mkdir()
    (deep/'file').write_bytes(pattern(64))
    raw = os.fsencode(root) + b'/raw-\xff'
    fd = os.open(raw, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    try:
        assert os.write(fd, pattern(64)) == 64
    finally:
        os.close(fd)
    cases = []
    for name,n in zip(PRIMARY,[0,64,4096,65536,1048576]):
        cases.append(dict(name=name,path=os.fsencode(root/f'read-{n}'),limit=n,code=0,error=0,data=pattern(n)))
    cases += [dict(name='large-budget',path=os.fsencode(root/'read-64'),limit=1048576,code=0,error=0,data=pattern(64)),
              dict(name='missing',path=os.fsencode(root/'missing'),limit=64,code=4,error=errno.ENOENT,data=b''),
              dict(name='overflow',path=os.fsencode(root/'read-64'),limit=32,code=2,error=0,data=b''),
              dict(name='zero-overflow',path=os.fsencode(root/'read-64'),limit=0,code=2,error=0,data=b''),
              dict(name='nonregular',path=os.fsencode(root/'directory'),limit=64,code=3,error=0,data=b''),
              dict(name='deep',path=os.fsencode(deep/'file'),limit=64,code=0,error=0,data=pattern(64))]
    extra = [dict(name='raw-name',path=raw,limit=64,code=0,error=0,data=pattern(64)),
             dict(name='root',path=b'/',limit=64,code=3,error=0,data=b''),
             dict(name='fifo',path=os.fsencode(root/'fifo'),limit=64,code=3,error=0,data=b''),
             dict(name='device',path=b'/dev/null',limit=64,code=3,error=0,data=b''),
             dict(name='leaf-link',path=os.fsencode(root/'link'),limit=64,code=4,error=errno.ELOOP,data=b''),
             dict(name='parent-link',path=os.fsencode(root/'parent-link'/'absent'),limit=64,code=4,error=ancestor_symlink_errno(),data=b'')]
    for n in (4,8,1023,1024,1025,2047,2048,2049):
        path=root/f'boundary-{n}';path.write_bytes(pattern(n))
        extra.append(dict(name=f'boundary-{n}',path=os.fsencode(path),limit=n,code=0,error=0,data=pattern(n)))
        if 1023<=n<=1025:
            extra.append(dict(name=f'boundary-loose-{n}',path=os.fsencode(path),limit=1048576,code=0,error=0,data=pattern(n)))
    invalid = [b'',b'local',b'//',b'/.',b'/..',b'/x/',b'/x//y',b'/x/./y',b'/x/../y',b'/x\0tail',b'/' + b'x'*4095]
    extra += [dict(name=f'invalid-{i}',path=p,limit=64,code=1,error=0,data=b'') for i,p in enumerate(invalid)]
    extra += [dict(name=f'limit-{n}',path=os.fsencode(root/'read-64'),limit=n,code=1,error=0,data=b'') for n in (-1,1048577)]
    # Longest accepted path, with actual <=255-byte components on disk.
    long = root
    while len(os.fsencode(long)) + 202 < 4095:
        long /= 'a'*200
        long.mkdir()
    remainder = 4095 - len(os.fsencode(long)) - 1
    leaf = long / ('z'*remainder)
    leaf.write_bytes(pattern(64))
    assert len(os.fsencode(leaf)) == 4095
    extra.append(dict(name='max-path',path=os.fsencode(leaf),limit=64,code=0,error=0,data=pattern(64)))
    return cases,extra

def probe(binary,case,loops=1,fault=None,growth_old=None):
    env = dict(os.environ)
    env.pop('READ_CONTRACT_FAULT',None)
    if fault:
        env['READ_CONTRACT_FAULT']=fault
    p = subprocess.run([str(binary),('empty-probe' if case.get('mode')=='fresh' else 'probe') if growth_old is None else 'growth',case['path'].hex(),str(case['limit']),str(loops if growth_old is None else growth_old)],
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=30)
    if p.returncode:
        raise AssertionError((str(binary),case['name'],fault,p.returncode,p.stderr.decode(errors='replace')))
    head,data = p.stdout.split(b'\n',1)
    code,error,length,before,after = map(int,head.split(b'\t'))
    assert (code,error,length,data)==(case['code'],case['error'],len(case['data']),case['data']), (binary,case['name'],fault,(code,error,length),head)
    assert before==after, ('FD leak',binary,case['name'],fault,before,after)
    counters=json.loads(p.stderr) if fault else None
    if not fault:
        assert not p.stderr, p.stderr
    return counters

def add_fresh_case(cases):
    cases.append(dict(next(c for c in cases if c['name']=='max'),name='fresh-max',mode='fresh',count=100))

def fresh_smoke(binary,c):
    env=dict(os.environ);env.pop('READ_CONTRACT_FAULT',None)
    p=subprocess.run([str(binary),'fresh',os.fsdecode(c['path']),str(c['limit']),str(c['code']),'1'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    assert p.returncode==0 and not p.stderr, (binary,p.returncode,p.stderr)
    rows=[list(map(int,line.split(b'\t'))) for line in p.stdout.splitlines()]
    value=len(c['data'])+(c['data'][0]+c['data'][-1] if c['data'] else 0)+c['code']+1
    assert len(rows)==7 and all(len(r)==3 and r[0]==i and r[1]>0 and r[2]==value for i,r in enumerate(rows)), (binary,rows)

def check_release(binaries,cases,extra):
    count=0
    for binary in binaries:
        for c in cases+extra:
            probe(binary,c); count+=1
            if c.get('mode')=='fresh':fresh_smoke(binary,c);count+=1
        for name in ('tiny','missing','nonregular','overflow'):
            probe(binary,next(c for c in cases if c['name']==name),loops=1000); count+=1
    return count

def check_faults(binaries,cases):
    count=0
    tiny=next(c for c in cases if c['name']=='tiny')
    for binary in binaries:
        growth=dict(tiny,name='dirty-retained-growth',limit=1048576)
        for old in (0,7,63,65,128,1023,1024,1025,1047551,1047552,1047553,1048576):
            s=probe(binary,growth,fault=f'growth-{old}',growth_old=old)
            assert s.get('growth_checked')==1 and s.get('injected')==1 and s.get('reads')==2, (binary,old,s)
            count+=1
        for c in cases:
            s=probe(binary,c,fault='observe')
            assert s.get('open2')==1 and not s.get('injected'), (binary,c['name'],s)
            assert s.get('read_bytes',0)<=c['limit']+1, (binary,c['name'],s)
            assert s.get('file_closes',0)==(c['name']!='missing'), (binary,c['name'],s)
            if c['code']==0 or c['code']==2:
                expected=len(c['data']) if c['code']==0 else c['limit']+1
                assert s.get('read_bytes',0)==expected and s.get('stats')==1, (binary,c['name'],s)
            count+=1
        for mode in ('fallback38','fallback1'):
            c=dict(name='fallback-parent-link',path=tiny['path'].rsplit(b'/',1)[0]+b'/parent-link/absent',limit=64,code=4,error=errno.ENOTDIR,data=b'')
            s=probe(binary,c,fault=mode)
            assert s.get('open2')==1 and s.get('injected')==1 and not s.get('leaf_seen') and s.get('walk_closes',0)>0, (binary,mode,s)
            count+=1
        for mode in FAULTS:
            c=dict(tiny,name=mode)
            code,error=0,0
            if mode=='stat_eio' or mode=='read_eio' or mode.startswith('read_close_'):
                code,error=4,5
            elif mode in ('file_close_eio','reuse_file','walk_close'):
                code,error=4,5
            elif mode=='file_close_eintr':
                code,error=4,4
            elif mode=='walk_open_close':
                code,error=4,13
            elif mode.startswith('limit_close_'):
                c['limit']=32; code=2
            c.update(code=code,error=error,data=tiny['data'] if code==0 else b'')
            s=probe(binary,c,fault=mode)
            assert s.get('open2')==1 and s.get('injected',0)>0, (binary,mode,s)
            if mode.startswith('walk_'):
                assert s.get('walk_closes')==1 and s.get('reuse_checked')==1 and not s.get('leaf_seen'), (mode,s)
                assert s.get('next_closes',0)==(mode=='walk_close'), (mode,s)
            else:
                assert s.get('file_closes')==1 and s.get('stats')==1, (binary,mode,s)
                if 'close_' in mode or mode in ('reuse_file','parent_close'):
                    assert s.get('reuse_checked')==1, (binary,mode,s)
                if mode=='stat_eio': assert not s.get('reads'), s
                if mode.startswith('read_'): assert s.get('read_bytes')==1 and s.get('reads')==2, s
                if mode=='short': assert s.get('reads')==23 and s.get('read_bytes')==64, s
                if mode=='eintr': assert s.get('reads')==3, s
                if mode.startswith('limit_'): assert s.get('read_bytes')==33, s
            count+=1
    return count

if __name__=='__main__':
    raise SystemExit('Import through build.py or measure.py; no independent mutable fixture directory.')
