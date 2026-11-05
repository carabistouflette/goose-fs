# Matched-path baseline/candidate listing comparison

Clean measured harness `0034683dfc1e556cd303df80013f59e98f1ea605`; baseline **a1/a2** exports `3456547b8465b4b803ced6c5065fddd06e3a604f`, candidate **b1/b2** exports published `edd94ced1d7ae76490efb497794b9ba19504d4da`. No new runtime or native source change. [Raw data/provenance](raw.json) · [Interactive observations](comparison.html).

Two independently built replicas per revision use identical absolute export, harness, output, CWD and fresh GOOSE_HOME paths. The entire tree/cache is reset between builds, in order a1,b1,a2,b2. Each same-revision pair must match whole ELF and text/rodata hashes before recording. Cross-revision differences are allowed. Source maps, pins, four executable hashes, sections, paths, build settings/log digests, compiler and stdlib hashes are retained. Execution paths a1/a2/b1/b2 differ. Inputs are checked before/after recording; a shared lock excludes cooperating rebuilds. No host settings change.

In this run, all four baseline/candidate median ratios across the absolute/Root and exact/maximum-budget sorted cases span **1.322–1.563** for 4,096 short names and **4.037–4.908** for 4,080 long shared-prefix names. A cross-revision ratio above 1 means the candidate median is lower in that comparison. Same-revision control ratios across all cases span **0.824–1.212** for baseline a1/a2 and **0.858–1.343** for candidate b1/b2; those are identical-code differences, not speedups or noise bounds. All medians, all four cross ratios and both controls are shown below, without pooling or favorable-replica selection. Smaller/slower cases remain visible. This is an observation from one shared-host series, not a universal SOTA, isolation or causal conclusion. No old measurement is corrected or normalized, and no source/release/pin migration is inferred.

Five shuffled rounds × 76 workloads × 4 executables × 7 sample means = **10,640 rows**, five calls per mean. CPU6, warm tmpfs, shared Intel Core Ultra7 258V Linux host; GCC 16.2.1 -O2 and pinned Goose eadca409 inputs are recorded. No other heavy goose-fs job ran during this series. ASLR, allocator history, temperature/frequency and other host work are uncontrolled. Sample means within each process are not independent process replicates. Fixture creation shuffles with seed 61938 and job order uses 61937. Actual unsorted preflight hashes agree across variants/budgets within each fixture. Full filename/order validation precedes timing; timed checksums consume count, lengths and endpoint bytes. Both revisions use full staging, identical budgets, paths and public APIs; no adaptive staging confound. This is FS-versus-FS, not Rust/Go or equal-security adapter benchmarking.

## Median ns per call

