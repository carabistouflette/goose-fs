#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare private metadata transport with independent Python lstat results."""
import ctypes as C
import errno
import os
from pathlib import Path
import stat
import tempfile
ROOT = Path(__file__).resolve().parent.parent
class Slice(C.Structure):
    _fields_ = [('data', C.c_void_p), ('len', C.c_int64)]
lib = C.CDLL(os.environ.get('FS_NATIVE_LIBRARY', str(ROOT/'.build/fs.so')))
call = lib.gf_metadata
call.argtypes = [Slice, Slice]
call.restype = C.c_int64
checks = 0
def inspect(path):
    global checks
    data = os.fsencode(path)
    source = C.create_string_buffer(data)
    fields = (C.c_int64*18)(*([99]*18))
    code = call(Slice(C.addressof(source),len(data)), Slice(C.addressof(fields),18))
    checks += 1
    if code:
        assert all(value == 0 for value in fields[1:])
        assert (fields[0] > 0) == (code == 4)
    return code,list(fields)
with tempfile.TemporaryDirectory(prefix='goose-fs-stat-') as root:
    root = Path(root)
    file = root/'file'; file.write_bytes(b'ab\0c')
    os.utime(file, ns=(-1000000001, 1234567890123456789))
    os.chmod(file, 0o640)
    (root/'link').symlink_to('file')
    (root/'dangling').symlink_to('missing')
    os.mkfifo(root/'fifo')
    (root/'directory').mkdir()
    (root/'alias').symlink_to('directory')
    for path in [root,file,root/'link',root/'dangling',root/'fifo',root/'directory','/','/dev/null']:
        code, got = inspect(path); assert code == 0
        expected = os.lstat(path)
        mode = expected.st_mode
        kind = 1 if stat.S_ISREG(mode) else 2 if stat.S_ISDIR(mode) else 3 if stat.S_ISLNK(mode) else 5 if stat.S_ISFIFO(mode) else 6 if stat.S_ISSOCK(mode) else 7 if stat.S_ISCHR(mode) else 8 if stat.S_ISBLK(mode) else 4
        assert got[1:9] == [kind,expected.st_size,mode&0o7777,expected.st_uid,expected.st_gid,expected.st_dev,expected.st_ino,expected.st_nlink], (path,got,expected)
        assert got[9]*1000000000+got[10] == expected.st_atime_ns
        assert got[11]*1000000000+got[12] == expected.st_mtime_ns
        assert got[13]*1000000000+got[14] == expected.st_ctime_ns
        assert got[17] in (0,1)
        if got[17]: assert 0 <= got[16] < 1000000000
        else: assert got[15] == got[16] == 0
    assert inspect(root/'missing')[0] == 4
    assert inspect(root/'file/child')[0] == 4
    assert inspect(root/'alias/child')[0] == 4
    for path in [b'',b'relative',b'//a',b'/a/',b'/a/../b',b'/a\0b',b'/'*4096]: assert inspect(path)[0] == 1
print(f'{checks} independent metadata transport cases passed')
