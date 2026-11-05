# Matched-path identical-code listing controls

Recorded experiment, with the source and toolchain identities stated below.
These tables are not automatically measurements of current main. See
[the currentness inventory](../../../docs/PERFORMANCE.md) before applying them.
To rebuild an experiment, use its measured source revision in a separate checkout.
For the retained raw artifacts and original replay scripts, use publication
`60cec1e1956962772fff6091b4c7ff1876533f9e`. Historical raw artifacts are unchanged.

Two independent A/A records, 5,320 rows each: [initial](initial.json) at `c9ddc0c00bd9e0118655d740a11b7b6c193ba3d8` and [final](final.json) at `3fbe3923cd7c9f89a7e1e196ef91cd9d59b17076`. Both export library revision `edd94ced1d7ae76490efb497794b9ba19504d4da`. [Interactive observations](comparison.html).

Within each build pair, complete executable and text/rodata section hashes match. Each build independently compiles the native package and runtime in the same source, harness, output, CWD and fresh GOOSE_HOME paths. Temporary base paths differ between records; executable identity is required within a pair, not across records. Saved execution paths a/b differ and are recorded. Sources, compiler, stdlib and hashes are verified before/after timing. Post-measurement tooling hardening adds atomic artifact publication and stronger rejection fixtures; it changes no measured library code.

All 10,640 observations remain unmodified. Median A/B ratios span **0.685–2.531** initially and **0.702–1.706** finally. These are identical-code observations, not speedups, noise bounds, normalization factors, proof of a cause or validation/invalidation of earlier optimization results. No old raw data or registered library source is changed. Future A/B claims need their own matched-path comparison; this control alone establishes no causal performance conclusion.

Each record uses five shuffled rounds, 76 workloads, two executables, seven sample means and five calls per mean. Complete filename/order preflight and independent checksums pass. Shuffled creation uses seed 61938, process scheduling 61937; all per-fixture unsorted preflight hashes agree across labels/budgets. CPU6, warm tmpfs, shared host; no exclusive core or frequency isolation. No other heavy goose-fs job ran during timing. ASLR, execution paths, allocator history, temperature and other host work are uncontrolled. Build paths, versions, settings, fixture hashes, timestamps, host/load and all samples are retained in each JSON.

Reproduce at each measured tool revision using [the control commands](../../listing-control.md). Do not pool records or reinterpret these sample means as independent process replicates. Ratios below/above 1 simply reflect the ordering of the two measured medians.

## Observations

Median ns/call, A divided by B; neither label is an optimization.

