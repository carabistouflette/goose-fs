# SPDX-License-Identifier: Apache-2.0
"""Capture one known runner, including pipe bytes remaining after timeout."""
import subprocess

def run_captured(command,timeout):
    proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        stdout,stderr=proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as e:
        proc.kill()
        stdout,stderr=proc.communicate()  # drain pipes and reap before returning evidence
        e.stdout=stdout;e.stderr=stderr
        raise
    except BaseException as e:
        proc.kill()
        stdout,stderr=proc.communicate()
        e.stdout=stdout;e.stderr=stderr
        raise
    return subprocess.CompletedProcess(command,proc.returncode,stdout,stderr)
