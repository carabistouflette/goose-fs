GOOSE ?= .toolchain/goose/build/goose
CC ?= gcc
SANITIZER_CC ?= gcc
BENCH_CC ?= gcc
BENCH_ITERATIONS ?= 100
CFLAGS = -std=c11 -Wall -Wextra -Werror
.NOTPARALLEL:
.PHONY: setup format check test native sanitize bench
setup:
	./scripts/setup-goose.sh
format:
	python3 scripts/native-manifest.py
	$(GOOSE) format fs.goose tests examples bench
check:
	python3 scripts/native-manifest.py --check
	$(GOOSE) format --check fs.goose tests examples bench
	$(GOOSE) check tests/api.goose
	$(GOOSE) check examples/read.goose
	$(GOOSE) check bench/bench.goose
test:
	python3 scripts/native-manifest.py --check
	mkdir -p .build
	python3 tests/run.py $(abspath $(GOOSE)) run tests/api.goose --
	$(GOOSE) build tests/api.goose --cc $(CC) -O2 -o .build/api
	python3 tests/run.py .build/api
	$(GOOSE) build tests/api.goose --cc $(CC) --debug --no-bce -o .build/api-debug
	python3 tests/run.py .build/api-debug
	python3 tests/ownership.py $(abspath $(GOOSE))
	python3 tests/run.py $(abspath $(GOOSE)) run tests/overloads.goose --
	$(GOOSE) build tests/overloads.goose --cc $(CC) -O2 -o .build/overloads
	python3 tests/run.py .build/overloads
	$(MAKE) native
native:
	mkdir -p .build
	$(CC) $(CFLAGS) -O2 -shared -fPIC native/fs.c -o .build/fs.so
	python3 tests/model.py
	$(CC) $(CFLAGS) -O2 tests/native.c native/fs.c -o .build/native
	python3 tests/run.py .build/native
	$(CC) $(CFLAGS) -O2 tests/failures.c native/fs.c -Wl,--wrap=read -Wl,--wrap=write -Wl,--wrap=close -Wl,--wrap=readdir -Wl,--wrap=closedir -o .build/failures
	python3 tests/run.py .build/failures
sanitize:
	mkdir -p .build
	$(SANITIZER_CC) $(CFLAGS) -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie tests/native.c native/fs.c -o .build/native-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/native-sanitize
	$(SANITIZER_CC) $(CFLAGS) -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie tests/failures.c native/fs.c -Wl,--wrap=read -Wl,--wrap=write -Wl,--wrap=close -Wl,--wrap=readdir -Wl,--wrap=closedir -o .build/failures-sanitize
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/run.py .build/failures-sanitize
bench:
	python3 scripts/native-manifest.py --check
	mkdir -p .build
	$(GOOSE) build bench/bench.goose --cc $(BENCH_CC) -O2 -o .build/bench
	python3 bench/measure.py --goose $(abspath $(GOOSE)) --cc $(BENCH_CC) --iterations $(BENCH_ITERATIONS)
