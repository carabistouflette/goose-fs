GOOSE ?= .toolchain/goose/build/goose
CC ?= gcc
SANITIZER_CC ?= gcc
BENCH_CC ?= gcc
BENCH_ITERATIONS ?= 100
CFLAGS = -std=c11 -Wall -Wextra -Werror -pthread
RESOURCE_WRAP = -Wl,--wrap=read -Wl,--wrap=__read_chk
HANDLE_WRAP = -Wl,--wrap=read -Wl,--wrap=pread -Wl,--wrap=__read_chk -Wl,--wrap=__pread_chk -Wl,--wrap=write -Wl,--wrap=pwrite -Wl,--wrap=close -Wl,--wrap=fstat -Wl,--wrap=ftruncate -Wl,--wrap=fsync -Wl,--wrap=fdatasync -Wl,--wrap=lseek -Wl,--wrap=fcntl
WRAP_FLAGS = -Wl,--wrap=read -Wl,--wrap=write -Wl,--wrap=close -Wl,--wrap=readdir -Wl,--wrap=closedir -Wl,--wrap=fstat -Wl,--wrap=fdopendir -Wl,--wrap=openat
.NOTPARALLEL:
.PHONY: setup format check test native handles resources fallback sanitize bench
setup:
	./scripts/setup-goose.sh
format:
	python3 scripts/native-manifest.py
	$(GOOSE) format fs.goose tests examples bench
check:
	python3 scripts/native-manifest.py --check
	$(GOOSE) format --check fs.goose tests examples bench
	$(GOOSE) check tests/api.goose
	$(GOOSE) check tests/handles.goose
	$(GOOSE) check tests/handles_workers.goose
	$(GOOSE) check tests/metadata.goose
	$(GOOSE) check tests/sorted_oracle.goose
	$(GOOSE) check examples/read.goose
	$(GOOSE) check examples/stream.goose
	$(GOOSE) check bench/bench.goose
test:
	python3 scripts/native-manifest.py --check
	mkdir -p .build
	python3 tests/run.py --api $(abspath $(GOOSE)) run tests/api.goose --
	$(GOOSE) build tests/api.goose --cc $(CC) -O2 -o .build/api
	python3 tests/run.py --api .build/api
	$(GOOSE) build tests/api.goose --cc $(CC) --debug --no-bce -o .build/api-debug
	python3 tests/run.py --api .build/api-debug
	python3 tests/run.py --api $(abspath $(GOOSE)) run tests/metadata.goose --
	$(GOOSE) build tests/metadata.goose --cc $(CC) -O2 -o .build/metadata
	python3 tests/run.py --api .build/metadata
	$(GOOSE) build tests/metadata.goose --cc $(CC) --debug --no-bce -o .build/metadata-debug
	python3 tests/run.py --api .build/metadata-debug
	$(GOOSE) build tests/sorted_oracle.goose --cc $(CC) -O2 -o .build/sorted-oracle
	$(GOOSE) build tests/sorted_oracle.goose --cc $(CC) --debug --no-bce -o .build/sorted-oracle-debug
	python3 tests/sorted_model.py .build/sorted-oracle .build/sorted-oracle-debug
	python3 tests/run.py $(abspath $(GOOSE)) run tests/handles.goose --
	$(GOOSE) build tests/handles.goose --cc $(CC) -O2 -o .build/handles
	python3 tests/run.py .build/handles
	$(GOOSE) build tests/handles.goose --cc $(CC) --debug --no-bce -o .build/handles-debug
	python3 tests/run.py .build/handles-debug
	$(GOOSE) build tests/handles_workers.goose --cc $(CC) -O2 -o .build/handles-workers
	python3 tests/run.py .build/handles-workers
	$(GOOSE) build tests/handles_workers.goose --cc $(CC) --debug --no-bce -o .build/handles-workers-debug
	python3 tests/run.py .build/handles-workers-debug
	$(MAKE) handles
	python3 tests/ownership.py $(abspath $(GOOSE))
	python3 tests/run.py $(abspath $(GOOSE)) run tests/overloads.goose --
	$(GOOSE) build tests/overloads.goose --cc $(CC) -O2 -o .build/overloads
	python3 tests/run.py .build/overloads
	$(MAKE) native
handles:
	mkdir -p .build
	$(CC) $(CFLAGS) -O2 -shared -fPIC native/fs.c native/handles.c -o .build/fs-handles.so
	python3 tests/handles_model.py
	$(CC) $(CFLAGS) -O2 -shared -fPIC native/fs.c native/handles.c tests/no-openat2.c -Wl,--wrap=syscall -o .build/fs-handles-fallback.so
	FS_HANDLES_LIBRARY=$(abspath .build/fs-handles-fallback.so) python3 tests/handles_model.py
	$(CC) $(CFLAGS) -O2 -shared -fPIC native/fs.c native/handles.c -Wl,--wrap=statx -o .build/fs-handles-no-statx.so
	FS_HANDLES_LIBRARY=$(abspath .build/fs-handles-no-statx.so) python3 tests/handles_model.py
	$(CC) $(CFLAGS) -O2 tests/handles_native.c native/fs.c $(HANDLE_WRAP) -o .build/handles-native
	python3 tests/run.py .build/handles-native
