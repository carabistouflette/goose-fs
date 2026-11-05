# Sorted listing performance — 2026-11-05

Initial natural-creation and native API measured clean source: `efa585c05eeb84151aed1d1cf5cf68532da0257d`; production change: `8195b5d706b282950c8f41076a540dd7e2627610`; published baseline: `3456547b8465b4b803ced6c5065fddd06e3a604f`.

[Natural-creation raw results/provenance](paired.json) · [Shuffled-creation raw results/provenance](paired-shuffled.json) · [Four-library raw results/provenance](native-api.json) · [Interactive chart](comparison.html).

The initial paired run uses natural name-creation order and compares the old full-staging implementation, current full staging, and current opt-in adaptive staging. On the same full-staging policy, 4,096 short-name sorted listings improve **1.59–1.90×**, and 4,080 long shared-prefix names improve **4.07–4.90×**, across absolute/Root and exact/maximum budgets. Empty/single-entry sorted results do not establish a win: median speed ratios span 0.869–1.062×. Unsorted controls span 0.830–1.295× with unchanged operation code; host noise and binary-layout effects were not isolated. A ratio below 1 means the candidate is slower. Every cell, including regressions, is retained below.

The added shuffled-creation series measured clean benchmark source `d81bafa8255990d0244cea1f571717c41cfccf81`, with byte-identical library sources and the same compiler/stdlib inputs. Same-policy improvements are **1.21–1.76×** for 4,096 short names and **3.47–3.70×** for long shared-prefix names. Its empty/single sorted speed ratios span 0.820–1.175×; unsorted controls span 0.859–1.625×. All data from the initial run remains intact. Across both paired runs and the native API run, **20,720 raw rows** are retained.

In the separate four-library native API run, sorted 4,096-name listing takes goose-fs 2,266,564 ns, Goose stdlib 2,859,321 ns, Rust 2,655,530 ns and Go 4,335,837 ns. goose-fs is about **1.26×/1.17×/1.91× as fast** respectively for that task in this run. Small listings remain slower than Goose/Rust; the 128-name absolute row remains slower than Rust. These APIs have different safety/output contracts. This is not a universal state-of-the-art, equal-security, full-parity or regression-free claim. Hardened-adapter comparisons remain outstanding.

## Change and measurement

An initial user-space cycle profile of the baseline's 4,096 short-name sorted case attributed about 77% of sampled cycles to the custom heapsort. The final code reuses the pinned Goose standard sort, including its depth-limited heapsort fallback, and replaces scalar name comparison with a small libc memcmp wrapper. The wrapper skips zero-length reads, checks malformed lengths/null slices, compares unsigned bytes, and uses length for prefix ties. A private pointer-sized carrier prevents ordinary consumer overloads on public Entry references from intercepting the standard algorithm. The production hot path contains fewer library-maintained lines than the baseline.

Native enumeration, bounds, symlink policy, error clearing, cleanup, staging defaults and result ownership remain unchanged. The final implementation still owns temporary unsorted names and copies names into the sorted result; it makes no copy-count, allocation-free or lower-peak-memory claim. A scalar-loop alternative and a borrowed-view/single-copy prototype were tried diagnostically and rejected after mixed results or regressions; neither is part of this measured source.

All three final series ran sequentially on CPU6, warm tmpfs, shared Intel Core Ultra7 258V Linux host, GCC 16.2.1 -O2 and the pinned Goose compiler eadca409. The pinned Rust 1.99.1 and installed Go 1.27.3-X:nodwarf5 versions/settings are recorded in raw data. No other heavy goose-fs job ran during any final series; other projects and host load were not excluded. There is no exclusive-core or frequency-isolation claim. UTC timestamps are in the raw files (the runs fall on November 5 in Paris).

