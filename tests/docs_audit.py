#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check output guards without reading or changing real source/history files."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
if not __debug__:raise SystemExit('Python optimization disables audit tests')
source=Path(__file__).resolve().parent.parent/'scripts/audit-docs.py'
with tempfile.TemporaryDirectory(prefix='goose-fs-doc-guards-') as tmp:
    root=Path(tmp);(root/'scripts').mkdir();(root/'docs').mkdir();(root/'.build').mkdir()
    script=root/'scripts/audit-docs.py';shutil.copyfile(source,script)
    protected=root/'protected';protected.write_bytes(b'preserve source')
    def reject(output,dispersion,expected,optimized=False):
        r=subprocess.run([sys.executable,*(['-O'] if optimized else []),str(script),'--output',str(output),'--dispersion',str(dispersion)],capture_output=True,text=True,timeout=10)
        assert r.returncode!=0 and expected in r.stderr,(r.returncode,r.stderr)
        assert protected.read_bytes()==b'preserve source'
    reject(protected,root/'.build/a','forbidden')
    reject(root/'.build/a',root/'.build/a','distinct')
    link=root/'docs/announcement-audit.json';link.symlink_to(protected)
    reject(link,root/'.build/a','forbidden');link.unlink()
    (root/'.build').rmdir();(root/'.build').symlink_to(root/'docs',target_is_directory=True)
    reject(root/'.build/a',root/'docs/performance-dispersion.json','must not redirect')
    reject(protected,protected,'optimization disables',optimized=True)
    assert not (root/'docs/a').exists()
print('Audit guards: source/history writes, collisions, redirected doc/build paths and -O rejected')
