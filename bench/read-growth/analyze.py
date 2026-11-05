#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the frozen bounded-growth adoption rules; never normalize controls."""
import argparse
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'read-contract'))
from build import GROWTH_LABELS,GROWTH_PAIRS,BASELINE
REUSED_CASES=('empty','tiny','page','chunk','max','large-budget','missing','overflow','zero-overflow','nonregular','deep')
CASES=(*REUSED_CASES,'fresh-max')

def analyze_growth(records):
    assert len(records)==2 and [r['attempt'] for r in records]==[1,2]
    assert all(r['status']=='complete' and not r['smoke'] and r['profile']=='bounded-read-growth' for r in records)
    assert records[0]['build_manifest_sha256']==records[1]['build_manifest_sha256']
    outputs=[]
    for r in records:
        assert (r['rounds'],r['count'],r['samples_per_process'],r['cpu'])==(5,2000,7,6)
        assert r['build']['baseline_revision']==BASELINE
        assert len(r['cases'])==len(CASES) and {c['name'] for c in r['cases']}==set(CASES)
        for c in r['cases']:
            assert c.get('mode','measure')==('fresh' if c['name']=='fresh-max' else 'measure')
            assert c.get('count',r['count'])==(100 if c['name']=='fresh-max' else 2000)
        assert len(r['rows'])==5*len(CASES)*len(GROWTH_LABELS)*7
        seen=set();groups={}
        for row in r['rows']:
            key=(row['round'],row['case'],row['variant'],row['sample'])
            assert key not in seen and row['case'] in CASES and row['variant'] in GROWTH_LABELS
            assert 0<=row['round']<5 and 0<=row['sample']<7 and row['ns']>0
            seen.add(key);groups.setdefault((row['case'],row['variant']),[]).append(row['ns'])
        medians={c:{n:statistics.median(groups[c,n]) for n in GROWTH_LABELS} for c in CASES}
        cells={}
        for c,m in medians.items():
            controls={x.rstrip('1'):max(m[x],m[y])/min(m[x],m[y]) for x,y in GROWTH_PAIRS}
            ratios={b+'/'+f:m[b]/m[f] for b in ('base1','base2') for f in ('fs1','fs2')}
            references={ref+'/'+f:m[ref]/m[f] for ref in ('rust1','rust2','go1','go2') for f in ('base1','base2','fs1','fs2')}
            cells[c]=dict(medians_ns=m,controls=controls,base_over_candidate=ratios,reference_over_fs=references,
                controls_pass=all(v<=1.05 for v in controls.values()),
                target_pass=c=='large-budget' and all(v>=1.10 for v in ratios.values()),
                descriptive_regression=c!='large-budget' and any(1/v>1.05 for v in ratios.values()))
        outputs.append(dict(attempt=r['attempt'],cells=cells))
    controls=all(x['controls_pass'] for r in outputs for x in r['cells'].values())
    target=all(r['cells']['large-budget']['target_pass'] for r in outputs)
    regression=any(x['descriptive_regression'] for r in outputs for x in r['cells'].values())
    return dict(records=outputs,all_controls_pass=controls,target_pass=target,descriptive_regression=regression,
        decision='eligible for adoption' if controls and target and not regression else 'retain released runtime',
        reason='inconclusive controls' if not controls else 'target below threshold' if not target else 'regression guard' if regression else 'all preregistered performance gates passed',
        no_sota_or_overall_leadership_claim=True)

if __name__=='__main__':
    if not __debug__:raise SystemExit('Python optimization disables validation')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('attempts',nargs=2,type=Path);a=p.parse_args()
    print(json.dumps(analyze_growth([json.loads(p.read_text()) for p in a.attempts]),indent=2))