The paired series has five shuffled rounds × 76 workloads × 3 variants × 7 sample means = **7,980 rows**, five calls per sample mean. Complete independent filename/order checks precede timing. Timed checksums consume counts, lengths and endpoint bytes. Existing 68 cases are preserved; eight new cases use 4,080 unique 255-byte names with 250 shared prefix bytes, totaling 1,048,560 packed bytes, 16 below MAX. Full/adaptive staging stays distinct. Adaptive large results can need another enumeration and remain slower than full staging; the sorting change does not remove that tradeoff.

Natural fixtures create names in deterministic byte order; filesystem enumeration order can differ. Standard sort can benefit from existing runs. The extra paired series instead shuffles file creation with separate seed 61938, keeping process shuffle 61937 unchanged. It records creation-order hashes and actual unsorted preflight output hashes; all variants/budgets for each fixture observed the same unsorted preflight order. This establishes matching preflight inputs within that run, not a filesystem ordering guarantee. Separate runs do not isolate ordering from host effects. The native API suite also shuffles creation order with its recorded seed.

The native API series has five shuffled process rounds × 34 tasks × 4 runners × 7 sample means = **4,760 rows**, including 1,015 unsupported, 200 iterations per mean. FS listings explicitly select adaptive staging. Owned-name/output work differs across runners; the pinned Goose list API uses sorted newline names and cannot represent arbitrary filenames. These common fixtures are ASCII. All existing read, metadata, locking, Root, rename and setter tasks remain visible. Rename rows are ns per pair of two operations; other rows are ns/call. Goose basic rename always requests best-effort destination-parent sync, while other basic rows request none. Checked compositions and Root lookup/error contracts also differ. See [all native API policies](../../compare/README.md).

Both builders/runners verify source, executable, compiler and selected standard-library hashes before/after measurement. The new provenance records all 15 Goose standard-library source files, not only the compiler executable, and forces the resolved directory during builds. This binds the harnesses' std/os imports; it is not a general compiler import-resolution manifest. The selected compiler checkout and stdlib were clean at the pinned revision. Fixture hashes, flags, runtime settings, CPU affinity/load and raw process order are retained. Whole-process VmHWM in the native profile includes setup, registry initialization, validation, allocator/GC history and retained sinks; it is not per-operation memory or allocations.

## Paired results — natural creation

Median sample means, ns/call. Speed ratio is old-full/current-full, comparing the same staging policy. Current adaptive is a separate option, not the default.

