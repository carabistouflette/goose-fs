/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "support.h"
#include <dirent.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

static int descriptors(void) {
    DIR *d = opendir("/proc/self/fd"); assert(d);
    int n = 0; while (readdir(d)) ++n;
    assert(!closedir(d)); return n;
}
int main(int argc, char **argv) {
    assert(argc == 2);
    char path[4096]; assert(snprintf(path, sizeof path, "%s/file", argv[1]) > 0);
    uint8_t out[65536]; int64_t meta[3];
    assert(!invoke(2, path, "abcdef", out, 0, meta));
    assert(!invoke(0, path, "", out, 6, meta)); assert(meta[1] == 6 && !memcmp(out, "abcdef", 6));
    int before = descriptors();
    for (int i = 0; i < 1000; ++i) {
        assert(invoke(0, path, "", out, 5, meta) == 2);
        assert(meta[1] == 0 && meta[2] == 0);
        assert(invoke(1, path, "", out, sizeof out, meta) == 4);
    }
    assert(descriptors() == before);
    /* Exact writable boundary: neither read nor listing may touch the guard. */
    long page = sysconf(_SC_PAGESIZE); assert(page > 0);
    uint8_t *mem = mmap(NULL, (size_t)page * 2, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    assert(mem != MAP_FAILED); assert(!mprotect(mem+page, (size_t)page, PROT_NONE));
    assert(!invoke(0, path, "", mem+page-6, 6, meta));
    assert(invoke(0, path, "", mem+page-5, 5, meta) == 2);
    assert(!invoke(1, argv[1], "", mem+page-6, 6, meta));
    assert(invoke(1, argv[1], "", mem+page-5, 5, meta) == 2);
    assert(!munmap(mem, (size_t)page*2));
    gf_input p = {(const uint8_t *)path, (int64_t)strlen(path)};
    gf_input empty = {NULL, 0}; gf_output o = {out, 6}; gf_meta m = {meta, 3};
    assert(gf_call(0, p, empty, 0, o, (gf_meta){NULL, 3}) == 1);
    assert(gf_call(0, p, empty, 0, (gf_output){NULL, 6}, m) == 1);
    assert(gf_call(0, p, empty, 0, (gf_output){out, -1}, m) == 1);
    assert(gf_call(0, p, empty, 0, (gf_output){out, 1048577}, m) == 1);
    assert(gf_call(0, p, empty, 0, (gf_output){(uint8_t *)path, 6}, m) == 1);
    assert(gf_call(0, (gf_input){NULL, 6}, empty, 0, o, m) == 1);
    assert(gf_call(0, (gf_input){(uint8_t *)meta, 6}, empty, 0, o, m) == 1);
    assert(gf_call(0, p, empty, 0, (gf_output){(uint8_t *)meta, 6}, m) == 1);
    assert(gf_call(6, p, empty, 0, o, m) == 1);
    assert(!invoke(4, path, "", out, 0, meta));
    puts("native bounds, descriptor and ABI tests passed");
}
