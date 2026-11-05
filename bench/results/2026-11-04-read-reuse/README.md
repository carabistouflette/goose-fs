# Read output reuse — 2026-11-04

Recorded experiment, with the source and toolchain identities stated below.
These tables are not automatically measurements of current main. See
[the currentness inventory](../../../docs/PERFORMANCE.md) before applying them.
To rebuild an experiment, use its measured source revision in a separate checkout.
For the retained raw artifacts and original replay scripts, use publication
`60cec1e1956962772fff6091b4c7ff1876533f9e`. Historical raw artifacts are unchanged.

Baseline: `3157fd2d0183d994e481c778a51e193bb93da340`. Candidate: `81e304c7938373355ac3c20b9135ac4eeb9bc843` (clean tree; production change is `c483607`). Identical benchmark source and compiler; raw data retain both binary SHA256 values, harness hash, compiler pin/flags, host/load/affinity and all 1,050 samples.

Five alternating baseline/candidate rounds, seven sample means per workload/variant/round, 300 calls per sample. Warm tmpfs, GCC 16.2.1 -O2, shared Linux host, CPU6 affinity with no exclusive-core/frequency guarantee. Values are median sample means in ns/call.

The read path reuses its already initialized prefix instead of clearing and reinitializing the complete buffer. Repeated exact-size 64 KiB and 1 MiB reads improve about 1.30× and 1.41× in this series. Small-file/oversized-budget calls still initialize growth after shrinking; no general zero-copy claim. Unchanged workloads show noise/regressions and are all retained below.

[Raw samples and provenance](raw.json)

| Workload | Baseline ns | Candidate ns | Change |
| --- | ---: | ---: | ---: |
| read-empty | 3,451 | 3,277 | -5.0% |
| read-empty-max-buffer | 52,900 | 52,674 | -0.4% |
| read-small | 3,613 | 3,598 | -0.4% |
| read-small-max-buffer | 50,311 | 52,330 | +4.0% |
| read-missing | 2,818 | 2,784 | -1.2% |
| read-64k | 12,317 | 9,445 | -23.3% |
| read-1m | 215,759 | 152,835 | -29.2% |
| read-overflow | 3,908 | 3,947 | +1.0% |
| read-deep | 4,454 | 4,372 | -1.8% |
| list-one | 4,711 | 4,732 | +0.4% |
| list-one-max-buffer | 53,107 | 55,260 | +4.1% |
| create-remove-file | 14,280 | 14,086 | -1.4% |
| create-remove-dir | 7,853 | 8,290 | +5.6% |
| list-1000 | 183,909 | 174,245 | -5.3% |
| list-1000-max-buffer | 296,053 | 300,752 | +1.6% |

## Reproduce

Check out candidate `81e304c7938373355ac3c20b9135ac4eeb9bc843`, install the pinned compiler, then:

```sh
python3 bench/build-baseline.py --revision 3157fd2d0183d994e481c778a51e193bb93da340 \
  --goose .toolchain/goose/build/goose --cc gcc --output .build/read-baseline
.toolchain/goose/build/goose build bench/bench.goose --cc gcc -O2 -o .build/read-candidate
python3 bench/measure.py --goose .toolchain/goose/build/goose --cc gcc \
  --binary .build/read-candidate --baseline .build/read-baseline \
  --baseline-revision 3157fd2d0183d994e481c778a51e193bb93da340 \
  --iterations 300 --rounds 5 --output .build/read-pair.json
```

The recorded run used `taskset -c 6`. All workload/sample checksums matched. Public alternating-size/sentinel/error tests, independent implementation reviews, GCC/Clang public/debug/oracle suites and ASan/UBSan passed. The native filesystem kernel and its lookup/security policy are unchanged by this optimization.
