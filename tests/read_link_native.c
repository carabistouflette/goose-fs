/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "../native/fs.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <linux/openat2.h>
#include <unistd.h>
#include <stdio.h>
static int64_t context, root;
static int relative;
static int calls, closes, inject, close_error, replacement = -1, fallback, read_fd = -1;
ssize_t __real_readlinkat(int,const char *,char *,size_t);
int __real_close(int);
long __real_syscall(long,...);
long __wrap_syscall(long number, ...) {
    assert(number == SYS_openat2);
    va_list ap;va_start(ap,number);int dir=va_arg(ap,int);const char *path=va_arg(ap,const char *);
    struct open_how *how=va_arg(ap,struct open_how *);size_t size=va_arg(ap,size_t);va_end(ap);
    if (fallback) { errno=ENOSYS;return -1; }
    return __real_syscall(number,dir,path,how,size);
}
int __wrap_close(int fd) {
    int rc=__real_close(fd);
    if (fd==read_fd) ++closes;
    if (close_error && fd==read_fd) {
        replacement=open("/dev/null",O_RDONLY|O_CLOEXEC);assert(replacement==fd);
        errno=close_error;close_error=0;return -1;
    }
    return rc;
}
ssize_t __wrap_readlinkat(int dir,const char *name,char *out,size_t cap) {
    ++calls;read_fd=dir;
    if (inject==1 && calls==1) { errno=EINTR;return -1; }
    if (inject==2) { errno=EIO;return -1; }
    if (inject==3) { memset(out,'q',cap);return (ssize_t)cap; }
    return __real_readlinkat(dir,name,out,cap);
}
static int64_t invoke(const char *path,int64_t limit,uint8_t *out,int64_t cap,int64_t meta[3]) {
    read_fd=-1;
    if (relative) {
        const char *leaf=strrchr(path,'/')+1;
        return gf_root_read_link(context,root,(gf_input){(const uint8_t *)leaf,(int64_t)strlen(leaf)},limit,
                                 (gf_output){out,cap},(gf_meta){meta,3});
    }
    return gf_read_link((gf_input){(const uint8_t *)path,(int64_t)strlen(path)},limit,
                        (gf_output){out,cap},(gf_meta){meta,3});
}
int main(int argc,char **argv) {
    assert(argc==2);char path[4096];snprintf(path,sizeof path,"%s/link",argv[1]);assert(!symlink("abc",path));
    uint8_t out[257];int64_t m[3];
    assert(!gf_context_create((gf_meta){m,3}));context=m[1];
    assert(!gf_root_open(context,(gf_input){(const uint8_t *)argv[1],(int64_t)strlen(argv[1])},(gf_meta){m,3}));root=m[1];
    for(relative=0;relative<=1;++relative) {
    for(fallback=0;fallback<=1;++fallback) {
        calls=0;inject=1;assert(invoke(path,3,out,4,m)==0 && m[1]==3 && !memcmp(out,"abc",3) && calls==2);
        inject=0;assert(invoke(path,2,out,3,m)==2 && !m[0] && !m[1]);
        assert(invoke(path,0,out,1,m)==2 && !m[0] && !m[1]);
        assert(invoke(path,10,out,2,m)==5 && !m[0] && !m[1]);
    }
    fallback=0;inject=0;calls=closes=0;close_error=EINTR;
    assert(invoke(path,3,out,4,m)==4 && m[0]==EINTR && !m[1] && closes==1);
    assert(fcntl(replacement,F_GETFD)>=0);__real_close(replacement);
    close_error=EIO;closes=0;
    assert(invoke(path,10,out,2,m)==4 && m[0]==EIO && !m[1] && closes==1);__real_close(replacement);
    inject=2;close_error=EINTR;assert(invoke(path,3,out,4,m)==4 && m[0]==EIO && !m[1]);__real_close(replacement);
    inject=0;close_error=EIO;assert(invoke(path,0,out,1,m)==2 && !m[0] && !m[1]);__real_close(replacement);
    calls=0;
    assert(invoke(path,-1,out,1,m)==1 && !calls);
    assert(invoke(path,1048577,out,1,m)==1 && !calls);
    assert(invoke(path,3,out,0,m)==1 && !calls);
    assert(invoke(path,3,NULL,4,m)==1 && !calls);
    assert(invoke(path,3,out,5,m)==1 && !calls);
    assert(gf_read_link((gf_input){out,1},3,(gf_output){out,4},(gf_meta){m,3})==1 && !calls);
    assert(gf_read_link((gf_input){(uint8_t *)m,1},3,(gf_output){out,4},(gf_meta){m,3})==1 && !calls);
    assert(gf_read_link((gf_input){(uint8_t *)path,(int64_t)strlen(path)},3,(gf_output){(uint8_t *)m,4},(gf_meta){m,3})==1 && !calls);
    long page=sysconf(_SC_PAGESIZE);uint8_t *map=mmap(NULL,(size_t)page*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    assert(map!=MAP_FAILED && !mprotect(map+page,(size_t)page,PROT_NONE));
    inject=3;assert(invoke(path,256,map+page-257,257,m)==2);
    assert(invoke(path,256,map+page-256,256,m)==5);
    uint8_t *maximum=malloc(1048577);assert(maximum);
    assert(invoke(path,1048576,maximum,1048577,m)==2 && !m[1]);free(maximum);
    munmap(map,(size_t)page*2);
    }
    assert(!gf_context_close(context,(gf_meta){m,3}));
    puts("readlink native EINTR/truncation/close reuse/precedence/ABI/guard boundaries passed");
}
