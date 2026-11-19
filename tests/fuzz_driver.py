# SPDX-License-Identifier: Apache-2.0
"""Finite tests of fuzz gate failure and process cleanup, without fuzz builds."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

spec=importlib.util.spec_from_file_location('fuzz_driver',Path(__file__).resolve().parents[1]/'scripts/fuzz.py')
fuzz=importlib.util.module_from_spec(spec);spec.loader.exec_module(fuzz)


class Driver(unittest.TestCase):
    def test_coverage_regressions_are_rejected(self):
        values={name+'_clone':{'edges':floor} for name,floor in fuzz.MIN_TARGET_EDGES.items()}
        fuzz.check_coverage(values)
        for name,floor in fuzz.MIN_TARGET_EDGES.items():
            changed={k:dict(v) for k,v in values.items()};changed[name+'_clone']['edges']=floor-1
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'coverage below'):
                fuzz.check_coverage(changed)

    def test_timeout_kills_group_and_keeps_journal(self):
        with tempfile.TemporaryDirectory() as raw:
            folder=Path(raw);fuzz.RUN_DIR=folder
            code=('import subprocess,sys,time;from pathlib import Path;'
                  'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);'
                  'Path(sys.argv[1]).write_text(str(p.pid));time.sleep(30)')
            pid=None;terminated=False
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    fuzz.run([sys.executable,'-c',code,str(folder/'pid')],timeout=2)
                pid=int((folder/'pid').read_text());deadline=time.monotonic()+2
                while True:
                    try:fields=Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()
                    except FileNotFoundError:terminated=True;break
                    if fields and fields[0] in ('Z','X'):terminated=True;break
                    if time.monotonic()>=deadline:self.fail('live descendant after fuzz timeout')
                    time.sleep(.01)
                events=[json.loads(line) for line in (folder/'commands.jsonl').read_text().splitlines()]
                self.assertEqual(events[-1]['event'],'failed')
            finally:
                if pid is None and (folder/'pid').exists():pid=int((folder/'pid').read_text())
                if pid is not None and not terminated:
                    import signal
                    try:os.kill(pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                fuzz.RUN_DIR=None


if __name__=='__main__':unittest.main()
