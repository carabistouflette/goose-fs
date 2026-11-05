#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply preregistered per-cell rules without pooling or correcting controls."""
import argparse
import json
from pathlib import Path
import statistics
from build import LABELS,PAIRS
from conformance import PRIMARY
CASES=(*PRIMARY,'missing','overflow','zero-overflow','nonregular','deep')

def analyze(records):
    assert len(records)==2 and [r['attempt'] for r in records]==[1,2], 'first two attempts required'
    assert all(r['status']=='complete' and not r['smoke'] for r in records), 'failed/incomplete/smoke checkpoint is inconclusive'
    assert records[0]['build_manifest_sha256']==records[1]['build_manifest_sha256'], 'different frozen builds'
    outputs=[]
    for r in records:
        assert (r['rounds'],r['count'],r['samples_per_process'],r['cpu'])==(5,200,7,6)
        assert len(r['rows'])==5*len(CASES)*len(LABELS)*7
        seen=set();groups={}
        for row in r['rows']:
            key=(row['round'],row['case'],row['variant'],row['sample'])
            assert key not in seen and row['case'] in CASES and row['variant'] in LABELS
            assert 0<=row['round']<5 and 0<=row['sample']<7 and row['ns']>0
            seen.add(key);groups.setdefault((row['case'],row['variant']),[]).append(row['ns'])
        medians={c:{n:statistics.median(groups[c,n]) for n in LABELS} for c in CASES}
        cells={}
        for c,m in medians.items():
            controls={x.rstrip('1'):max(m[x],m[y])/min(m[x],m[y]) for x,y in PAIRS}
            ratios={ref+'/'+fs:m[ref]/m[fs] for ref in ('rust1','rust2','go1','go2') for fs in ('fs1','fs2')}
            cells[c]=dict(medians_ns=m,controls=controls,reference_over_fs=ratios,
                controls_pass=all(v<=1.05 for v in controls.values()),
                all_reference_ratios_pass=all(v>=1.10 for v in ratios.values()),
                descriptive_regression=c in PRIMARY and any(1/v>1.05 for v in ratios.values()))
        outputs.append(dict(attempt=r['attempt'],cells=cells))
    labels={c:('qualifying FS lead' if all(o['cells'][c]['controls_pass'] and o['cells'][c]['all_reference_ratios_pass'] for o in outputs) else 'inconclusive') for c in CASES}
    return dict(records=outputs,labels=labels,no_overall_leadership_label=True)

def main():
    if not __debug__:raise SystemExit('Python optimization disables validation')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('attempts',nargs=2,type=Path);a=p.parse_args()
    print(json.dumps(analyze([json.loads(p.read_text()) for p in a.attempts]),indent=2))
if __name__=='__main__':main()