| Case | Baseline a1 | Baseline a2 | Candidate b1 | Candidate b2 |
| --- | ---: | ---: | ---: | ---: |
| above 128k/1048576/absolute | 438,095 | 442,750 | 402,585 | 425,831 |
| above 128k/1048576/absolute-sorted | 616,732 | 508,988 | 481,609 | 483,196 |
| above 128k/1048576/root | 431,971 | 364,498 | 436,276 | 368,328 |
| above 128k/1048576/root-sorted | 550,885 | 577,005 | 528,184 | 393,239 |
| above 128k/131073/absolute | 279,669 | 274,012 | 279,141 | 307,250 |
| above 128k/131073/absolute-sorted | 440,271 | 459,558 | 406,984 | 406,552 |
| above 128k/131073/root | 282,833 | 278,630 | 283,488 | 288,605 |
| above 128k/131073/root-sorted | 467,212 | 458,051 | 403,020 | 354,620 |
| above512k/1048576/absolute | 1,787,964 | 1,780,388 | 1,829,645 | 1,753,038 |
| above512k/1048576/absolute-sorted | 2,747,665 | 2,651,305 | 2,161,126 | 2,201,273 |
| above512k/1048576/root | 1,913,666 | 1,796,338 | 1,837,306 | 1,787,045 |
| above512k/1048576/root-sorted | 2,607,101 | 2,699,161 | 2,217,104 | 2,247,858 |
| above512k/524289/absolute | 1,716,066 | 1,825,497 | 1,743,710 | 1,681,501 |
| above512k/524289/absolute-sorted | 2,586,240 | 2,495,908 | 2,100,215 | 2,160,455 |
| above512k/524289/root | 1,666,652 | 1,705,651 | 1,808,669 | 1,796,661 |
| above512k/524289/root-sorted | 2,586,062 | 2,655,467 | 2,061,129 | 2,131,189 |
| above64k/1048576/absolute | 196,844 | 218,977 | 207,575 | 213,251 |
| above64k/1048576/absolute-sorted | 241,994 | 267,926 | 206,714 | 215,987 |
| above64k/1048576/root | 215,940 | 209,297 | 244,441 | 195,899 |
| above64k/1048576/root-sorted | 289,045 | 243,502 | 246,414 | 271,280 |
| above64k/65537/absolute | 146,245 | 152,345 | 142,467 | 146,603 |
| above64k/65537/absolute-sorted | 205,450 | 199,796 | 175,449 | 185,192 |
| above64k/65537/root | 155,812 | 160,763 | 146,452 | 150,659 |
| above64k/65537/root-sorted | 187,727 | 199,675 | 177,443 | 168,139 |
| at64k/1048576/absolute | 234,636 | 196,399 | 231,746 | 212,403 |
| at64k/1048576/absolute-sorted | 266,768 | 232,694 | 275,844 | 207,414 |
| at64k/1048576/root | 199,590 | 184,624 | 213,854 | 206,415 |
| at64k/1048576/root-sorted | 277,971 | 263,775 | 212,587 | 225,495 |
| at64k/65536/absolute | 136,646 | 159,729 | 147,721 | 145,525 |
| at64k/65536/absolute-sorted | 189,719 | 188,582 | 183,139 | 168,889 |
| at64k/65536/root | 164,822 | 152,863 | 147,152 | 147,361 |
| at64k/65536/root-sorted | 195,036 | 183,814 | 183,421 | 193,919 |
| below64k/1048576/absolute | 201,077 | 206,645 | 185,844 | 198,742 |
| below64k/1048576/absolute-sorted | 269,861 | 247,519 | 249,158 | 248,505 |
| below64k/1048576/root | 218,238 | 196,169 | 240,680 | 231,577 |
| below64k/1048576/root-sorted | 260,692 | 250,433 | 232,926 | 253,866 |
| below64k/65535/absolute | 152,700 | 153,043 | 151,079 | 149,967 |
| below64k/65535/absolute-sorted | 188,947 | 185,684 | 169,165 | 172,400 |
| below64k/65535/root | 146,750 | 146,179 | 140,113 | 143,091 |
| below64k/65535/root-sorted | 187,736 | 199,873 | 188,024 | 168,370 |
| empty/0/absolute | 4,946 | 4,898 | 5,106 | 5,268 |
| empty/0/absolute-sorted | 5,213 | 5,285 | 5,146 | 5,255 |
| empty/0/root | 4,242 | 4,212 | 4,275 | 4,534 |
| empty/0/root-sorted | 4,107 | 4,506 | 4,586 | 4,282 |
| empty/1048576/absolute | 50,901 | 48,093 | 49,120 | 54,667 |
| empty/1048576/absolute-sorted | 44,113 | 53,554 | 47,271 | 55,063 |
| empty/1048576/root | 48,690 | 48,734 | 49,397 | 55,558 |
| empty/1048576/root-sorted | 50,098 | 52,708 | 45,845 | 48,098 |
| max1m/1048576/absolute | 3,973,391 | 3,867,837 | 3,840,585 | 4,143,939 |
| max1m/1048576/absolute-sorted | 5,943,842 | 6,072,321 | 4,518,161 | 4,624,369 |
| max1m/1048576/root | 3,911,141 | 3,731,675 | 4,021,364 | 4,016,558 |
| max1m/1048576/root-sorted | 6,157,986 | 6,004,551 | 4,867,632 | 4,694,827 |
| one/1048576/absolute | 48,535 | 49,335 | 46,887 | 48,389 |
| one/1048576/absolute-sorted | 49,966 | 46,450 | 48,174 | 46,716 |
| one/1048576/root | 46,209 | 53,137 | 47,460 | 47,975 |
| one/1048576/root-sorted | 50,991 | 53,636 | 57,966 | 44,776 |
| one/12/absolute | 5,130 | 5,338 | 5,453 | 5,329 |
| one/12/absolute-sorted | 5,220 | 5,656 | 5,513 | 5,658 |
| one/12/root | 4,157 | 4,331 | 4,556 | 4,465 |
| one/12/root-sorted | 4,461 | 4,507 | 4,710 | 4,461 |
| prefix255/1048560/absolute | 3,745,068 | 3,936,686 | 3,933,863 | 4,165,484 |
| prefix255/1048560/absolute-sorted | 22,500,841 | 24,515,422 | 5,252,122 | 5,517,281 |
| prefix255/1048560/root | 3,933,753 | 3,880,012 | 3,982,370 | 3,866,758 |
| prefix255/1048560/root-sorted | 24,689,062 | 25,809,790 | 5,259,197 | 5,570,888 |
| prefix255/1048576/absolute | 3,996,000 | 4,025,169 | 4,080,111 | 4,165,358 |
| prefix255/1048576/absolute-sorted | 22,622,878 | 25,779,175 | 5,298,358 | 5,603,618 |
| prefix255/1048576/root | 4,144,909 | 4,178,997 | 4,089,427 | 3,834,714 |
| prefix255/1048576/root-sorted | 24,292,232 | 25,311,681 | 5,446,621 | 5,209,026 |
| short4096/1048576/absolute | 1,849,299 | 1,694,793 | 1,820,476 | 1,997,849 |
| short4096/1048576/absolute-sorted | 3,686,950 | 3,545,874 | 2,595,261 | 2,662,706 |
| short4096/1048576/root | 1,839,888 | 1,759,972 | 1,762,506 | 1,831,707 |
| short4096/1048576/root-sorted | 3,817,850 | 3,550,603 | 2,569,873 | 2,685,682 |
| short4096/49152/absolute | 1,645,371 | 1,653,055 | 1,493,957 | 1,607,090 |
| short4096/49152/absolute-sorted | 3,486,629 | 3,275,214 | 2,337,986 | 2,230,561 |
| short4096/49152/root | 1,543,912 | 1,588,487 | 1,441,661 | 1,511,865 |
| short4096/49152/root-sorted | 3,278,113 | 3,337,242 | 2,379,633 | 2,369,292 |

