/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "support.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <sys/stat.h>
#include <unistd.h>
static int read_mode, write_mode, close_mode, directory_mode, closedir_mode;
static int read_progress, write_progress;
static int stat_mode, directory_open_mode, open_mode;
int __real_fstat(int, struct stat *);
DIR *__real_fdopendir(int);
int __real_openat(int, const char *, ...);
int __wrap_fstat(int fd, struct stat *st) {
    if (stat_mode) { stat_mode = 0; errno = EIO; return -1; }
    return __real_fstat(fd, st);
}
DIR *__wrap_fdopendir(int fd) {
    if (directory_open_mode) { directory_open_mode = 0; errno = ENOMEM; return NULL; }
    return __real_fdopendir(fd);
}
int __wrap_openat(int dir, const char *path, int flags, ...) {
    if (open_mode) { open_mode = 0; errno = EACCES; return -1; }
    int mode = 0;
    if (flags & O_CREAT) {
        va_list args; va_start(args, flags); mode = va_arg(args, int); va_end(args);
    }
    return __real_openat(dir, path, flags, mode);
}
static int descriptors(void) {
    DIR *dir = opendir("/proc/self/fd"); assert(dir);
    int n = 0; while (readdir(dir)) ++n;
    assert(!closedir(dir)); return n;
}
ssize_t __real_read(int, void *, size_t);
ssize_t __real_write(int, const void *, size_t);
int __real_close(int);
struct dirent *__real_readdir(DIR *);
int __real_closedir(DIR *);
ssize_t __wrap_read(int fd, void *buf, size_t n) {
    int mode = read_mode;
    if (mode == 5) {
        if (!read_progress++) return __real_read(fd, buf, n > 1 ? 1 : n);
        errno = EIO; return -1;
    }
    if (mode == 1 || mode == 2) { read_mode = 0; errno = mode == 1 ? EINTR : EIO; return -1; }
    return __real_read(fd, buf, mode == 3 && n > 1 ? 1 : n);
}
ssize_t __wrap_write(int fd, const void *buf, size_t n) {
    int mode = write_mode;
    if (mode == 5) {
        if (!write_progress++) return __real_write(fd, buf, n > 1 ? 1 : n);
        errno = ENOSPC; return -1;
    }
    if (mode == 1 || mode == 2) { write_mode = 0; errno = mode == 1 ? EINTR : ENOSPC; return -1; }
    if (mode == 4) return 0;
    return __real_write(fd, buf, mode == 3 && n > 1 ? 1 : n);
}
int __wrap_close(int fd) {
    int flags = fcntl(fd, F_GETFL);
    int rc = __real_close(fd);
    if (close_mode && flags >= 0 && !(flags & O_PATH)) { close_mode = 0; errno = EINTR; return -1; }
    return rc;
}
struct dirent *__wrap_readdir(DIR *d) {
    if (directory_mode == 1 || directory_mode == 3) { directory_mode = 0; errno = EIO; return NULL; }
    struct dirent *entry = __real_readdir(d);
    if (directory_mode == 2 && entry && strcmp(entry->d_name, ".") && strcmp(entry->d_name, "..")) directory_mode = 3;
    return entry;
}
int __wrap_closedir(DIR *d) {
    int rc = __real_closedir(d);
    if (closedir_mode) { closedir_mode = 0; errno = EIO; return -1; }
    return rc;
}
int main(int argc, char **argv) {
    assert(argc == 2); char path[4096]; uint8_t out[100]; int64_t m[3];
    assert(snprintf(path, sizeof path, "%s/file", argv[1]) > 0);
    for (int mode = 0; mode <= 5; ++mode) {
        write_mode = mode;
        int code = (int)invoke(2, path, "abcdef", out, 0, m);
        assert(code == ((mode == 2 || mode == 4 || mode == 5) ? 4 : 0));
        if (code) assert(m[0] == ((mode == 2 || mode == 5) ? ENOSPC : EIO));
        write_mode = 0;
        assert(!invoke(4, path, "", out, 0, m));
    }
    assert(!invoke(2, path, "abcdef", out, 0, m));
    for (int mode = 0; mode <= 5; ++mode) {
        if (mode == 4) continue;
        read_mode = mode;
        int code = (int)invoke(0, path, "", out, 6, m);
        assert(code == ((mode == 2 || mode == 5) ? 4 : 0));
        if (!code) assert(m[1] == 6 && !memcmp(out, "abcdef", 6));
        else assert(m[0] == EIO && !m[1]);
    }
    read_mode = 0;
    int before = descriptors();
    stat_mode = 1; close_mode = 1;
    assert(invoke(0, path, "", out, 6, m) == 4 && m[0] == EIO && !m[1]);
    directory_open_mode = 1; close_mode = 1;
    assert(invoke(1, argv[1], "", out, 100, m) == 4 && m[0] == ENOMEM && !m[1]);
    open_mode = 1;
    assert(invoke(0, path, "", out, 6, m) == 4 && m[0] == EACCES && !m[1]);
    assert(descriptors() == before);
    close_mode = 1;
    assert(invoke(0, path, "", out, 6, m) == 4 && m[0] == EINTR && !m[1]);
    directory_mode = 1;
    assert(invoke(1, argv[1], "", out, 100, m) == 4 && m[0] == EIO && !m[1]);
    directory_mode = 2;
    assert(invoke(1, argv[1], "", out, 100, m) == 4 && m[0] == EIO && !m[1] && !m[2]);
    closedir_mode = 1;
    assert(invoke(1, argv[1], "", out, 100, m) == 4 && m[0] == EIO && !m[1]);
    assert(!invoke(4, path, "", out, 0, m));
    close_mode = 1;
    assert(invoke(2, path, "written", out, 0, m) == 4 && m[0] == EINTR);
    assert(!invoke(0, path, "", out, 100, m) && m[1] == 7);
    puts("injected short I/O, EINTR, zero-progress, full-disk and close failures passed");
}