| Workload: fixture/budget/API | Old full ns | Current full ns | Current adaptive ns | Full-policy speed ratio |
| --- | ---: | ---: | ---: | ---: |
| above128k/1048576/absolute | 300,857 | 299,501 | 417,824 | 1.005× |
| above128k/1048576/absolute-sorted | 400,348 | 355,260 | 542,582 | 1.127× |
| above128k/1048576/root | 349,085 | 321,519 | 439,923 | 1.086× |
| above128k/1048576/root-sorted | 433,145 | 337,443 | 447,742 | 1.284× |
| above128k/131073/absolute | 269,941 | 299,519 | 439,772 | 0.901× |
| above128k/131073/absolute-sorted | 382,677 | 319,085 | 501,337 | 1.199× |
| above128k/131073/root | 263,807 | 278,262 | 461,897 | 0.948× |
| above128k/131073/root-sorted | 397,552 | 364,047 | 450,690 | 1.092× |
| above512k/1048576/absolute | 1,736,597 | 1,684,490 | 2,338,830 | 1.031× |
| above512k/1048576/absolute-sorted | 2,512,306 | 1,930,390 | 2,924,296 | 1.301× |
| above512k/1048576/root | 1,757,878 | 1,690,518 | 2,482,502 | 1.040× |
| above512k/1048576/root-sorted | 2,364,037 | 1,954,778 | 2,917,926 | 1.209× |
| above512k/524289/absolute | 1,671,378 | 1,615,521 | 2,561,716 | 1.035× |
| above512k/524289/absolute-sorted | 2,385,352 | 1,761,285 | 2,872,485 | 1.354× |
| above512k/524289/root | 1,635,277 | 1,670,066 | 2,289,931 | 0.979× |
| above512k/524289/root-sorted | 2,409,728 | 1,718,147 | 2,825,637 | 1.403× |
| above64k/1048576/absolute | 196,430 | 202,640 | 237,353 | 0.969× |
| above64k/1048576/absolute-sorted | 259,841 | 188,885 | 232,766 | 1.376× |
| above64k/1048576/root | 184,157 | 184,847 | 254,528 | 0.996× |
| above64k/1048576/root-sorted | 231,751 | 195,570 | 222,387 | 1.185× |
| above64k/65537/absolute | 142,363 | 156,380 | 226,279 | 0.910× |
| above64k/65537/absolute-sorted | 169,610 | 149,128 | 243,065 | 1.137× |
| above64k/65537/root | 145,120 | 136,949 | 224,679 | 1.060× |
| above64k/65537/root-sorted | 181,312 | 146,875 | 234,717 | 1.234× |
| at64k/1048576/absolute | 188,818 | 185,238 | 136,133 | 1.019× |
| at64k/1048576/absolute-sorted | 217,242 | 180,763 | 143,989 | 1.202× |
| at64k/1048576/root | 179,772 | 162,550 | 141,455 | 1.106× |
| at64k/1048576/root-sorted | 221,791 | 199,758 | 142,700 | 1.110× |
| at64k/65536/absolute | 134,506 | 140,773 | 142,037 | 0.955× |
| at64k/65536/absolute-sorted | 180,405 | 155,641 | 180,496 | 1.159× |
| at64k/65536/root | 142,065 | 137,944 | 138,097 | 1.030× |
| at64k/65536/root-sorted | 187,583 | 142,195 | 148,383 | 1.319× |
| below64k/1048576/absolute | 175,362 | 186,536 | 140,727 | 0.940× |
| below64k/1048576/absolute-sorted | 251,359 | 196,210 | 147,674 | 1.281× |
| below64k/1048576/root | 177,595 | 188,971 | 142,615 | 0.940× |
| below64k/1048576/root-sorted | 216,227 | 210,177 | 157,495 | 1.029× |
| below64k/65535/absolute | 137,509 | 134,457 | 136,300 | 1.023× |
| below64k/65535/absolute-sorted | 176,311 | 147,183 | 135,702 | 1.198× |
| below64k/65535/root | 143,133 | 139,147 | 127,459 | 1.029× |
| below64k/65535/root-sorted | 185,880 | 151,088 | 147,822 | 1.230× |
| empty/0/absolute | 4,867 | 4,710 | 4,772 | 1.033× |
| empty/0/absolute-sorted | 4,996 | 5,192 | 4,943 | 0.962× |
| empty/0/root | 4,199 | 4,062 | 4,069 | 1.034× |
| empty/0/root-sorted | 4,293 | 4,209 | 4,105 | 1.020× |
| empty/1048576/absolute | 45,452 | 44,115 | 7,902 | 1.030× |
| empty/1048576/absolute-sorted | 41,907 | 48,241 | 7,312 | 0.869× |
| empty/1048576/root | 43,292 | 43,149 | 6,800 | 1.003× |
| empty/1048576/root-sorted | 43,272 | 43,158 | 6,759 | 1.003× |
| max1m/1048576/absolute | 3,804,226 | 3,795,267 | 6,683,945 | 1.002× |
| max1m/1048576/absolute-sorted | 5,499,536 | 4,481,032 | 6,936,084 | 1.227× |
| max1m/1048576/root | 3,948,524 | 4,057,741 | 6,935,707 | 0.973× |
| max1m/1048576/root-sorted | 5,595,137 | 4,437,272 | 7,199,272 | 1.261× |
| one/1048576/absolute | 39,022 | 47,035 | 7,948 | 0.830× |
| one/1048576/absolute-sorted | 44,489 | 45,453 | 7,655 | 0.979× |
| one/1048576/root | 48,003 | 37,078 | 7,058 | 1.295× |
| one/1048576/root-sorted | 43,583 | 41,027 | 6,909 | 1.062× |
| one/12/absolute | 5,354 | 4,908 | 4,925 | 1.091× |
| one/12/absolute-sorted | 5,027 | 4,924 | 5,270 | 1.021× |
| one/12/root | 4,313 | 4,189 | 4,319 | 1.030× |
| one/12/root-sorted | 4,235 | 4,278 | 4,469 | 0.990× |
| prefix255/1048560/absolute | 4,008,189 | 4,198,532 | 7,137,535 | 0.955× |
| prefix255/1048560/absolute-sorted | 20,208,530 | 4,487,968 | 7,359,398 | 4.503× |
| prefix255/1048560/root | 3,800,453 | 3,987,709 | 7,221,685 | 0.953× |
| prefix255/1048560/root-sorted | 18,791,316 | 4,621,158 | 7,337,208 | 4.066× |
| prefix255/1048576/absolute | 4,064,104 | 4,050,979 | 7,246,060 | 1.003× |
| prefix255/1048576/absolute-sorted | 19,467,845 | 3,973,703 | 7,217,615 | 4.899× |
| prefix255/1048576/root | 4,154,729 | 3,865,955 | 6,789,682 | 1.075× |
| prefix255/1048576/root-sorted | 19,478,573 | 4,694,314 | 7,519,636 | 4.149× |
| short4096/1048576/absolute | 1,914,425 | 1,753,681 | 1,392,396 | 1.092× |
| short4096/1048576/absolute-sorted | 3,195,872 | 1,870,771 | 1,459,483 | 1.708× |
| short4096/1048576/root | 1,725,463 | 1,788,493 | 1,478,943 | 0.965× |
| short4096/1048576/root-sorted | 3,121,779 | 1,959,470 | 1,574,438 | 1.593× |
| short4096/49152/absolute | 1,648,305 | 1,464,129 | 1,357,896 | 1.126× |
| short4096/49152/absolute-sorted | 3,061,161 | 1,614,168 | 1,550,406 | 1.896× |
| short4096/49152/root | 1,630,579 | 1,542,767 | 1,511,850 | 1.057× |
| short4096/49152/root-sorted | 2,244,829 | 1,411,634 | 1,618,609 | 1.590× |

