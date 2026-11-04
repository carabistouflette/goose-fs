/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "support.h"
#include <errno.h>
#include <fcntl.h>
#include <linux/openat2.h>
#include <inttypes.h>
#include <sys/stat.h>
#include <stdarg.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

static int checked;

/* Check inheritance while the descriptor is still owned by the operation. */
static void verify(int fd) {
    if (fd < 0) return;
    int bits = fcntl(fd, F_GETFD);
    assert(bits >= 0 && (bits & FD_CLOEXEC));
    struct stat expected; assert(!fstat(fd, &expected));
    pid_t pid = fork(); assert(pid >= 0);
    if (!pid) {
        char text[30], device[30], inode[30];
        snprintf(text, sizeof text, "%d", fd);
        snprintf(device, sizeof device, "%ju", (uintmax_t)expected.st_dev);
        snprintf(inode, sizeof inode, "%ju", (uintmax_t)expected.st_ino);
        execl("/proc/self/exe", "cloexec", "inspect", text, device, inode, NULL);
        _exit(90);
    }
    int status;
    pid_t waited;
    do { waited = waitpid(pid, &status, 0); } while (waited < 0 && errno == EINTR);
    assert(waited == pid && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    ++checked;
}

int __real_open(const char *, ...);
int __wrap_open(const char *name, int flags, ...) {
    int mode = 0;
    if (flags & O_CREAT) {
        va_list args; va_start(args, flags); mode = va_arg(args, int); va_end(args);
    }
    int fd = __real_open(name, flags, mode);
    int saved = errno; verify(fd); errno = saved; return fd;
}

int __real_openat(int, const char *, ...);
int __wrap_openat(int dir, const char *name, int flags, ...) {
    int mode = 0;
    if (flags & O_CREAT) {
        va_list args; va_start(args, flags); mode = va_arg(args, int); va_end(args);
    }
    int fd = __real_openat(dir, name, flags, mode);
    int saved = errno; verify(fd); errno = saved; return fd;
}

long __real_syscall(long, ...);
long __wrap_syscall(long number, ...) {
    assert(number == SYS_openat2);
#ifdef GF_FORCE_WALKER
    errno = ENOSYS;
    return -1;
#else
    va_list args; va_start(args, number);
    int dir = va_arg(args, int);
    const char *name = va_arg(args, const char *);
    struct open_how *how = va_arg(args, struct open_how *);
    size_t size = va_arg(args, size_t);
    va_end(args);
    long fd = __real_syscall(number, dir, name, how, size);
    int saved = errno; verify((int)fd); errno = saved; return fd;
#endif
}

int main(int argc, char **argv) {
    if (argc == 5 && !strcmp(argv[1], "inspect")) {
        int fd = atoi(argv[2]);
        struct stat current;
        if (fstat(fd, &current) < 0) { assert(errno == EBADF); }
        else {
            // Runtime startup may reuse a closed descriptor number.
            assert((uintmax_t)current.st_dev != strtoumax(argv[3], NULL, 10) ||
                   (uintmax_t)current.st_ino != strtoumax(argv[4], NULL, 10));
        }
        return 0;
    }
    assert(argc == 2);
    char path[4096]; uint8_t out[100]; int64_t meta[3];
    assert(snprintf(path, sizeof path, "%s/file", argv[1]) > 0);
    assert(!invoke(2, path, "data", out, 0, meta));
    assert(!invoke(0, path, "", out, 4, meta));
    assert(!invoke(1, argv[1], "", out, sizeof out, meta));
    assert(checked >= 6);
    puts("CLOEXEC flags and real exec noninheritance passed");
}
