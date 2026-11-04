#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Race the real kernel against symlink replacement; test hard resource boundaries."""
import ctypes as C
import errno
import fcntl
import os
from pathlib import Path
import signal
import tempfile
import threading

signal.alarm(90)
ROOT = Path(__file__).resolve().parent.parent
class Slice(C.Structure):
    _fields_ = [('data', C.c_void_p), ('len', C.c_int64)]
lib = C.CDLL(os.environ.get('FS_NATIVE_LIBRARY', str(ROOT / '.build/fs.so')))
invoke = lib.gf_call
invoke.argtypes = [C.c_int64, Slice, Slice, C.c_int64, Slice, Slice]
invoke.restype = C.c_int64
libc = C.CDLL(None, use_errno=True)
exchange = libc.renameat2
exchange.argtypes = [C.c_int, C.c_char_p, C.c_int, C.c_char_p, C.c_uint]
exchange.restype = C.c_int

def call(op, path, data=b'', limit=1024):
    path = os.fsencode(path)
    p, d, out = C.create_string_buffer(path), C.create_string_buffer(data), C.create_string_buffer(limit)
    meta = (C.c_int64 * 3)()
    code = invoke(op, Slice(C.addressof(p), len(path)), Slice(C.addressof(d), len(data)), 4096,
                  Slice(C.addressof(out), limit), Slice(C.addressof(meta), 3))
    assert 0 <= meta[1] <= limit and 0 <= meta[2] <= 4096
    assert not code or meta[1] == meta[2] == 0
    return code, out.raw[:meta[1]], meta[0]

def swap(a, b):
    if exchange(-100, os.fsencode(a), -100, os.fsencode(b), 2):
        raise OSError(C.get_errno(), 'renameat2 exchange')

def race(a, b, probe):
    stop, started = threading.Event(), threading.Event()
    errors = []
    def attacker():
        try:
            swap(a, b)
            started.set()
            while not stop.is_set(): swap(a, b)
        except BaseException as error:
            errors.append(error)
            started.set()
    thread = threading.Thread(target=attacker)
    thread.start()
    try:
        assert started.wait(5), 'attacker did not start'
        assert not errors, errors
        for i in range(10000): probe(i)
    finally:
        stop.set()
        thread.join(timeout=5)
    assert not thread.is_alive() and not errors, errors

with tempfile.TemporaryDirectory(prefix='goose-fs-races-') as temp:
    root = Path(temp)
    good, protected, alternate = root/'good', root/'protected', root/'alternate'
    good.mkdir(); protected.mkdir()
    (good/'file').write_bytes(b'allowed')
    (protected/'file').write_bytes(b'protected')
    (protected/'sentinel').write_bytes(b'untouched')
    sentinel_inode = (protected/'file').stat().st_ino
    alternate.symlink_to(protected, target_is_directory=True)
    def ancestor_probe(i):
        code, data, _ = call(0, good/'file')
        assert code == 4 or (code == 0 and data == b'allowed'), (code, data)
        if i % 20 == 0:
            code, packed, _ = call(1, good)
            assert code == 4 or (code == 0 and b'sentinel' not in packed)
            assert call(2, good/'new', b'created')[0] in (0, 4)
            assert call(4, good/'new')[0] in (0, 4)
            assert not (protected/'new').exists()
    race(good, alternate, ancestor_probe)
    if good.is_symlink(): swap(good, alternate)
    final, other = good/'file', good/'other'
    other.symlink_to(protected/'file')
    def final_probe(_):
        code, data, _ = call(0, final)
        assert code == 4 or (code == 0 and data == b'allowed'), (code, data)
    race(final, other, final_probe)
    assert (protected/'file').read_bytes() == b'protected'
    assert (protected/'file').stat().st_ino == sentinel_inode
    assert (protected/'sentinel').read_bytes() == b'untouched'

with tempfile.TemporaryDirectory(prefix='goose-fs-boundary-') as temp:
    root = Path(temp)
    for i in range(4096): (root/(f'{i:04d}'+'x'*250)).touch()
    code, packed, _ = call(1, root, limit=1048576)
    assert code == 0 and len(packed) == 1048576
    assert call(1, root, limit=1048575)[0] == 2
    (root/'extra').touch()
    assert call(1, root, limit=1048576)[0] == 2

# Resolve an actually existing maximum-length pathname, not merely its grammar.
assert call(0, '/', limit=1)[0] == 3
assert call(2, '/', b'x')[0] == 1
with tempfile.TemporaryDirectory(prefix='goose-fs-path-') as temp:
    parent = Path(temp)
    for i in range(20):
        parent = parent / ('d'*199 + str(i % 10))
        parent.mkdir()
    target = parent / ('f'*(4095-len(os.fsencode(parent))-1))
    assert len(os.fsencode(target)) == 4095
    target.write_bytes(b'maximum')
    assert call(0, target, limit=7)[:2] == (0, b'maximum')
    assert call(0, str(target)+'x', limit=7)[0] == 1
    assert call(4, target)[0] == 0

with tempfile.TemporaryDirectory(prefix='goose-fs-stdio-') as temp:
    root = Path(temp)
    (root/'file').write_bytes(b'data')
    reader, writer = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(reader)
        try:
            for fd in (0, 1, 2): os.close(fd)
            for _ in range(100):
                assert call(0, root/'file')[:2] == (0, b'data')
                assert call(1, root)[0] == 0
                assert call(2, root/'new', b'data')[0] == 0
                assert call(4, root/'new')[0] == 0
            for fd in (0, 1, 2):
                try: fcntl.fcntl(fd, fcntl.F_GETFD)
                except OSError as error: assert error.errno == errno.EBADF
                else: raise AssertionError('leaked descriptor')
            os.write(writer, b'ok')
        except BaseException as error:
            os.write(writer, repr(error).encode())
            os._exit(1)
        os._exit(0)
    os.close(writer)
    result = os.read(reader, 4096)
    os.close(reader)
    _, status = os.waitpid(pid, 0)
    assert result == b'ok' and status == 0, (result, status)
print('20000 symlink race probes, 4096-entry/1MiB boundaries and closed stdio passed')
