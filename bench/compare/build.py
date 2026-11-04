#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build native-API comparator runners; no downloads or external dependencies."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
from provenance import ROOT, RUNNERS, capture, sha256, sources, toolchains
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--goose',required=True)
p.add_argument('--cc',default='gcc')
p.add_argument('--rust-toolchain',default='1.99.1')
p.add_argument('--adaptive-listing',action='store_true',help='opt goose-fs listings into adaptive staging')
a=p.parse_args()
out=ROOT/'.build/compare'; out.mkdir(exist_ok=True,parents=True)
manifest=out/'build.json'
# A failed/interrupted rebuild must never leave an apparently valid old manifest.
manifest.unlink(missing_ok=True)
compiler=str(Path(a.goose).resolve())
before=sources()
versions=toolchains(compiler,a.cc,a.rust_toolchain)
goose_env=dict(os.environ,GOOSE_STDLIB=versions['goose_stdlib']['directory'])
for name, custom in [('goose-fs','true'),('goose-stdlib','false')]:
    source=out/f'{name}.goose'
    source.write_text((ROOT/'bench/compare/goose.goose.in').read_text().replace('@CUSTOM@',custom).replace('@ADAPTIVE@','true' if a.adaptive_listing else 'false'))
    subprocess.run([compiler,'format',str(source)],cwd=ROOT,check=True)
    subprocess.run([compiler,'build',str(source),'--cc',a.cc,'-O2','-o',str(out/name)],cwd=ROOT,env=goose_env,check=True)
subprocess.run(['rustc',f'+{a.rust_toolchain}','--edition=2024','-C','opt-level=2','-C','codegen-units=1',
                'bench/compare/rust.rs','-o',str(out/'rust')],cwd=ROOT,check=True)
subprocess.run(['go','build','-trimpath','-o',str(out/'go'),'bench/compare/go.go'],cwd=ROOT,check=True)
if sources()!=before or toolchains(compiler,a.cc,a.rust_toolchain)!=versions:
    raise SystemExit('Build inputs changed during compilation; rebuild from stable sources')
record=dict(schema=1,timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    source_revision=capture(['git','rev-parse','HEAD']),
    adaptive_listing=a.adaptive_listing,source_dirty=bool(capture(['git','status','--porcelain'])),
    source_sha256=before,toolchains=versions,
    binaries_sha256={name:sha256(out/name) for name in RUNNERS},
    flags={'goose':['-O2'],'rust':['opt-level=2','codegen-units=1','edition=2024'],
           'go':['-trimpath','plus GOFLAGS/settings recorded in toolchains']},
    go_build_settings=capture(['go','version','-m',str(out/'go')]))
manifest.write_text(json.dumps(record,indent=2)+'\n')
print('Built four native-API runners in .build/compare')
