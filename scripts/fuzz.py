#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build and run a bounded coverage-guided Clang/libFuzzer campaign for the
Goose path grammar, then replay the retained corpus through an independent
byte oracle and a weakened-guard control.

The campaign exercises fs::valid_path, fs::valid_relative and
fs::valid_components plus the InvalidInput branches that return before any
native call. It makes no filesystem, host-configuration, timing or
universal-correctness claim. Generated C, corpus, logs and artifacts stay
under .build/fuzz/runs/<stamp>/ and are never committed.
"""
import argparse
import hashlib
import json
import platform
import re
import os
import signal
import resource
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_INPUT_BYTES = 4096
MAX_RUNS = 20000
MAX_SECONDS = 300
SOURCES = ['fs.goose', 'GOOSE_REVISION', 'scripts/fuzz.py', 'tests/fuzz.goose',
           'tests/fuzz.c', 'tests/path_oracle.py', 'tests/path_grammar.goose',
           'Makefile', 'fs.build', 'tests/fuzz_driver.py']
SOURCES += sorted(str(p.relative_to(ROOT)) for p in (ROOT/'native').rglob('*')
                  if p.is_file() and p.suffix in {'.c', '.h'})
RUN_DIR = None
MIN_TARGET_EDGES = {'fs_valid_path': 5, 'fs_valid_components': 24, 'contract_valid': 41, 'fuzz_check': 26}
# fs::valid_relative is inlined by the pinned compiler, so it has no symbol of
# its own in the generated C; its verdicts are covered by the differential replay.
REQUIRED_FUNCTIONS = ['fuzz_check', 'contract_valid', 'fs_valid_path',
                      'fs_valid_components']


def fingerprint(goose, cc):
    """Identify the actual campaign inputs before building and after running."""
    compiler = shutil.which(cc)
    if compiler is None:
        raise RuntimeError('C compiler not found: ' + cc)
    version = subprocess.check_output([goose, '--version'], text=True).strip()
    return {
        'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        'sources_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES},
        'goose_executable_sha256': hashlib.sha256(Path(goose).read_bytes()).hexdigest(),
        'goose_version': version,
        'cc_executable_sha256': hashlib.sha256(Path(compiler).resolve().read_bytes()).hexdigest(),
        'cc_version': subprocess.check_output([compiler, '--version'], text=True).splitlines()[0],
    }


def seeds():
    """Focused corpus: the grammar's boundaries and the shapes mutations rarely build."""
    yield from [b'', b'/', b'//', b'///', b'.', b'..', b'...', b'a', b'/a', b'a/', b'/a/',
                b'/a/b', b'a/b', b'./a', b'../a', b'a/.', b'a/..', b'/.', b'/..', b'/./a',
                b'/../a', b'/a/.', b'/a/..', b'/a/./b', b'/a/../b', b'/a//b', b'a//b',
                b'\x00', b'/\x00', b'a\x00b', b'/\xff', b'\xff', b'/a\xffb', b'/a\nb',
                b'/a b', b'/a\\b', b'C:\\a', b'~', b'/a/b/c/d/e/f/g']
    for size in (1, 2, 3, 254, 255, 256, 257, 4093, 4094, 4095, 4096):
        yield b'a' * size
        yield b'/' + b'a' * (size - 1)
        yield b'a/' * (size // 2) + b'a' * (size % 2)
        yield b'/' + b'a/' * ((size - 1) // 2) + b'a' * ((size - 1) % 2)
    for size in (4088, 4089, 4090, 4091, 4092):
        for suffix in (b'/..', b'/.', b'/', b'/x', b'\x00'):
            yield b'/' + b'a' * size + suffix
    yield b'/' + b'a' * 2047 + b'/' + b'a' * 2046
    yield b'/' + b'a' * 2047 + b'//' + b'a' * 2045
    yield b'/' + b'a' * 2047 + b'/../' + b'a' * 2044


def event(value):
    if RUN_DIR is not None:
        with (RUN_DIR/'commands.jsonl').open('a') as stream:
            stream.write(json.dumps(value)+'\n');stream.flush();os.fsync(stream.fileno())


def run(command, timeout=MAX_SECONDS, check=False, **kwargs):
    kwargs.setdefault('cwd', ROOT)
    log = None
    if 'stdout' not in kwargs and RUN_DIR is not None:
        log = (RUN_DIR/f'command-{time_stamp()}.log').open('xb')
        kwargs.update(stdout=log, stderr=subprocess.STDOUT)
    args = [str(part) for part in command]
    event({'event':'started','command':args,'timeout':timeout})
    child = subprocess.Popen(args, start_new_session=True, **kwargs)
    try:
        code = child.wait(timeout=timeout)
    except BaseException as error:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait(timeout=2)
        event({'event':'failed','command':args,'error':repr(error),'exit':child.returncode})
        raise
    finally:
        if log:log.close()
    event({'event':'completed','command':args,'exit':code})
    if check and code:raise subprocess.CalledProcessError(code,args)
    return subprocess.CompletedProcess(args,code)


def time_stamp():
    import time
    return str(time.time_ns())


def check_coverage(functions):
    for prefix, floor in MIN_TARGET_EDGES.items():
        matches=[entry for name,entry in functions.items() if name.startswith(prefix)]
        if not matches or max(entry['edges'] for entry in matches)<floor:
            raise RuntimeError(f'generated target coverage below {prefix} edge floor {floor}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--goose', type=Path, default=ROOT / '.toolchain/goose/build/goose')
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--seconds', type=int, default=30)
    parser.add_argument('--runs', type=int, default=MAX_RUNS)
    parser.add_argument('--seed', type=int, default=20261119)
    parser.add_argument('--allow-dirty', action='store_true', help='development snapshot only, not clean-revision qualification')
    args = parser.parse_args()
    if not 1 <= args.seconds <= MAX_SECONDS:
        parser.error(f'seconds must be 1..{MAX_SECONDS}')
    if not 1 <= args.runs <= MAX_RUNS:
        parser.error(f'runs must be 1..{MAX_RUNS}')
    if not 1 <= args.seed < 2**32:
        parser.error('seed must be 1..4294967295')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    goose = str(args.goose.resolve())
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run_dir = ROOT / '.build/fuzz/runs' / f'{stamp}-seed{args.seed}'
    if run_dir.exists():
        raise SystemExit('refusing to reuse an existing evidence directory: ' + str(run_dir))
    initial = run_dir / 'seeds'
    corpus = run_dir / 'corpus'
    artifacts = run_dir / 'artifacts'
    for directory in (initial, corpus, artifacts):
        directory.mkdir(parents=True)
    global RUN_DIR
    RUN_DIR = run_dir
    commands = []

    def step(command):
        result = run(command, check=True)
        commands.append({'command': [str(part) for part in command], 'exit': result.returncode})
        return result

    all_seeds = sorted(set(seeds()))
    seed_manifest = hashlib.sha256(''.join(hashlib.sha256(data).hexdigest() for data in all_seeds).encode()).hexdigest()
    for data in all_seeds:
        if len(data) > MAX_INPUT_BYTES:
            raise RuntimeError('initial seed exceeds the campaign input bound')
        (initial / hashlib.sha256(data).hexdigest()).write_bytes(data)
    dictionary = run_dir / 'path.dict'
    dictionary.write_text('\n'.join(json.dumps(value) for value in ['/', '.', '..', 'a', '//']) + '\n"\\x00"\n')
    provenance = fingerprint(goose, args.cc)
    if provenance['source_dirty'] and not args.allow_dirty:
        raise RuntimeError('dirty source requires explicit --allow-dirty development mode')
    snapshot = run_dir/'sources'
    for name in SOURCES:
        target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    revision = (ROOT / 'GOOSE_REVISION').read_text().strip()
    if not provenance['goose_version'].split()[1].startswith(revision[:7]):
        raise RuntimeError(f"compiler {provenance['goose_version']} does not match GOOSE_REVISION {revision}")

    generated = run_dir / 'fs-fuzz.c'
    header = run_dir / 'fs-fuzz.h'
    step([goose, 'tests/fuzz.goose', '--standalone', '--debug', '--no-bce',
          '-o', str(generated), '--header', str(header)])
    # Record which path functions the pinned compiler actually emitted, so the
    # inlining of fs::valid_relative is verified rather than assumed.
    generated_text = generated.read_bytes()
    emitted = {name: (b'fs_' + name.encode() + b'_') in generated_text
               for name in ('valid_path', 'valid_relative', 'valid_components')}
    # -fno-inline keeps per-function coverage attributable to the generated C.
    instrument = ['-O1', '-g', '-fno-inline', '-fsanitize=fuzzer-no-link,address,undefined',
                  '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
    step([args.cc, *instrument, '-D_Exit=goose_fuzz_exit', '-c', str(generated),
          '-o', str(run_dir / 'fs-fuzz.o')])
    native = ['native/fs.c', 'native/handles.c']
    link = [args.cc, '-O1', '-g', '-fno-inline', '-fsanitize=fuzzer,address,undefined',
            '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
            str(run_dir / 'fs-fuzz.o'), 'tests/fuzz.c', *native,
            '-I' + str(run_dir), '-Inative', '-lm', '-ldl', '-lpthread',
            '-Wl,--wrap=gf_call', '-Wl,--wrap=gf_list', '-Wl,--wrap=gf_metadata']
    step([*link, '-o', str(run_dir / 'fs-fuzzer')])
    step([*link, '-DGOOSE_FUZZ_SELF_TEST=1', '-o', str(run_dir / 'self-test')])

    # The self-test must exercise Goose's own failed assertion path. A sanitizer
    # smoke test alone would not prove _Exit becomes a saved libFuzzer artifact.
    probe = run_dir / 'self-test-seeds'
    probe.mkdir()
    expected = b'libFuzzer Goose assertion bridge probe'
    (probe / 'input').write_bytes(expected)
    crash = run_dir / 'self-test-crash'
    with (run_dir / 'self-test.log').open('wb') as log:
        result = run([str(run_dir / 'self-test'), str(probe), '-runs=10', '-seed=1',
                                 '-exact_artifact_path=' + str(crash)], cwd=ROOT,
                                stdout=log, stderr=subprocess.STDOUT, timeout=60)
    commands.append({'command': [str(run_dir / 'self-test'), str(probe), '-runs=10', '-seed=1'],
                     'exit': result.returncode, 'log': 'self-test.log'})
    probe_log = (run_dir / 'self-test.log').read_text(errors='replace')
    if result.returncode == 0 or not crash.is_file() or crash.read_bytes() != expected or 'assert failed' not in probe_log:
        raise RuntimeError('Goose assertion-artifact self-test failed; inspect ' + str(run_dir / 'self-test.log'))
    print('Verified Goose assertions preserve the exact triggering input', flush=True)

    campaign = [str(run_dir / 'fs-fuzzer'), str(corpus), str(initial),
                '-dict=' + str(dictionary), '-max_len=' + str(MAX_INPUT_BYTES),
                '-max_total_time=' + str(args.seconds), '-runs=' + str(args.runs),
                '-seed=' + str(args.seed), '-timeout=5', '-rss_limit_mb=1024',
                '-print_coverage=1', '-print_final_stats=1',
                '-artifact_prefix=' + str(artifacts) + '/']
    print(f'Fuzzing {len(all_seeds)} initial seeds for at most {args.seconds}s/{args.runs} runs', flush=True)
    with (run_dir / 'run.log').open('wb') as log:
        result = run(campaign, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                timeout=min(args.seconds + 120, MAX_SECONDS))
    commands.append({'command': campaign, 'exit': result.returncode, 'log': 'run.log'})
    log_text = (run_dir / 'run.log').read_text(errors='replace')
    if result.returncode:
        print(log_text[-12000:])
        raise SystemExit(result.returncode if result.returncode > 0 else 1)
    finished = re.findall(r'^Done (\d+) runs in (\d+) second\(s\)', log_text, re.MULTILINE)
    if not finished or int(finished[-1][0]) < 1:
        raise RuntimeError('libFuzzer returned without a valid execution summary; inspect run.log')
    done = re.findall(r'^#\d+\s+DONE\s+cov: (\d+) ft: (\d+)', log_text, re.MULTILINE)
    if not done:
        raise RuntimeError('libFuzzer printed no DONE coverage line; inspect run.log')
    functions = {}
    for state, hits, edges, total, name, location in re.findall(
            r'^(COVERED_FUNC|UNCOVERED_FUNC): hits: (\d+) edges: (\d+)/(\d+) (\S+) (\S+)$',
            log_text, re.MULTILINE):
        functions[name] = {'state': state, 'hits': int(hits), 'edges': int(edges),
                           'total_edges': int(total), 'location': location}
    missing = [prefix for prefix in REQUIRED_FUNCTIONS
               if not any(name.startswith(prefix) for name in functions)]
    if missing:
        raise RuntimeError('campaign did not execute the generated target functions: ' + ', '.join(missing))
    executed = {name: entry for name, entry in functions.items()
                if any(name.startswith(prefix) for prefix in REQUIRED_FUNCTIONS)}
    if any(entry['state'] != 'COVERED_FUNC' or entry['hits'] < 1 for entry in executed.values()):
        raise RuntimeError('a required generated target function was not executed')

    check_coverage(functions)

    # Coverage control: the same instrumented binary on one empty input must
    # report strictly less target coverage than the campaign, so the counters
    # are live rather than a static report.
    baseline_dir = run_dir / 'baseline-seeds'
    baseline_dir.mkdir()
    (baseline_dir / 'empty').write_bytes(b'')
    with (run_dir / 'baseline.log').open('wb') as log:
        result = run([str(run_dir / 'fs-fuzzer'), str(baseline_dir), '-runs=1', '-seed=1',
                                 '-print_coverage=1'], cwd=ROOT, stdout=log,
                                stderr=subprocess.STDOUT, timeout=60)
    commands.append({'command': [str(run_dir / 'fs-fuzzer'), str(baseline_dir), '-runs=1', '-seed=1'],
                     'exit': result.returncode, 'log': 'baseline.log'})
    baseline_text = (run_dir / 'baseline.log').read_text(errors='replace')
    baseline_done = re.findall(r'^#\d+\s+DONE\s+cov: (\d+) ft: (\d+)', baseline_text, re.MULTILINE)
    if result.returncode or not baseline_done:
        raise RuntimeError('coverage control run failed; inspect baseline.log')
    baseline_cov, baseline_ft = (int(value) for value in baseline_done[-1])
    campaign_cov, campaign_ft = (int(value) for value in done[-1])
    if not (campaign_cov > baseline_cov and campaign_ft > baseline_ft):
        raise RuntimeError(f'coverage control did not separate campaign ({campaign_cov}/{campaign_ft}) '
                           f'from baseline ({baseline_cov}/{baseline_ft})')

    # Differential replay: the retained corpus through the independent oracle.
    grammar = run_dir / 'path-grammar'
    step([goose, 'build', 'tests/path_grammar.goose', '--cc', args.cc, '-O2', '-o', str(grammar)])
    with (run_dir / 'replay.log').open('wb') as log:
        result = run([sys.executable, 'tests/path_oracle.py', str(grammar),
                                 str(corpus), str(initial)],
                                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    commands.append({'command': [sys.executable, 'tests/path_oracle.py', str(grammar),
                                 str(corpus), str(initial)],
                     'exit': result.returncode, 'log': 'replay.log'})
    replay_text = (run_dir / 'replay.log').read_text(errors='replace')
    if result.returncode:
        print(replay_text[-4000:])
        raise RuntimeError('independent oracle disagreed with the retained corpus; inspect replay.log')
    print(replay_text.strip().splitlines()[0], flush=True)

    # Mutation control: a weakened component guard must fail both the oracle
    # replay and the in-process contract assertion.
    mutant = run_dir / 'mutant'
    shutil.copytree(ROOT, mutant, ignore=shutil.ignore_patterns('.git', '.build', '.toolchain', '__pycache__'))
    source = mutant / 'fs.goose'
    text = source.read_text()
    weakened = [
        ("            if n == 0 || (n == 1 && path[start] == '.') ||\n"
         "                (n == 2 && path[start] == '.' && path[start + 1] == '.') { return false; }\n",
         "            if n == 0 || (n == 1 && path[start] == '.') { return false; }\n"),
        ("    return n > 0 && !(n == 1 && path[start] == '.') &&\n"
         "        !(n == 2 && path[start] == '.' && path[start + 1] == '.');\n",
         "    return n > 0 && !(n == 1 && path[start] == '.');\n"),
    ]
    for original, replacement in weakened:
        if text.count(original) != 1:
            raise RuntimeError('mutation site not found exactly once in fs.goose')
        text = text.replace(original, replacement)
    source.write_text(text)
    mutant_grammar = run_dir / 'mutant-path-grammar'
    step([goose, 'build', str(mutant / 'tests/path_grammar.goose'), '--cc', args.cc, '-O2',
          '-o', str(mutant_grammar)])
    with (run_dir / 'mutant-replay.log').open('wb') as log:
        result = run([sys.executable, 'tests/path_oracle.py', str(mutant_grammar),
                                 str(corpus), str(initial)],
                                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    commands.append({'command': [sys.executable, 'tests/path_oracle.py', str(mutant_grammar),
                                 str(corpus), str(initial)],
                     'exit': result.returncode, 'log': 'mutant-replay.log'})
    mutant_replay = (run_dir / 'mutant-replay.log').read_text(errors='replace')
    if result.returncode == 0:
        raise RuntimeError('weakened guard passed the independent oracle; the control is not live')
    mutant_build = run_dir / 'mutant-build'
    mutant_build.mkdir()
    step([goose, str(mutant / 'tests/fuzz.goose'), '--standalone', '--debug', '--no-bce',
          '-o', str(mutant_build / 'fs-fuzz.c'), '--header', str(mutant_build / 'fs-fuzz.h')])
    step([args.cc, *instrument, '-D_Exit=goose_fuzz_exit', '-c', str(mutant_build / 'fs-fuzz.c'),
          '-o', str(mutant_build / 'fs-fuzz.o')])
    step([args.cc, '-O1', '-g', '-fno-inline', '-fsanitize=fuzzer,address,undefined',
          '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
          str(mutant_build / 'fs-fuzz.o'), 'tests/fuzz.c',
          str(mutant / 'native/fs.c'), str(mutant / 'native/handles.c'),
          '-I' + str(mutant_build), '-I' + str(mutant / 'native'), '-lm', '-ldl', '-lpthread',
          '-Wl,--wrap=gf_call', '-Wl,--wrap=gf_list', '-Wl,--wrap=gf_metadata',
          '-o', str(run_dir / 'mutant-fuzzer')])
    mutant_corpus = run_dir / 'mutant-corpus'
    shutil.copytree(corpus, mutant_corpus)
    mutant_artifacts = run_dir / 'mutant-artifacts'
    mutant_artifacts.mkdir()
    with (run_dir / 'mutant-run.log').open('wb') as log:
        result = run([str(run_dir / 'mutant-fuzzer'), str(mutant_corpus), str(initial),
                                 '-runs=' + str(args.runs), '-seed=' + str(args.seed),
                                 '-max_len=' + str(MAX_INPUT_BYTES), '-timeout=5',
                                 '-artifact_prefix=' + str(mutant_artifacts) + '/'],
                                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                timeout=min(args.seconds + 120, MAX_SECONDS))
    commands.append({'command': [str(run_dir / 'mutant-fuzzer'), str(mutant_corpus), str(initial),
                                 '-runs=' + str(args.runs)],
                     'exit': result.returncode, 'log': 'mutant-run.log'})
    mutant_log = (run_dir / 'mutant-run.log').read_text(errors='replace')
    saved = sorted(path.name for path in mutant_artifacts.iterdir())
    if result.returncode == 0 or not saved or 'assert failed' not in mutant_log:
        raise RuntimeError('weakened guard did not fail the in-process contract assertion; inspect mutant-run.log')
    print(f'Weakened guard failed as required: {len(saved)} saved artifact(s)', flush=True)

    # Dedicated controls keep output clearing and the pure/native boundary live.
    original = (ROOT/'fs.goose').read_text()
    controls = []
    read_start=original.index('fn read(path:')
    read_end=original.index('extern fn native_read_link',read_start)
    read=original[read_start:read_end]
    changes={
        'read-path-guard':(read,read.replace('!valid_path(path) || ','')),
        'read-output-clear':(read,read.replace('        out.clear();\n','')),
        'list-output-clear':('    out.clear();\n    if !valid_path(path) || byte_limit',
                             '    if !valid_path(path) || byte_limit'),
    }
    for label,(old,new) in changes.items():
        if old==new or original.count(old)!=1:raise RuntimeError('ambiguous control '+label)
        directory=run_dir/label;directory.mkdir()
        (directory/'tests').mkdir()
        (directory/'fs.goose').write_text(original.replace(old,new))
        shutil.copyfile(ROOT/'tests/fuzz.goose',directory/'tests/fuzz.goose')
        generated_control=directory/'fs-fuzz.c'
        step([goose,str(directory/'tests/fuzz.goose'),'--standalone','--debug','--no-bce',
              '-o',str(generated_control),'--header',str(directory/'fs-fuzz.h')])
        step([args.cc,*instrument,'-D_Exit=goose_fuzz_exit','-c',str(generated_control),
              '-o',str(directory/'fs-fuzz.o')])
        step([args.cc,'-O1','-g','-fno-inline','-fsanitize=fuzzer,address,undefined',
              '-fno-sanitize-recover=all',str(directory/'fs-fuzz.o'),'tests/fuzz.c',*native,
              '-I'+str(directory),'-Inative','-lm','-ldl','-lpthread',
              '-Wl,--wrap=gf_call','-Wl,--wrap=gf_list','-Wl,--wrap=gf_metadata',
              '-o',str(directory/'fuzzer')])
        inputs=directory/'inputs';inputs.mkdir();(inputs/'relative').write_bytes(b'relative')
        crash=directory/'crash'
        with (directory/'run.log').open('wb') as log:
            outcome=run([str(directory/'fuzzer'),str(inputs),'-runs=1','-seed=1',
                         '-exact_artifact_path='+str(crash)],timeout=30,stdout=log,stderr=subprocess.STDOUT)
        text=(directory/'run.log').read_text(errors='replace')
        expected='unexpected native boundary' if label=='read-path-guard' else 'assert failed'
        if outcome.returncode==0 or not crash.exists() or expected not in text:
            raise RuntimeError('negative control survived or failed for wrong reason: '+label)
        controls.append({'name':label,'exit':outcome.returncode,'artifact_sha256':hashlib.sha256(crash.read_bytes()).hexdigest()})

    if fingerprint(goose, args.cc) != provenance:
        raise RuntimeError('source or compiler changed during build/fuzzing; discard this campaign evidence')
    summary = {
        'goose_revision': revision,
        **provenance,
        'platform': platform.platform(),
        'seed': args.seed,
        'requested_runs': args.runs,
        'max_seconds': args.seconds,
        'max_input_bytes': MAX_INPUT_BYTES,
        'initial_seeds': len(all_seeds),
        'seed_manifest_sha256': seed_manifest,
        'completed_runs': int(finished[-1][0]),
        'elapsed_seconds': int(finished[-1][1]),
        'campaign_coverage': {'cov': campaign_cov, 'ft': campaign_ft},
        'baseline_coverage': {'cov': baseline_cov, 'ft': baseline_ft},
        'executed_target_functions': executed,
        'min_target_edges': MIN_TARGET_EDGES,
        'coverage_hits_unit': 'libFuzzer retained-corpus replay hits, not campaign executions',
        'qualification': 'development snapshot' if provenance['source_dirty'] else 'clean source snapshot',
        'path_functions_emitted_in_generated_c': emitted,
        'generated_c_sha256': hashlib.sha256(generated.read_bytes()).hexdigest(),
        'generated_header_sha256': hashlib.sha256(header.read_bytes()).hexdigest(),
        'fuzzer_sha256': hashlib.sha256((run_dir/'fs-fuzzer').read_bytes()).hexdigest(),
        'corpus_inputs': len([path for path in corpus.iterdir() if path.is_file()]),
        'replay': replay_text.strip().splitlines()[0],
        'mutant_replay': mutant_replay.strip().splitlines()[0],
        'mutant_artifacts': saved,
        'boundary_controls': controls,
        'commands': commands,
        'scope': ('Coverage-guided mutations of the generated Goose path target plus a second '
                  'in-process contract implementation, an independent Python byte oracle over the '
                  'retained corpus, and a weakened-guard control. No filesystem, host-configuration, '
                  'timing, soak or universal-correctness claim. A reused writable corpus changes '
                  'mutation sequences.'),
    }
    (run_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'{finished[-1][0]} runs, cov {campaign_cov} ft {campaign_ft} '
          f'(baseline {baseline_cov}/{baseline_ft}); evidence: {run_dir.relative_to(ROOT)}')


def terminate(signum, frame):
    raise SystemExit(128+signum)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, terminate)
    try:
        main()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, RuntimeError) as error:
        if RUN_DIR is not None:
            (RUN_DIR/'failure.json').write_text(json.dumps({'error':repr(error)})+'\n')
        raise SystemExit(str(error)) from error
