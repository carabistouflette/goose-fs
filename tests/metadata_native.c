/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "support.h"
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>
static int mode, fallback_error, fallback_calls;
int __real_statx(int, const char *, int, unsigned, struct statx *);
int __real_fstatat(int, const char *, struct stat *, int);
int __wrap_fstatat(int dir, const char *path, struct stat *out, int flags) {
    ++fallback_calls;
    if (fallback_error) { errno = EACCES; return -1; }
    assert(flags == AT_SYMLINK_NOFOLLOW);
    return __real_fstatat(dir, path, out, flags);
}
int __wrap_statx(int dir, const char *path, int flags, unsigned mask, struct statx *out) {
    assert(flags == AT_SYMLINK_NOFOLLOW);
    if (mode == 1 || mode == 2 || mode == 3) { errno = mode == 1 ? ENOSYS : mode == 2 ? EPERM : EIO; return -1; }
    if (mode == 4) { memset(out, 0, sizeof *out); out->stx_mask = STATX_SIZE; return 0; }
    if (mode == 6) {
        memset(out, 0, sizeof *out);
        out->stx_mask = STATX_BASIC_STATS | STATX_BTIME;
        out->stx_mode = S_IFREG | 04751;
        out->stx_size = UINT64_C(0xfedcba9876543210); out->stx_ino = UINT64_MAX;
        out->stx_uid = UINT32_MAX; out->stx_gid = UINT32_MAX; out->stx_nlink = UINT32_MAX;
        out->stx_dev_major = UINT32_MAX; out->stx_dev_minor = UINT32_MAX;
        out->stx_atime.tv_sec = -2; out->stx_atime.tv_nsec = 123;
        out->stx_mtime.tv_sec = -3; out->stx_mtime.tv_nsec = 456;
        out->stx_ctime.tv_sec = -4; out->stx_ctime.tv_nsec = 789;
        out->stx_btime.tv_sec = -5; out->stx_btime.tv_nsec = 987;
        return 0;
    }
    int rc = __real_statx(dir, path, flags, mask, out);
    if (!rc && mode == 5) out->stx_mask &= ~STATX_BTIME;
    return rc;
}
static int64_t inspect(const char *path, int64_t fields[18]) {
    for (int i = 0; i < 18; ++i) fields[i] = 99;
    return gf_metadata((gf_input){(const uint8_t *)path, (int64_t)strlen(path)}, (gf_meta){fields,18});
}
int main(int argc, char **argv) {
    assert(argc == 2); char path[4096]; uint8_t unused[1]; int64_t legacy[3], fields[18];
    snprintf(path, sizeof path, "%s/file", argv[1]);
    assert(!invoke(2,path,"abcdef",unused,0,legacy));
    for (mode = 0; mode <= 5; ++mode) {
        fallback_calls = 0;
        int64_t code = inspect(path,fields);
        if (mode == 3) {
            assert(code == 4 && fields[0] == EIO && fallback_calls == 0);
            for (int i = 1; i < 18; ++i) assert(fields[i] == 0);
        } else {
            assert(!code && fields[0] == 0 && fields[1] == 1 && fields[2] == 6);
            if (mode == 1 || mode == 2 || mode == 4) assert(fallback_calls == 1 && !fields[17]);
            if (mode == 5) assert(!fields[15] && !fields[16] && !fields[17]);
        }
    }
    mode = 6;
    assert(!inspect(path,fields));
    assert((uint64_t)fields[2] == UINT64_C(0xfedcba9876543210));
    assert((uint64_t)fields[7] == UINT64_MAX && fields[4] == UINT32_MAX && fields[5] == UINT32_MAX);
    assert((uint64_t)fields[6] == (uint64_t)makedev(UINT32_MAX,UINT32_MAX));
    assert(fields[3] == 04751 && fields[9] == -2 && fields[10] == 123 && fields[15] == -5 && fields[16] == 987 && fields[17] == 1);
    mode = 1; fallback_error = 1;
    assert(inspect(path,fields) == 4 && fields[0] == EACCES);
    for (int i = 1; i < 18; ++i) assert(!fields[i]);
    assert(gf_metadata((gf_input){NULL,0},(gf_meta){fields,17}) == 1);
    assert(gf_metadata((gf_input){(uint8_t *)fields,8},(gf_meta){fields,18}) == 1);
    puts("metadata statx/fstatat failures, missing birth time and unsigned fields passed");
}
