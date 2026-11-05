# SPDX-License-Identifier: Apache-2.0
"""Serial child observations, without changing the runner or its clocks."""
import math
import resource
import subprocess
import time
from child import run_captured

FIELDS=('ru_utime','ru_stime','ru_nvcsw','ru_nivcsw','ru_minflt','ru_majflt','ru_inblock','ru_oublock')

def snapshot():
    value=resource.getrusage(resource.RUSAGE_CHILDREN)
    return {key:getattr(value,key) for key in FIELDS}

def observe(command,event,emit,timeout=60):
    # No other child is running/reaped between these snapshots. run_captured
    # drains/reaps its child on normal exit and timeout before returning/raising.
    before=snapshot();start=time.perf_counter_ns()
    try:
        proc=run_captured(command,timeout)
        event.update(returncode=proc.returncode,stdout_hex=proc.stdout.hex(),stderr_hex=proc.stderr.hex())
    except subprocess.TimeoutExpired as e:
        event.update(timeout=True,stdout_hex=(e.stdout or b'').hex(),stderr_hex=(e.stderr or b'').hex())
        raise
    except BaseException as e:
        event['launch_error']=repr(e)
        raise
    finally:
        wall=time.perf_counter_ns()-start
        try:
            after=snapshot();delta={key:after[key]-before[key] for key in FIELDS}
            event['resources']=dict(before=before,after=after,delta=delta,parent_wall_ns=wall)
            if not all(math.isfinite(v) and v>=0 for d in (before,after,delta) for v in d.values()):
                event['resource_error']='invalid/nonmonotonic child counters'
        except BaseException as e:
            event['resource_error']=repr(e)
        emit(event)
    assert 'resource_error' not in event,event
    return proc
