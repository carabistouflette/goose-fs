#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent Python filesystem oracle for the private kernel's OS behavior."""
import ctypes as C
import errno
import os
from pathlib import Path
import random
import pty
import signal
import socket
import tempfile
signal.alarm(60)
class Slice(C.Structure):
    _fields_ = [('data', C.c_void_p), ('len', C.c_int64)]
lib = C.CDLL(str(Path(__file__).resolve().parent.parent / '.build/fs.so'))
call = lib.gf_call
call.argtypes = [C.c_int64, Slice, Slice, C.c_int64, Slice, Slice]
call.restype = C.c_int64
checks = 0

def invoke(op, path, data=b'', cap=1048576, entries=4096):
    global checks
    path = os.fsencode(path)
    p, d, out = C.create_string_buffer(path), C.create_string_buffer(data), C.create_string_buffer(cap)
    meta = (C.c_int64 * 3)(99, 99, 99)
    code = call(op, Slice(C.addressof(p), len(path)), Slice(C.addressof(d), len(data)), entries,
                Slice(C.addressof(out), cap), Slice(C.addressof(meta), 3))
    checks += 1
    assert (meta[0] > 0) == (code == 4), (code, list(meta))
    if code:
        assert meta[1] == meta[2] == 0
    assert 0 <= meta[1] <= cap and 0 <= meta[2] <= entries
    return code, bytes(out[:meta[1]]), meta[2], meta[0]

with tempfile.TemporaryDirectory(prefix='goose-fs-model-') as root:
    root = os.fsencode(root)
    file = root + b'/file'
    rng = random.Random(80931)
    for size in [0, 1, 2, 255, 4096, 65536, 1048576]:
        data = rng.randbytes(size)
        assert invoke(2, file, data)[0] == 0
        assert Path(os.fsdecode(file)).read_bytes() == data
        assert os.stat(file).st_mode & 0o777 & ~0o600 == 0
        assert invoke(2, file, b'replacement')[0] == 4
        for cap in sorted({0, max(0, size - 1), size, min(1048576, size + 1)}):
            result = invoke(0, file, cap=cap)
            assert result[0] == (2 if cap < size else 0)
            if cap >= size: assert result[1] == data
        assert invoke(4, file)[0] == 0
    for path in [b'', b'relative', b'//tmp', root+b'/', root+b'//a', root+b'/./a', root+b'/../a', root+b'/a\0b', b'/'*4096]:
        for op in range(6): assert invoke(op, path)[0] == 1
    # Arbitrary filenames must not be converted to text or newline records.
    names = [b'a', b'line\nbreak', b'\xff\xfe', b'..valid', b'x'*255]
    names += [b'n'+str(i).encode() for i in range(120)]
    for name in names: assert invoke(2, root+b'/'+name)[0] == 0
    needed = sum(len(n)+2 for n in names)
    code, packed, count, _ = invoke(1, root, cap=needed, entries=len(names))
    assert code == 0 and count == len(names)
    records, pos = {}, 0
    while pos < len(packed):
        tag = packed[pos]; end = packed.index(0, pos+1)
        records[packed[pos+1:end]] = tag; pos = end+1
    assert set(records) == set(os.listdir(root)) == set(names)
    assert all(t in (0, 1) for t in records.values())
    assert invoke(1, root, cap=needed-1)[0] == 2
    assert invoke(1, root, entries=len(names)-1)[0] == 2
    assert invoke(1, root, cap=0, entries=0)[0] == 2
    for name in names: assert invoke(4, root+b'/'+name)[0] == 0
    assert invoke(1, root, cap=0, entries=0)[:3] == (0, b'', 0)
    directory = root+b'/directory'
    assert invoke(3, directory)[0] == 0
    assert os.stat(directory).st_mode & 0o777 & ~0o700 == 0
    assert invoke(0, directory)[0] == 3
    link = root+b'/link'; os.symlink(directory, link)
    assert invoke(1, link)[0] == 4
    for op in range(6): assert invoke(op, link+b'/child')[0] == 4
    assert invoke(4, link)[0] == 0 and os.path.isdir(directory)
    assert invoke(5, directory)[0] == 0
    os.mkfifo(root+b'/fifo')
    assert invoke(0, root+b'/fifo')[0] == 3
    sock = socket.socket(socket.AF_UNIX); sock.bind(root+b'/socket')
    assert invoke(0, root+b'/socket')[0] == 4
    sock.close()
    assert invoke(0, b'/dev/null')[0] == 3
    os.symlink(root+b'/missing', link)
    assert invoke(2, link)[0] == 4
    assert invoke(0, link)[0] == 4
    assert invoke(4, link)[0] == 0
    # Hard links are permitted; no accidental confinement promise.
    assert invoke(2, file, b'linked')[0] == 0
    os.link(file, link)
    assert invoke(0, link, cap=6)[1] == b'linked'
    before = len(os.listdir('/proc/self/fd'))
    for _ in range(1000):
        assert invoke(0, file, cap=5)[0] == 2
        assert invoke(1, file)[0] == 4
        assert invoke(0, root+b'/absent')[0] == 4
    assert len(os.listdir('/proc/self/fd')) == before
    # Kernel still enforces limits against filesystem contents during mutation.
    for _ in range(300):
        data = rng.randbytes(rng.randrange(512)); Path(os.fsdecode(file)).write_bytes(data)
        limit = rng.randrange(512)
        result = invoke(0, file, cap=limit)
        assert result[0] == (0 if len(data) <= limit else 2)
        if not result[0]: assert result[1] == data
# A rejected TTY read must not acquire a controlling terminal.
master, slave = pty.openpty()
tty = os.ttyname(slave)
pid = os.fork()
if pid == 0:
    try:
        os.close(master); os.close(slave); os.setsid()
        try:
            fd = os.open('/dev/tty', os.O_RDONLY | os.O_NOCTTY)
        except OSError as error:
            assert error.errno == errno.ENXIO
        else:
            os.close(fd); raise AssertionError('session unexpectedly has tty')
        assert invoke(0, tty, cap=1)[0] == 3
        try:
            fd = os.open('/dev/tty', os.O_RDONLY | os.O_NOCTTY)
        except OSError as error:
            assert error.errno == errno.ENXIO
        else:
            os.close(fd); raise AssertionError('read acquired controlling tty')
    except BaseException:
        import traceback
        traceback.print_exc(); os._exit(1)
    os._exit(0)
_, status = os.waitpid(pid, 0)
os.close(master); os.close(slave)
assert status == 0, status
print(f'{checks} filesystem oracle calls and isolated TTY regression passed')