## Paired results — shuffled creation

Same library implementation and staging policies; separately recorded run. Median ns/call and old-full/current-full ratio. See paired-shuffled.json for all hashes and raw samples.

| Workload: fixture/budget/API | Old full ns | Current full ns | Current adaptive ns | Full-policy speed ratio |
| --- | ---: | ---: | ---: | ---: |
| above128k/1048576/absolute | 493,327 | 303,654 | 392,926 | 1.625× |
| above128k/1048576/absolute-sorted | 387,764 | 372,652 | 581,149 | 1.041× |
| above128k/1048576/root | 336,149 | 292,558 | 388,746 | 1.149× |
| above128k/1048576/root-sorted | 430,576 | 363,869 | 478,366 | 1.183× |
| above128k/131073/absolute | 248,769 | 266,271 | 439,945 | 0.934× |
| above128k/131073/absolute-sorted | 386,204 | 300,247 | 486,716 | 1.286× |
| above128k/131073/root | 269,049 | 262,721 | 435,281 | 1.024× |
| above128k/131073/root-sorted | 342,243 | 299,955 | 433,157 | 1.141× |
| above512k/1048576/absolute | 1,526,618 | 1,604,970 | 2,299,763 | 0.951× |
| above512k/1048576/absolute-sorted | 2,474,766 | 1,837,048 | 2,757,487 | 1.347× |
| above512k/1048576/root | 1,763,285 | 1,612,125 | 2,750,033 | 1.094× |
| above512k/1048576/root-sorted | 2,510,513 | 1,938,307 | 2,764,597 | 1.295× |
| above512k/524289/absolute | 1,248,892 | 1,453,954 | 2,112,560 | 0.859× |
| above512k/524289/absolute-sorted | 2,488,666 | 1,776,361 | 2,586,659 | 1.401× |
| above512k/524289/root | 1,360,991 | 1,406,026 | 1,668,407 | 0.968× |
| above512k/524289/root-sorted | 2,375,154 | 2,090,086 | 2,612,818 | 1.136× |
| above64k/1048576/absolute | 167,986 | 160,978 | 213,676 | 1.044× |
| above64k/1048576/absolute-sorted | 225,330 | 177,503 | 249,673 | 1.269× |
| above64k/1048576/root | 169,194 | 169,876 | 209,326 | 0.996× |
| above64k/1048576/root-sorted | 220,178 | 209,953 | 233,515 | 1.049× |
| above64k/65537/absolute | 136,108 | 122,792 | 209,314 | 1.108× |
| above64k/65537/absolute-sorted | 172,937 | 145,885 | 255,205 | 1.185× |
| above64k/65537/root | 133,904 | 135,228 | 197,634 | 0.990× |
| above64k/65537/root-sorted | 199,605 | 148,031 | 241,196 | 1.348× |
| at64k/1048576/absolute | 182,578 | 169,445 | 138,057 | 1.078× |
| at64k/1048576/absolute-sorted | 223,227 | 196,839 | 148,762 | 1.134× |
| at64k/1048576/root | 170,514 | 169,127 | 136,045 | 1.008× |
| at64k/1048576/root-sorted | 216,296 | 185,174 | 148,383 | 1.168× |
| at64k/65536/absolute | 127,561 | 129,964 | 135,664 | 0.982× |
| at64k/65536/absolute-sorted | 167,765 | 150,054 | 146,194 | 1.118× |
| at64k/65536/root | 135,632 | 138,905 | 121,722 | 0.976× |
| at64k/65536/root-sorted | 186,140 | 149,835 | 157,244 | 1.242× |
| below64k/1048576/absolute | 164,078 | 163,677 | 130,249 | 1.002× |
| below64k/1048576/absolute-sorted | 208,376 | 193,573 | 179,497 | 1.076× |
| below64k/1048576/root | 176,888 | 181,927 | 139,677 | 0.972× |
| below64k/1048576/root-sorted | 185,377 | 182,828 | 157,159 | 1.014× |
| below64k/65535/absolute | 134,764 | 125,846 | 136,958 | 1.071× |
| below64k/65535/absolute-sorted | 177,481 | 149,660 | 154,260 | 1.186× |
| below64k/65535/root | 133,876 | 134,168 | 142,406 | 0.998× |
| below64k/65535/root-sorted | 174,355 | 148,496 | 138,772 | 1.174× |
| empty/0/absolute | 4,472 | 4,556 | 4,615 | 0.982× |
| empty/0/absolute-sorted | 4,651 | 4,633 | 4,852 | 1.004× |
| empty/0/root | 3,862 | 3,657 | 3,791 | 1.056× |
| empty/0/root-sorted | 3,765 | 4,135 | 3,642 | 0.911× |
| empty/1048576/absolute | 38,969 | 44,389 | 7,588 | 0.878× |
| empty/1048576/absolute-sorted | 39,651 | 46,178 | 6,944 | 0.859× |
| empty/1048576/root | 40,580 | 40,820 | 6,209 | 0.994× |
| empty/1048576/root-sorted | 39,992 | 40,838 | 6,246 | 0.979× |
| max1m/1048576/absolute | 4,014,478 | 3,998,015 | 6,539,343 | 1.004× |
| max1m/1048576/absolute-sorted | 5,807,269 | 4,548,970 | 7,314,632 | 1.277× |
| max1m/1048576/root | 3,770,842 | 4,022,285 | 6,587,811 | 0.937× |
| max1m/1048576/root-sorted | 5,675,387 | 4,484,741 | 7,708,135 | 1.265× |
| one/1048576/absolute | 42,046 | 41,645 | 7,494 | 1.010× |
| one/1048576/absolute-sorted | 49,285 | 41,933 | 7,415 | 1.175× |
| one/1048576/root | 40,087 | 36,013 | 6,274 | 1.113× |
| one/1048576/root-sorted | 37,093 | 45,252 | 6,579 | 0.820× |
| one/12/absolute | 4,795 | 4,473 | 5,366 | 1.072× |
| one/12/absolute-sorted | 4,617 | 4,573 | 4,860 | 1.010× |
| one/12/root | 3,988 | 3,800 | 3,939 | 1.049× |
| one/12/root-sorted | 3,812 | 4,253 | 4,072 | 0.896× |
| prefix255/1048560/absolute | 3,990,821 | 4,075,731 | 7,123,782 | 0.979× |
| prefix255/1048560/absolute-sorted | 19,239,299 | 5,412,805 | 7,804,720 | 3.554× |
| prefix255/1048560/root | 3,831,243 | 4,005,632 | 6,870,315 | 0.956× |
| prefix255/1048560/root-sorted | 19,150,102 | 5,172,835 | 7,962,073 | 3.702× |
| prefix255/1048576/absolute | 3,783,914 | 3,737,277 | 7,075,109 | 1.012× |
| prefix255/1048576/absolute-sorted | 17,343,362 | 4,997,315 | 8,415,000 | 3.471× |
| prefix255/1048576/root | 3,977,118 | 3,831,586 | 7,080,327 | 1.038× |
| prefix255/1048576/root-sorted | 18,447,885 | 5,259,515 | 8,010,840 | 3.508× |
| short4096/1048576/absolute | 1,614,935 | 1,702,737 | 1,534,461 | 0.948× |
| short4096/1048576/absolute-sorted | 3,139,625 | 2,512,688 | 2,061,261 | 1.250× |
| short4096/1048576/root | 2,004,939 | 1,770,134 | 1,711,340 | 1.133× |
| short4096/1048576/root-sorted | 3,043,006 | 2,508,074 | 1,919,798 | 1.213× |
| short4096/49152/absolute | 1,322,963 | 1,280,405 | 1,375,136 | 1.033× |
| short4096/49152/absolute-sorted | 2,385,033 | 1,946,122 | 1,983,630 | 1.226× |
| short4096/49152/root | 1,434,911 | 1,404,292 | 1,168,312 | 1.022× |
| short4096/49152/root-sorted | 3,388,551 | 1,929,677 | 1,802,567 | 1.756× |

