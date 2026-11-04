#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""An owned File token does not replace kernel inode-ownership checks."""
import ctypes as c
import errno
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if len(sys.argv)==4 and sys.argv[1]=='--child':
    class Slice(c.Structure):_fields_=[('data',c.c_void_p),('len',c.c_int64)]
    I=c.c_int64;lib=c.CDLL(sys.argv[2])
    for name,args in {'context_create':[], 'context_close':[I], 'file_open':[I,Slice,I,I],
                      'file_set_permissions':[I,I,I], 'file_set_owner':[I,I,I,I],
                      'file_set_times':[I,I,I,I,I,I,I,I]}.items():
        f=getattr(lib,'gf_'+name);f.restype=I;f.argtypes=args+[Slice]
    def call(name,*args):
        m=(I*3)();code=getattr(lib,'gf_'+name)(*args,Slice(c.addressof(m),3));return code,list(m)
    os.close(int(sys.argv[2].rsplit('/',1)[1]))
    ctx=call('context_create')[1][1];data=os.fsencode(sys.argv[3]);buf=c.create_string_buffer(data)
    code,m=call('file_open',ctx,Slice(c.addressof(buf),len(data)),0,0);assert code==0;file=m[1]
    for value in [call('file_set_permissions',ctx,file,0o600),
                  call('file_set_owner',ctx,file,os.geteuid(),-1),
                  call('file_set_times',ctx,file,2,1000,0,2,1000,0),
                  call('file_set_times',ctx,file,1,0,0,1,0,0)]:
        code,m=value;assert code==4 and m[0] in [errno.EPERM,errno.EACCES] and m[1:]==[0,0],value
    assert call('file_set_times',ctx,file,0,0,0,0,0,0)==(0,[0,0,0])
    assert call('context_close',ctx)==(0,[0,0,0])
    assert call('file_set_times',ctx,file,0,0,0,0,0,0)==(4,[errno.EBADF,0,0])
    raise SystemExit(0)

if os.geteuid()!=0:
    print('metadata credential-demotion test skipped: requires root; syscall permission/error oracles remain enabled')
    raise SystemExit(0)
library=Path(os.environ.get('FS_HANDLES_LIBRARY','.build/fs-handles.so')).resolve()
with tempfile.TemporaryDirectory(prefix='goose-fs-metadata-credentials-') as temp:
    root=Path(temp);root.chmod(0o755);path=root/'root-owned';path.write_bytes(b'permission fixture');path.chmod(0o644)
    fd=os.open(library,os.O_RDONLY|os.O_CLOEXEC)
    def demote():os.setgroups([]);os.setgid(65534);os.setuid(65534)
    try:
        # The inherited library fd avoids needing access to a private source checkout.
        subprocess.run([sys.executable,'-c',Path(__file__).read_text(),'--child',f'/proc/self/fd/{fd}',str(path)],
                       pass_fds=(fd,),preexec_fn=demote,check=True,timeout=30)
    finally:os.close(fd)
    assert path.stat().st_uid==0 and path.stat().st_mode&0o7777==0o644 and path.read_bytes()==b'permission fixture'
print('unprivileged read-only File cannot change a root-owned inode; Keep/Keep still validates lifetime')