## Ratios — no pooling or correction

First four columns divide baseline by candidate. Last two divide replicas of the same revision and are controls, not speedups.

| Case | a1/b1 | a1/b2 | a2/b1 | a2/b2 | Control a1/a2 | Control b1/b2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| above 128k/1048576/absolute | 1.088 | 1.029 | 1.100 | 1.040 | 0.989 | 0.945 |
| above 128k/1048576/absolute-sorted | 1.281 | 1.276 | 1.057 | 1.053 | 1.212 | 0.997 |
| above 128k/1048576/root | 0.990 | 1.173 | 0.835 | 0.990 | 1.185 | 1.184 |
| above 128k/1048576/root-sorted | 1.043 | 1.401 | 1.092 | 1.467 | 0.955 | 1.343 |
| above 128k/131073/absolute | 1.002 | 0.910 | 0.982 | 0.892 | 1.021 | 0.909 |
| above 128k/131073/absolute-sorted | 1.082 | 1.083 | 1.129 | 1.130 | 0.958 | 1.001 |
| above 128k/131073/root | 0.998 | 0.980 | 0.983 | 0.965 | 1.015 | 0.982 |
| above 128k/131073/root-sorted | 1.159 | 1.318 | 1.137 | 1.292 | 1.020 | 1.136 |
| above512k/1048576/absolute | 0.977 | 1.020 | 0.973 | 1.016 | 1.004 | 1.044 |
| above512k/1048576/absolute-sorted | 1.271 | 1.248 | 1.227 | 1.204 | 1.036 | 0.982 |
| above512k/1048576/root | 1.042 | 1.071 | 0.978 | 1.005 | 1.065 | 1.028 |
| above512k/1048576/root-sorted | 1.176 | 1.160 | 1.217 | 1.201 | 0.966 | 0.986 |
| above512k/524289/absolute | 0.984 | 1.021 | 1.047 | 1.086 | 0.940 | 1.037 |
| above512k/524289/absolute-sorted | 1.231 | 1.197 | 1.188 | 1.155 | 1.036 | 0.972 |
| above512k/524289/root | 0.921 | 0.928 | 0.943 | 0.949 | 0.977 | 1.007 |
| above512k/524289/root-sorted | 1.255 | 1.213 | 1.288 | 1.246 | 0.974 | 0.967 |
| above64k/1048576/absolute | 0.948 | 0.923 | 1.055 | 1.027 | 0.899 | 0.973 |
| above64k/1048576/absolute-sorted | 1.171 | 1.120 | 1.296 | 1.240 | 0.903 | 0.957 |
| above64k/1048576/root | 0.883 | 1.102 | 0.856 | 1.068 | 1.032 | 1.248 |
| above64k/1048576/root-sorted | 1.173 | 1.065 | 0.988 | 0.898 | 1.187 | 0.908 |
| above64k/65537/absolute | 1.027 | 0.998 | 1.069 | 1.039 | 0.960 | 0.972 |
| above64k/65537/absolute-sorted | 1.171 | 1.109 | 1.139 | 1.079 | 1.028 | 0.947 |
| above64k/65537/root | 1.064 | 1.034 | 1.098 | 1.067 | 0.969 | 0.972 |
| above64k/65537/root-sorted | 1.058 | 1.116 | 1.125 | 1.188 | 0.940 | 1.055 |
| at64k/1048576/absolute | 1.012 | 1.105 | 0.847 | 0.925 | 1.195 | 1.091 |
| at64k/1048576/absolute-sorted | 0.967 | 1.286 | 0.844 | 1.122 | 1.146 | 1.330 |
| at64k/1048576/root | 0.933 | 0.967 | 0.863 | 0.894 | 1.081 | 1.036 |
| at64k/1048576/root-sorted | 1.308 | 1.233 | 1.241 | 1.170 | 1.054 | 0.943 |
| at64k/65536/absolute | 0.925 | 0.939 | 1.081 | 1.098 | 0.855 | 1.015 |
| at64k/65536/absolute-sorted | 1.036 | 1.123 | 1.030 | 1.117 | 1.006 | 1.084 |
| at64k/65536/root | 1.120 | 1.118 | 1.039 | 1.037 | 1.078 | 0.999 |
| at64k/65536/root-sorted | 1.063 | 1.006 | 1.002 | 0.948 | 1.061 | 0.946 |
| below64k/1048576/absolute | 1.082 | 1.012 | 1.112 | 1.040 | 0.973 | 0.935 |
| below64k/1048576/absolute-sorted | 1.083 | 1.086 | 0.993 | 0.996 | 1.090 | 1.003 |
| below64k/1048576/root | 0.907 | 0.942 | 0.815 | 0.847 | 1.112 | 1.039 |
| below64k/1048576/root-sorted | 1.119 | 1.027 | 1.075 | 0.986 | 1.041 | 0.918 |
| below64k/65535/absolute | 1.011 | 1.018 | 1.013 | 1.021 | 0.998 | 1.007 |
| below64k/65535/absolute-sorted | 1.117 | 1.096 | 1.098 | 1.077 | 1.018 | 0.981 |
| below64k/65535/root | 1.047 | 1.026 | 1.043 | 1.022 | 1.004 | 0.979 |
| below64k/65535/root-sorted | 0.998 | 1.115 | 1.063 | 1.187 | 0.939 | 1.117 |
| empty/0/absolute | 0.969 | 0.939 | 0.959 | 0.930 | 1.010 | 0.969 |
| empty/0/absolute-sorted | 1.013 | 0.992 | 1.027 | 1.006 | 0.986 | 0.979 |
| empty/0/root | 0.992 | 0.936 | 0.985 | 0.929 | 1.007 | 0.943 |
| empty/0/root-sorted | 0.896 | 0.959 | 0.983 | 1.052 | 0.911 | 1.071 |
| empty/1048576/absolute | 1.036 | 0.931 | 0.979 | 0.880 | 1.058 | 0.899 |
| empty/1048576/absolute-sorted | 0.933 | 0.801 | 1.133 | 0.973 | 0.824 | 0.858 |
| empty/1048576/root | 0.986 | 0.876 | 0.987 | 0.877 | 0.999 | 0.889 |
| empty/1048576/root-sorted | 1.093 | 1.042 | 1.150 | 1.096 | 0.950 | 0.953 |
| max1m/1048576/absolute | 1.035 | 0.959 | 1.007 | 0.933 | 1.027 | 0.927 |
| max1m/1048576/absolute-sorted | 1.316 | 1.285 | 1.344 | 1.313 | 0.979 | 0.977 |
| max1m/1048576/root | 0.973 | 0.974 | 0.928 | 0.929 | 1.048 | 1.001 |
| max1m/1048576/root-sorted | 1.265 | 1.312 | 1.234 | 1.279 | 1.026 | 1.037 |
| one/1048576/absolute | 1.035 | 1.003 | 1.052 | 1.020 | 0.984 | 0.969 |
| one/1048576/absolute-sorted | 1.037 | 1.070 | 0.964 | 0.994 | 1.076 | 1.031 |
| one/1048576/root | 0.974 | 0.963 | 1.120 | 1.108 | 0.870 | 0.989 |
| one/1048576/root-sorted | 0.880 | 1.139 | 0.925 | 1.198 | 0.951 | 1.295 |
| one/12/absolute | 0.941 | 0.963 | 0.979 | 1.002 | 0.961 | 1.023 |
| one/12/absolute-sorted | 0.947 | 0.923 | 1.026 | 1.000 | 0.923 | 0.974 |
| one/12/root | 0.912 | 0.931 | 0.951 | 0.970 | 0.960 | 1.020 |
| one/12/root-sorted | 0.947 | 1.000 | 0.957 | 1.010 | 0.990 | 1.056 |
| prefix255/1048560/absolute | 0.952 | 0.899 | 1.001 | 0.945 | 0.951 | 0.944 |
| prefix255/1048560/absolute-sorted | 4.284 | 4.078 | 4.668 | 4.443 | 0.918 | 0.952 |
| prefix255/1048560/root | 0.988 | 1.017 | 0.974 | 1.003 | 1.014 | 1.030 |
| prefix255/1048560/root-sorted | 4.694 | 4.432 | 4.908 | 4.633 | 0.957 | 0.944 |
| prefix255/1048576/absolute | 0.979 | 0.959 | 0.987 | 0.966 | 0.993 | 0.980 |
| prefix255/1048576/absolute-sorted | 4.270 | 4.037 | 4.866 | 4.600 | 0.878 | 0.946 |
| prefix255/1048576/root | 1.014 | 1.081 | 1.022 | 1.090 | 0.992 | 1.066 |
| prefix255/1048576/root-sorted | 4.460 | 4.663 | 4.647 | 4.859 | 0.960 | 1.046 |
| short4096/1048576/absolute | 1.016 | 0.926 | 0.931 | 0.848 | 1.091 | 0.911 |
| short4096/1048576/absolute-sorted | 1.421 | 1.385 | 1.366 | 1.332 | 1.040 | 0.975 |
| short4096/1048576/root | 1.044 | 1.004 | 0.999 | 0.961 | 1.045 | 0.962 |
| short4096/1048576/root-sorted | 1.486 | 1.422 | 1.382 | 1.322 | 1.075 | 0.957 |
| short4096/49152/absolute | 1.101 | 1.024 | 1.106 | 1.029 | 0.995 | 0.930 |
| short4096/49152/absolute-sorted | 1.491 | 1.563 | 1.401 | 1.468 | 1.065 | 1.048 |
| short4096/49152/root | 1.071 | 1.021 | 1.102 | 1.051 | 0.972 | 0.954 |
| short4096/49152/root-sorted | 1.378 | 1.384 | 1.402 | 1.409 | 0.982 | 1.004 |

## Reproduction and checks

Check out the measured harness revision and the recorded compiler/toolchain, then follow [the matched profile commands](../../listing-control.md) with the exact baseline/candidate pins above. Use `--matched-comparison --creation-order shuffled --rounds 5 --iterations 5`; saved labels must be a1,b1,a2,b2 beside their manifest. The raw record binds every measured input. Output creation is exclusive. Older [A/A controls](../2026-11-05-listing-control/README.md) and original [listing results](../2026-11-05-sorted-listing/README.md) remain unchanged.

Independent security and quality/performance implementation review passed. Successful same-source and distinct-source four-label smoke records each passed 2,128 rows before this series. Wrong candidate pins, missing/swapped revision labels, profile mixing, modified a2/b2, symlinked replicas, false identity flags and mismatched replica sections are rejected with otherwise valid copied fixtures. Existing A/A recording and rejection/symlink/alias tests pass. CI exercises the four-label profile using one source revision in both roles, making no timing claim. Native/runtime source and ABI are unchanged; no acceptance or rollback of the published optimization follows automatically from this run. Future performance claims need their own measured comparison.