## Native API task results

Median sample means; ns/call except rename pairs. Unsupported cells remain explicit.

| Workload | goose-fs ns | Goose stdlib ns | Rust ns | Go ns |
| --- | ---: | ---: | ---: | ---: |
| file-set-owner | 390 | unsupported | 380 | 473 |
| file-set-permissions | 337 | unsupported | 312 | 414 |
| file-set-times | 400 | unsupported | 402 | unsupported |
| is-dir | 1,792 | 653 | 716 | 1,026 |
| list-sorted-0 | 8,318 | 2,335 | 2,387 | 3,412 |
| list-sorted-1 | 9,197 | 2,475 | 2,472 | 3,883 |
| list-sorted-128 | 38,858 | 22,720 | 35,275 | 50,210 |
| list-sorted-4096 | 2,266,564 | 2,859,321 | 2,655,530 | 4,335,837 |
| lock-exclusive-pair | 722 | unsupported | 576 | unsupported |
| metadata-file | 1,992 | unsupported | 723 | 1,030 |
| read-fresh-0 | 3,125 | 2,397 | 2,022 | 4,995 |
| read-fresh-1048576 | 215,439 | 186,290 | 112,347 | 365,562 |
| read-fresh-4096 | 3,958 | 3,216 | 2,497 | 7,809 |
| read-fresh-64 | 3,646 | 3,050 | 2,449 | 5,229 |
| read-fresh-65536 | 11,189 | 10,146 | 6,953 | 28,552 |
| read-retained-0 | 99 | unsupported | 216 | 8 |
| read-retained-1048576 | 159,885 | unsupported | 93,018 | 110,539 |
| read-retained-4096 | 565 | unsupported | 449 | 655 |
| read-retained-64 | 417 | unsupported | 309 | 360 |
| read-retained-65536 | 4,847 | unsupported | 4,469 | 5,733 |
| read-reuse-0 | 3,130 | 2,366 | 2,222 | 3,480 |
| read-reuse-1048576 | 146,952 | 172,558 | 97,802 | 129,106 |
| read-reuse-4096 | 3,663 | 3,297 | 2,588 | 5,225 |
| read-reuse-64 | 3,659 | 2,978 | 2,607 | 4,044 |
| read-reuse-65536 | 8,634 | 9,494 | 6,788 | 10,044 |
| rename-noreplace-pair | 8,065 | unsupported | unsupported | unsupported |
| rename-parents-sync-pair | 14,612 | unsupported | 12,500 | 30,287 |
| rename-replace-pair | 9,044 | 8,654 | 4,957 | 9,522 |
| root-list-sorted-128 | 31,143 | unsupported | unsupported | 39,989 |
| root-metadata-file | 1,115 | unsupported | unsupported | 1,008 |
| root-read-fresh-64 | 3,000 | unsupported | unsupported | 6,793 |
| root-rename-noreplace-pair | 5,208 | unsupported | unsupported | unsupported |
| root-rename-parents-sync-pair | 11,240 | unsupported | unsupported | 31,099 |
| root-rename-replace-pair | 5,418 | unsupported | unsupported | 8,782 |

