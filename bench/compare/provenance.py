# SPDX-License-Identifier: Apache-2.0
"""Build inputs shared by the builder and measurement verifier."""
import hashlib
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
RUNNERS = ('goose-fs', 'goose-stdlib', 'rust', 'go')
GO_SETTINGS = ('GOOS', 'GOARCH', 'GOEXPERIMENT', 'CGO_ENABLED', 'GOFLAGS',
               'GOAMD64', 'GOARM64', 'GOTOOLCHAIN')
RUNTIME_SETTINGS = ('GOGC', 'GOMEMLIMIT', 'GODEBUG', 'GOMAXPROCS',
                    'MALLOC_CONF', 'GLIBC_TUNABLES', 'LD_PRELOAD')

def capture(args):
    return subprocess.check_output(args, cwd=ROOT, text=True, timeout=30).strip()

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def sources():
    paths = [ROOT/'tests/native_compare.py', ROOT/'bench/read-contract/child.py', ROOT/'fs.goose', ROOT/'fs.build', ROOT/'GOOSE_REVISION',
             *sorted((ROOT/'native').glob('*')), *sorted((ROOT/'bench/compare').glob('*'))]
    return {str(path.relative_to(ROOT)): sha256(path) for path in paths if path.is_file()}

def goose_stdlib(goose):
    # Match the compiler's environment/executable-relative search order. Require
    # one complete std/os directory, then bind its source bytes as build inputs.
    exe=Path(goose).resolve()
    override=Path(os.environ['GOOSE_STDLIB'] or '/') if 'GOOSE_STDLIB' in os.environ else None
    candidates=([override if override.is_absolute() else ROOT/override] if override is not None else [])
    candidates += [parent/'stdlib' for parent in list(exe.parents)[:4]]+[ROOT/'stdlib']
    for candidate in candidates:
        if (candidate/'std.goose').is_file():
            if not (candidate/'os.goose').is_file():
                raise RuntimeError('benchmarks require std and os in one complete Goose standard library directory')
            directory=candidate.resolve()
            return dict(directory=str(directory),sources_sha256={str(p.relative_to(directory)):sha256(p)
                        for p in sorted(directory.rglob('*.goose')) if p.is_file()})
    raise RuntimeError('cannot locate Goose standard library; set GOOSE_STDLIB')

def toolchains(goose, cc, rust_toolchain):
    return dict(goose=capture([goose, '--version']), goose_sha256=sha256(goose),goose_stdlib=goose_stdlib(goose),
                goose_revision=(ROOT/'GOOSE_REVISION').read_text().strip(),
                native_cc=capture([cc, '--version']),
                rust=capture(['rustc', f'+{rust_toolchain}', '--version', '--verbose']),
                go=capture(['go', 'version']),
                go_settings=capture(['go', 'env', '-json', *GO_SETTINGS]))

def runtime_settings():
    return {key: os.environ.get(key) for key in RUNTIME_SETTINGS}