native:
	mkdir -p .build
	$(CC) $(CFLAGS) -O2 -shared -fPIC native/fs.c -o .build/fs.so
	python3 tests/model.py
	python3 tests/metadata_model.py
	$(CC) $(CFLAGS) -O2 -shared -fPIC native/fs.c -Wl,--wrap=statx -o .build/fs-no-statx.so
	FS_NATIVE_LIBRARY=$(abspath .build/fs-no-statx.so) python3 tests/metadata_model.py
	$(CC) $(CFLAGS) -O2 tests/metadata_native.c native/fs.c -Wl,--wrap=statx -Wl,--wrap=fstatat -o .build/metadata-native
	python3 tests/run.py .build/metadata-native
	python3 tests/stress.py
	$(CC) $(CFLAGS) -O2 tests/native.c native/fs.c -o .build/native
	python3 tests/run.py .build/native
	$(CC) $(CFLAGS) -O2 tests/failures.c native/fs.c $(WRAP_FLAGS) -o .build/failures
	python3 tests/run.py .build/failures
	$(MAKE) resources
	$(MAKE) fallback
resources:
	mkdir -p .build
	$(CC) $(CFLAGS) -O2 tests/resources.c native/fs.c $(RESOURCE_WRAP) -o .build/resources
	python3 tests/run.py .build/resources
	$(CC) $(CFLAGS) -O2 tests/resources.c native/fs.c tests/no-openat2.c $(RESOURCE_WRAP) -Wl,--wrap=syscall -o .build/resources-fallback
	python3 tests/run.py .build/resources-fallback
	$(CC) $(CFLAGS) -O2 tests/cloexec.c native/fs.c -Wl,--wrap=open -Wl,--wrap=openat -Wl,--wrap=syscall -o .build/cloexec
	python3 tests/run.py .build/cloexec
	$(CC) $(CFLAGS) -O2 -DGF_FORCE_WALKER tests/cloexec.c native/fs.c -Wl,--wrap=open -Wl,--wrap=openat -Wl,--wrap=syscall -o .build/cloexec-fallback
	python3 tests/run.py .build/cloexec-fallback
fallback:
	mkdir -p .build
	$(CC) $(CFLAGS) -O2 tests/failures.c native/fs.c tests/no-openat2.c $(WRAP_FLAGS) -Wl,--wrap=syscall -o .build/failures-fallback
	python3 tests/run.py .build/failures-fallback
	$(CC) $(CFLAGS) -O2 -shared -fPIC native/fs.c tests/no-openat2.c -Wl,--wrap=syscall -o .build/fs-fallback.so
	FS_NATIVE_LIBRARY=$(abspath .build/fs-fallback.so) python3 tests/model.py
	FS_NATIVE_LIBRARY=$(abspath .build/fs-fallback.so) python3 tests/stress.py
	$(CC) $(CFLAGS) -O2 -shared -fPIC -DGF_DENIED_ERRNO=EPERM native/fs.c tests/no-openat2.c -Wl,--wrap=syscall -o .build/fs-denied.so
	FS_NATIVE_LIBRARY=$(abspath .build/fs-denied.so) python3 tests/model.py
	FS_NATIVE_LIBRARY=$(abspath .build/fs-denied.so) python3 tests/stress.py
sanitize:
	mkdir -p .build
	SANITIZER_CC=$(SANITIZER_CC) $(GOOSE) build tests/handles.goose --debug --no-bce --cc $(abspath scripts/sanitizer-cc.sh) -o .build/handles-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/handles-sanitize
	SANITIZER_CC=$(SANITIZER_CC) $(GOOSE) build tests/handles_workers.goose --debug --no-bce --cc $(abspath scripts/sanitizer-cc.sh) -o .build/handles-workers-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/handles-workers-sanitize
	$(SANITIZER_CC) $(CFLAGS) -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie tests/handles_native.c native/fs.c $(HANDLE_WRAP) -o .build/handles-native-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/handles-native-sanitize
	SANITIZER_CC=$(SANITIZER_CC) $(GOOSE) build tests/metadata.goose --debug --no-bce --cc $(abspath scripts/sanitizer-cc.sh) -o .build/metadata-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py --api .build/metadata-sanitize
	$(SANITIZER_CC) $(CFLAGS) -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie tests/metadata_native.c native/fs.c -Wl,--wrap=statx -Wl,--wrap=fstatat -o .build/metadata-native-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/metadata-native-sanitize
	python3 scripts/native-manifest.py --check
	SANITIZER_CC=$(SANITIZER_CC) $(GOOSE) build tests/api.goose --debug --no-bce --cc $(abspath scripts/sanitizer-cc.sh) -o .build/api-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py --api .build/api-sanitize
	$(SANITIZER_CC) $(CFLAGS) -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie tests/native.c native/fs.c -o .build/native-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/native-sanitize
	$(SANITIZER_CC) $(CFLAGS) -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie tests/failures.c native/fs.c $(WRAP_FLAGS) -o .build/failures-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/failures-sanitize
	$(SANITIZER_CC) $(CFLAGS) -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie tests/native.c native/fs.c tests/no-openat2.c -Wl,--wrap=syscall -o .build/fallback-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/fallback-sanitize
	$(SANITIZER_CC) $(CFLAGS) -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie tests/resources.c native/fs.c $(RESOURCE_WRAP) -o .build/resources-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/resources-sanitize
	$(SANITIZER_CC) $(CFLAGS) -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie tests/cloexec.c native/fs.c -Wl,--wrap=open -Wl,--wrap=openat -Wl,--wrap=syscall -o .build/cloexec-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/cloexec-sanitize
bench:
	python3 scripts/native-manifest.py --check
	mkdir -p .build
	$(GOOSE) build bench/bench.goose --cc $(BENCH_CC) -O2 -o .build/bench
	python3 bench/measure.py --goose $(abspath $(GOOSE)) --cc $(BENCH_CC) --iterations $(BENCH_ITERATIONS)