## Reproduction and checks

Check out the measured source with the pinned compiler and recorded toolchains, then:

```sh
python3 bench/listing-build.py --goose .toolchain/goose/build/goose --cc gcc \
  --baseline-revision 3456547b8465b4b803ced6c5065fddd06e3a604f
taskset -c 6 python3 bench/listing-measure.py --goose .toolchain/goose/build/goose --cc gcc \
  --baseline .build/listing-pair/baseline --full .build/listing-pair/full \
  --adaptive .build/listing-pair/adaptive \
  --baseline-revision 3456547b8465b4b803ced6c5065fddd06e3a604f \
  --build-manifest .build/listing-pair/build.json --rounds 5 --iterations 5 \
  --output .build/listing-pair/sort-final.json
python3 bench/compare/build.py --goose .toolchain/goose/build/goose --cc gcc --adaptive-listing
taskset -c 6 python3 bench/compare/run.py --goose .toolchain/goose/build/goose --cc gcc --adaptive-listing \
  --iterations 200 --rounds 5 --seed 20261105 --output .build/compare/sort-final.json
```

For the additional shuffled series, check out its benchmark source d81bafa8255990d0244cea1f571717c41cfccf81, rebuild the three listing runners, and repeat the listing-measure command with `--creation-order shuffled --output .build/listing-pair/sort-shuffled.json`. The production source hashes match the initial series. The first command block reproduces the initial natural/native series at efa585c. No library implementation changed for this extra run.

Two independent security and quality/performance reviewers checked the implementation, including reference-slot swaps, bounded sorting, ABI guards, lifetime rules and the actual consumer-overload regression. Stable-source GCC/Clang full check/test and ASan/UBSan matrices passed; native static analysis passed. Native guard pages cover every 0..255 input-length pair, equal/prefix/high-byte/mismatch cases and malformed/null slices. Public JIT/optimized/debug tests verify sorted names survive later calls, allocation pressure and Context closure, with mixed-kind association and failure clearing. Consumer overloads for sort and its public-reference helpers cannot intercept internal dispatch. Binary/prefix ordering and 4,096-entry oracles, all 12 public listing routes, byte/entry boundaries, fallback/fault/race/resource tests passed.

Tests and reviews do not prove absence of bugs. See [the API contract](../../../docs/API.md), [feature gaps](../../../docs/feature-coverage.md), and [earlier staging tradeoffs](../2026-11-04-listing-staging/README.md). No cold-storage, remote-filesystem, contention, crash-recovery or universal performance claim is made.
