/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "support.h"
#include <errno.h>
#include <fcntl.h>
#include <sys/resource.h>
#include <unistd.h>
static int mode, calls;
static int fail_read(void) {
    ++calls;
    if (calls == 2 && mode) { errno = mode == 1 ? EIO : EINTR; return 1; }
    return 0;
}
ssize_t __real_read(int, void *, size_t);
ssize_t __wrap_read(int fd, void *out, size_t n) {
    if (fail_read()) return -1;
    return __real_read(fd, out, n);
}
#ifdef __GLIBC__
/* Ubuntu GCC13 + FORTIFY3 routes the stack-byte probe through __read_chk.
 * Intercept it too, and preserve its bounds check when forwarding real I/O. */
ssize_t __real___read_chk(int, void *, size_t, size_t);
ssize_t __wrap___read_chk(int fd, void *out, size_t n, size_t capacity) {
    if (fail_read()) return -1;
    return __real___read_chk(fd, out, n, capacity);
}
#endif
int main(int argc, char **argv) {
    assert(argc == 2); char path[4096]; uint8_t out[6]; int64_t m[3];
    assert(snprintf(path,sizeof path,"%s/file",argv[1])>0);
    assert(!invoke(2,path,"abcdef",out,0,m));
    mode=1; calls=0;
    assert(invoke(0,path,"",out,6,m)==4 && m[0]==EIO && !m[1] && !m[2]);
    mode=2; calls=0;
    assert(!invoke(0,path,"",out,6,m) && m[1]==6 && calls==3);
    mode=0;
    struct rlimit old, reduced; assert(!getrlimit(RLIMIT_NOFILE,&old));
    reduced=old; if(reduced.rlim_cur>64)reduced.rlim_cur=64;
    assert(!setrlimit(RLIMIT_NOFILE,&reduced));
    int fds[64], count=0;
    while(count<64) {int fd=open("/dev/null",O_RDONLY|O_CLOEXEC);if(fd<0){assert(errno==EMFILE);break;}fds[count++]=fd;}
    assert(count<64);
    assert(invoke(0,path,"",out,6,m)==4 && m[0]==EMFILE && !m[1] && !m[2]);
    /* One slot allows an initial open, but a later open must fail. Every
     * descriptor acquired before that failure must still be released. */
    assert(count > 0);
    assert(!close(fds[--count]));
    for (int i = 0; i < 100; ++i) {
        assert(invoke(0,path,"",out,6,m)==4 && m[0]==EMFILE && !m[1] && !m[2]);
        int probe = open("/dev/null", O_RDONLY|O_CLOEXEC);
        assert(probe >= 0);
        assert(!close(probe));
    }
    for(int i=0;i<count;i++)assert(!close(fds[i]));
    assert(!setrlimit(RLIMIT_NOFILE,&old));
    assert(!invoke(0,path,"",out,6,m) && m[1]==6);
    puts("overflow-probe EIO/EINTR and real EMFILE recovery passed");
}
