#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build independent matched-path replicas and test the bounded-read contract."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.append(str(ROOT/'bench'))
from compare.provenance import sha256,goose_stdlib,runtime_settings,GO_SETTINGS
from conformance import fixtures,check_release,check_faults
LABELS=('fs1','rust1','go1','fs2','rust2','go2')
PAIRS=(('fs1','fs2'),('rust1','rust2'),('go1','go2'))
WRAP='-Wl,--wrap=syscall,--wrap=openat,--wrap=open,--wrap=fstat,--wrap=read,--wrap=__read_chk,--wrap=close'

def capture(args):
    return subprocess.check_output(args,cwd=ROOT,text=True,timeout=30).strip()

def inputs():
    paths=[ROOT/'fs.goose',ROOT/'fs.build',ROOT/'GOOSE_REVISION',*sorted((ROOT/'native').glob('*')),
           *sorted(HERE.rglob('*')),ROOT/'bench/compare/provenance.py',ROOT/'tests/read_contract.py']
    return {str(p.relative_to(ROOT)):sha256(p) for p in paths
            if p.is_file() and '__pycache__' not in p.parts}

def tools(goose,cc,rust):
    rustc=capture(['rustup','which','--toolchain',rust,'rustc'])
    go=str(Path(shutil.which('go')).resolve())
    return dict(goose_path=goose,goose_sha256=sha256(goose),goose=capture([goose,'--version']),
        stdlib=goose_stdlib(goose),cc_path=cc,cc_sha256=sha256(cc),cc=capture([cc,'--version']),
        rust_toolchain=rust,rustc_path=rustc,rustc_sha256=sha256(rustc),
        rust=capture([rustc,'--version','--verbose']),go_path=go,go_sha256=sha256(go),
        go=capture([go,'version']),go_environment=subprocess.check_output([go,'env','-json',*GO_SETTINGS,'GOVERSION','GOROOT','GOTOOLDIR','GOWORK'],cwd=ROOT,text=True,timeout=30,env=dict(os.environ,CGO_ENABLED='0',GOTOOLCHAIN='local',GOFLAGS='',GOWORK='off')).strip())

def publish(out,name,data,executable=False):
    with tempfile.TemporaryDirectory(prefix='publish-',dir=out) as t:
        p=Path(t)/'file';p.write_bytes(data);p.chmod(0o700 if executable else 0o600)
        p.replace(out/name)