| Case | Initial A | Initial B | A/B | Final A | Final B | A/B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| above 128k/1048576/absolute | 1,077,732 | 977,389 | 1.103 | 317,320 | 451,798 | 0.702 |
| above 128k/1048576/absolute-sorted | 1,634,823 | 1,211,063 | 1.350 | 352,232 | 483,808 | 0.728 |
| above 128k/1048576/root | 849,920 | 892,912 | 0.952 | 435,686 | 419,086 | 1.040 |
| above 128k/1048576/root-sorted | 1,139,357 | 1,041,006 | 1.094 | 387,502 | 519,402 | 0.746 |
| above 128k/131073/absolute | 367,588 | 371,759 | 0.989 | 326,424 | 283,455 | 1.152 |
| above 128k/131073/absolute-sorted | 978,755 | 386,679 | 2.531 | 384,000 | 467,193 | 0.822 |
| above 128k/131073/root | 545,548 | 600,369 | 0.909 | 360,011 | 298,191 | 1.207 |
| above 128k/131073/root-sorted | 706,862 | 860,908 | 0.821 | 412,638 | 335,704 | 1.229 |
| above512k/1048576/absolute | 4,576,567 | 4,560,346 | 1.004 | 1,975,815 | 1,937,322 | 1.020 |
| above512k/1048576/absolute-sorted | 5,492,294 | 4,824,698 | 1.138 | 4,138,643 | 2,425,364 | 1.706 |
| above512k/1048576/root | 4,389,445 | 4,502,065 | 0.975 | 1,986,432 | 1,931,061 | 1.029 |
| above512k/1048576/root-sorted | 6,787,837 | 5,356,840 | 1.267 | 2,372,369 | 2,289,886 | 1.036 |
| above512k/524289/absolute | 4,343,850 | 4,749,460 | 0.915 | 1,682,457 | 1,891,874 | 0.889 |
| above512k/524289/absolute-sorted | 6,946,488 | 4,916,497 | 1.413 | 2,328,646 | 2,100,517 | 1.109 |
| above512k/524289/root | 4,710,648 | 4,153,449 | 1.134 | 2,428,363 | 1,709,218 | 1.421 |
| above512k/524289/root-sorted | 6,789,753 | 5,423,618 | 1.252 | 2,444,499 | 2,321,837 | 1.053 |
| above64k/1048576/absolute | 237,552 | 306,722 | 0.774 | 202,986 | 209,396 | 0.969 |
| above64k/1048576/absolute-sorted | 299,231 | 394,328 | 0.759 | 205,286 | 215,493 | 0.953 |
| above64k/1048576/root | 279,794 | 320,198 | 0.874 | 196,469 | 191,712 | 1.025 |
| above64k/1048576/root-sorted | 549,045 | 273,037 | 2.011 | 226,745 | 293,377 | 0.773 |
| above64k/65537/absolute | 157,094 | 157,261 | 0.999 | 168,840 | 147,456 | 1.145 |
| above64k/65537/absolute-sorted | 192,601 | 191,115 | 1.008 | 173,417 | 182,331 | 0.951 |
| above64k/65537/root | 195,805 | 145,001 | 1.350 | 155,744 | 145,879 | 1.068 |
| above64k/65537/root-sorted | 193,523 | 209,959 | 0.922 | 189,955 | 177,955 | 1.067 |
| at64k/1048576/absolute | 255,834 | 269,892 | 0.948 | 235,666 | 192,745 | 1.223 |
| at64k/1048576/absolute-sorted | 342,129 | 325,961 | 1.050 | 243,151 | 241,242 | 1.008 |
| at64k/1048576/root | 221,421 | 273,169 | 0.811 | 197,268 | 195,687 | 1.008 |
| at64k/1048576/root-sorted | 256,211 | 255,722 | 1.002 | 207,803 | 270,825 | 0.767 |
| at64k/65536/absolute | 165,678 | 157,685 | 1.051 | 144,676 | 160,491 | 0.901 |
| at64k/65536/absolute-sorted | 201,056 | 184,822 | 1.088 | 188,012 | 169,097 | 1.112 |
| at64k/65536/root | 170,497 | 249,049 | 0.685 | 148,736 | 162,565 | 0.915 |
| at64k/65536/root-sorted | 165,818 | 222,292 | 0.746 | 164,779 | 169,061 | 0.975 |
| below64k/1048576/absolute | 234,051 | 255,854 | 0.915 | 205,301 | 185,585 | 1.106 |
| below64k/1048576/absolute-sorted | 413,585 | 327,647 | 1.262 | 290,814 | 216,852 | 1.341 |
| below64k/1048576/root | 287,070 | 231,410 | 1.241 | 214,081 | 204,362 | 1.048 |
| below64k/1048576/root-sorted | 267,308 | 345,107 | 0.775 | 209,350 | 209,180 | 1.001 |
| below64k/65535/absolute | 179,342 | 149,350 | 1.201 | 147,201 | 145,319 | 1.013 |
| below64k/65535/absolute-sorted | 197,910 | 211,534 | 0.936 | 160,590 | 170,144 | 0.944 |
| below64k/65535/root | 159,989 | 155,428 | 1.029 | 151,452 | 168,574 | 0.898 |
| below64k/65535/root-sorted | 191,219 | 178,401 | 1.072 | 164,791 | 214,566 | 0.768 |
| empty/0/absolute | 5,505 | 4,817 | 1.143 | 5,089 | 5,060 | 1.006 |
| empty/0/absolute-sorted | 4,892 | 4,921 | 0.994 | 5,198 | 4,981 | 1.044 |
| empty/0/root | 3,869 | 3,656 | 1.058 | 4,256 | 4,033 | 1.055 |
| empty/0/root-sorted | 4,074 | 3,917 | 1.040 | 4,129 | 4,521 | 0.913 |
| empty/1048576/absolute | 48,263 | 59,173 | 0.816 | 49,390 | 45,749 | 1.080 |
| empty/1048576/absolute-sorted | 46,749 | 48,031 | 0.973 | 44,936 | 55,178 | 0.814 |
| empty/1048576/root | 42,737 | 51,432 | 0.831 | 47,739 | 59,736 | 0.799 |
| empty/1048576/root-sorted | 47,887 | 59,440 | 0.806 | 48,735 | 47,662 | 1.023 |
| max1m/1048576/absolute | 9,684,505 | 9,765,614 | 0.992 | 4,269,418 | 4,248,512 | 1.005 |
| max1m/1048576/absolute-sorted | 15,062,521 | 14,264,210 | 1.056 | 5,174,583 | 5,419,030 | 0.955 |
| max1m/1048576/root | 9,236,096 | 9,320,381 | 0.991 | 4,521,794 | 4,263,804 | 1.061 |
| max1m/1048576/root-sorted | 11,383,494 | 11,479,387 | 0.992 | 5,247,035 | 5,247,286 | 1.000 |
| one/1048576/absolute | 54,467 | 57,033 | 0.955 | 66,925 | 50,789 | 1.318 |
| one/1048576/absolute-sorted | 59,353 | 46,199 | 1.285 | 56,379 | 60,832 | 0.927 |
| one/1048576/root | 46,590 | 45,860 | 1.016 | 53,174 | 45,800 | 1.161 |
| one/1048576/root-sorted | 46,396 | 61,045 | 0.760 | 42,225 | 46,705 | 0.904 |
| one/12/absolute | 4,922 | 5,352 | 0.920 | 5,374 | 5,903 | 0.910 |
| one/12/absolute-sorted | 4,859 | 5,222 | 0.930 | 5,558 | 5,201 | 1.069 |
| one/12/root | 4,002 | 4,299 | 0.931 | 4,690 | 4,271 | 1.098 |
| one/12/root-sorted | 4,253 | 4,439 | 0.958 | 4,318 | 4,389 | 0.984 |
| prefix255/1048560/absolute | 11,458,622 | 9,319,902 | 1.229 | 4,397,343 | 4,522,471 | 0.972 |
| prefix255/1048560/absolute-sorted | 12,009,113 | 12,283,982 | 0.978 | 5,958,839 | 5,679,324 | 1.049 |
| prefix255/1048560/root | 9,780,841 | 12,122,642 | 0.807 | 4,262,096 | 4,200,345 | 1.015 |
| prefix255/1048560/root-sorted | 12,709,684 | 12,291,136 | 1.034 | 5,762,377 | 5,429,223 | 1.061 |
| prefix255/1048576/absolute | 9,720,922 | 9,258,358 | 1.050 | 4,505,143 | 4,463,598 | 1.009 |
| prefix255/1048576/absolute-sorted | 12,068,628 | 14,819,348 | 0.814 | 5,981,790 | 5,815,688 | 1.029 |
| prefix255/1048576/root | 9,652,185 | 9,684,947 | 0.997 | 4,478,439 | 4,237,421 | 1.057 |
| prefix255/1048576/root-sorted | 12,686,332 | 16,696,628 | 0.760 | 5,893,785 | 5,782,937 | 1.019 |
| short4096/1048576/absolute | 5,379,532 | 5,511,669 | 0.976 | 2,019,546 | 2,066,909 | 0.977 |
| short4096/1048576/absolute-sorted | 7,356,546 | 7,056,763 | 1.042 | 2,809,845 | 2,868,778 | 0.979 |
| short4096/1048576/root | 6,448,661 | 5,455,902 | 1.182 | 2,058,622 | 1,834,026 | 1.122 |
| short4096/1048576/root-sorted | 8,995,336 | 7,122,902 | 1.263 | 3,059,962 | 2,677,379 | 1.143 |
| short4096/49152/absolute | 5,537,974 | 3,956,507 | 1.400 | 1,783,834 | 2,100,180 | 0.849 |
| short4096/49152/absolute-sorted | 6,101,293 | 6,412,304 | 0.951 | 2,778,538 | 2,807,001 | 0.990 |
| short4096/49152/root | 5,557,691 | 5,366,860 | 1.036 | 1,667,854 | 1,833,790 | 0.910 |
| short4096/49152/root-sorted | 8,219,962 | 6,489,756 | 1.267 | 2,591,622 | 2,621,165 | 0.989 |

## Validation

Independent security and quality/performance review found and resolved a template-snapshot race, optimized-Python assertion bypass, rebuild/recording lock overlap, and false-positive negative-test fixtures. Tests execute successful original/copied manifests before mutating eligibility/profile/source/binaries; optimized Python is rejected. Actual nonblocking exclusive lock acquisition failed while the recorder held its shared lock. The normal three-variant profile passed a 1,596-row compatibility smoke. Output publication now replaces artifact entries atomically; a symlink regression protects unrelated target bytes. No native/runtime source or ABI changed. CI exercises the control builder and integration tests in addition to the normal GCC/Clang matrix. Historical performance records remain intact.