def main():
    if not __debug__:raise SystemExit('Python optimization disables validation; use ordinary Python')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--goose',required=True);p.add_argument('--cc',default='gcc')
    p.add_argument('--rust-toolchain',default='1.99.1')
    p.add_argument('--output-dir',type=Path,default=ROOT/'.build/read-contract')
    a=p.parse_args()
    if (platform.system(),platform.machine())!=('Linux','x86_64'):p.error('Linux x86-64 only')
    allowed=(ROOT/'.build').resolve();out=a.output_dir.resolve()
    if out==allowed or not out.is_relative_to(allowed):p.error('output must be a child of this checkout .build')
    out.mkdir(parents=True,exist_ok=True)
    goose=str(Path(a.goose).resolve());cc=shutil.which(a.cc)
    if not cc:p.error('C compiler not found')
    cc=str(Path(cc).resolve())
    with (out/'build.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if any(out.glob('attempt-*.jsonl')):raise SystemExit('measured attempts already exist; preserve this checkpoint and use a new directory')
        (out/'build.json').unlink(missing_ok=True)
        before=inputs();versions=tools(goose,cc,a.rust_toolchain)
        revision=capture(['git','rev-parse','HEAD']);dirty=bool(capture(['git','status','--porcelain']))
        bins={};sections={};logs={};commands={}
        with tempfile.TemporaryDirectory(prefix='read-contract-build-',dir=allowed) as tmp:
            build=Path(tmp)/'build'
            def reset():
                if build.exists():shutil.rmtree(build)
                for name in before:
                    target=build/name;target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes((ROOT/name).read_bytes())
                (build/'bench/read-contract/fault-cc.sh').chmod(0o700)
            def environment():
                return dict(os.environ,GOOSE_HOME=str(build/'goose-home'),GOOSE_STDLIB=versions['stdlib']['directory'],
                    GOCACHE=str(build/'go-cache'),GOMODCACHE=str(build/'go-mod-cache'),
                    CGO_ENABLED='0',GOTOOLCHAIN='local',GOFLAGS='',GOWORK='off',GOPROXY='off',GOSUMDB='off',READ_CONTRACT_CC=cc)
            def compile_one(language,fault=False):
                env=environment();source=build/'bench/read-contract';result=build/'runner';cmds=[]
                if language=='fs':
                    entry=source/'main.goose';compiler=cc
                    if fault:
                        entry=source/'fault.goose'
                        entry.write_text((source/'main.goose').read_text().replace('fn main()',
                            'extern fn fault_finish() = "contract_fault_finish";\nfn main()').replace('// FAULT_FINISH','fault_finish();'))
                        (source/'fault.build').write_text('c_sources = ["native/faults.c"];\nc_flags_cc = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-pthread"];\n')
                        compiler=str(source/'fault-cc.sh')
                    cmds.append(([goose,'build',str(entry),'--cc',compiler,'-O2','-v','-o',str(result)],build))
                elif language=='rust':
                    cmds.append(([cc,'-std=c11','-Wall','-Wextra','-Werror','-O2','-c',str(source/'native/stat-abi.c'),'-o',str(build/'stat-abi.o')],build))
                    flags=[]
                    if fault:
                        cmds.append(([cc,'-std=c11','-Wall','-Wextra','-Werror','-O2','-c',str(source/'native/faults.c'),'-o',str(build/'faults.o')],build))
                        flags=['--cfg','adaptertest','-Clink-arg='+str(build/'faults.o'),'-Clink-arg='+WRAP]
                    cmds.append(([versions['rustc_path'],'--edition=2024','-Copt-level=2','-Ccodegen-units=1',str(source/'main.rs'),
                        '-Clink-arg='+str(build/'stat-abi.o'),*flags,'-o',str(result)],build))
                else:
                    cmds.append(([versions['go_path'],'build','-trimpath','-buildvcs=false',*(['-tags','adaptertest'] if fault else []),'-o',str(result),'.'],source))
                log=build/'build.log'
                with log.open('w') as stream:
                    for command,cwd in cmds:
                        stream.write(json.dumps(dict(command=command,cwd=str(cwd)))+'\n');stream.flush()
                        try:
                            subprocess.run(command,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=240)
                        except BaseException:
                            stream.flush()
                            stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
                            publish(out,'failed-build-'+stamp+'.log',log.read_bytes())
                            raise
                return result,log,[dict(command=c,cwd=str(w)) for c,w in cmds]
            for label in LABELS:
                reset();binary,log,cmd=compile_one(label.rstrip('12'))
                publish(out,label,binary.read_bytes(),True);publish(out,label+'-build.log',log.read_bytes())
                bins[label]=sha256(out/label);logs[label]=sha256(out/(label+'-build.log'));commands[label]=cmd
                subprocess.run(['objcopy','--dump-section',f'.text={build}/text','--dump-section',f'.rodata={build}/rodata',str(out/label),str(build/'probe')],check=True,timeout=30)
                sections[label]={n:sha256(build/n) for n in ('text','rodata')}
            assert all(bins[x]==bins[y] and sections[x]==sections[y] for x,y in PAIRS),'replicas differ; timing ineligible'
            fault_bins=[];fault_hashes={}
            for language in ('fs','rust','go'):
                reset();binary,log,cmd=compile_one(language,True)
                label=language+'-fault';publish(out,label,binary.read_bytes(),True);publish(out,label+'-build.log',log.read_bytes())
                fault_bins.append(out/label);fault_hashes[label]=sha256(out/label);logs[label]=sha256(out/(label+'-build.log'));commands[label]=cmd
            cases,extra=fixtures(Path(tmp)/'fixtures')
            checks=dict(release=check_release([out/n for n in LABELS],cases,extra),faults=check_faults(fault_bins,cases))
            build_path=str(build)
        assert inputs()==before and tools(goose,cc,a.rust_toolchain)==versions and capture(['git','rev-parse','HEAD'])==revision,'build inputs changed'
        record=dict(schema=1,profile='bounded-read-contract',timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_revision=revision,source_dirty=dirty,sources_sha256=before,toolchains=versions,
            binaries_sha256=bins,fault_binaries_sha256=fault_hashes,sections_sha256=sections,replica_pairs=PAIRS,build_logs_sha256=logs,
            commands=commands,build_path=build_path,conformance=checks,
            effective_go_overrides=dict(CGO_ENABLED='0',GOTOOLCHAIN='local',GOFLAGS='',GOWORK='off',GOPROXY='off',GOSUMDB='off',GOCACHE=build_path+'/go-cache',GOMODCACHE=build_path+'/go-mod-cache'),
            runtime_settings=runtime_settings(),build_environment={k:os.environ.get(k) for k in
                ('CFLAGS','CPPFLAGS','LDFLAGS','RUSTFLAGS','SOURCE_DATE_EPOCH','LD_PRELOAD','GLIBC_TUNABLES')},
            identical_executables=True,identical_sections=True)
        publish(out,'build.json',(json.dumps(record,indent=2)+'\n').encode())
        print(json.dumps(dict(replica_pairs='byte-identical',conformance=checks,source_dirty=dirty)))

if __name__=='__main__':main()
