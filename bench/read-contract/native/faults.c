/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
static const char *mode;
static int active, leaf=-1, parent=-1, walker=-1, next_fd=-1, reused=-1;
static int open2,opens,reads,stats,injected,closes;
static int file_closes,parent_closes,walk_closes,next_closes,read_bytes,growth_checked;
long __real_syscall(long,...);
int __real_openat(int,const char *,...);
int __real_open(const char *,...);
int __real_fstat(int,struct stat *);
ssize_t __real_read(int,void *,size_t);
int __real_close(int);
static int is(const char *s) { return mode && !strcmp(mode,s); }
static int prefix(const char *s) { return mode && !strncmp(mode,s,strlen(s)); }
static int suffix(const char *s) { return mode && strlen(mode)>=strlen(s) && !strcmp(mode+strlen(mode)-strlen(s),s); }
long __wrap_syscall(long number,...) {
    /* No untyped forwarding for unrelated syscall signatures. */
    assert(number==SYS_openat2);
    mode=getenv("READ_CONTRACT_FAULT"); active=mode && *mode;
    va_list a; va_start(a,number);
    int dir=va_arg(a,int); const char *path=va_arg(a,const char *);
    const void *how=va_arg(a,const void *); size_t size=va_arg(a,size_t); va_end(a);
    if(active) {
        uint64_t words[3]; assert(size==sizeof words); memcpy(words,how,sizeof words);
        assert(dir==AT_FDCWD && words[0]==(O_PATH|O_DIRECTORY|O_CLOEXEC) && words[1]==0 && words[2]==4);
        ++open2;
        if(is("fallback1") || is("fallback38") || prefix("walk_")) {
            ++injected; errno=is("fallback1") ? EPERM : ENOSYS; return -1;
        }
    }
    long fd=__real_syscall(number,dir,path,how,size);
    if(active && fd>=0) parent=(int)fd;
    return fd;
}
static void opened(int dir,int fd,int flags) {
    if(!active) return;
    ++opens;
    assert(flags==((flags&O_PATH) ? (O_PATH|O_DIRECTORY|O_CLOEXEC|(dir>=0 ? O_NOFOLLOW : 0)) : (O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_NOCTTY|O_CLOEXEC)));
    if(!(flags&O_PATH)) { if(fd>=0) leaf=fd; parent=dir; next_fd=-1; }
    else if(dir>=0) { walker=dir; next_fd=fd; }
}
int __wrap_openat(int dir,const char *path,int flags,...) {
    int permissions=0;
    if(flags&O_CREAT) { va_list a; va_start(a,flags); permissions=va_arg(a,int); va_end(a); }
    if(active && is("walk_open_close") && dir>=0 && (flags&O_PATH)) {
        opened(dir,-1,flags); ++injected; errno=EACCES; return -1;
    }
    int fd=__real_openat(dir,path,flags,permissions); opened(dir,fd,flags); return fd;
}
int __wrap_open(const char *path,int flags,...) {
    int permissions=0;
    if(flags&O_CREAT) { va_list a; va_start(a,flags); permissions=va_arg(a,int); va_end(a); }
    int fd=__real_open(path,flags,permissions); opened(AT_FDCWD,fd,flags); return fd;
}
int __wrap_fstat(int fd,struct stat *st) {
    int rc=__real_fstat(fd,st);
    if(active && fd==leaf) {
        ++stats;
        if(is("stat_eio")) { ++injected; errno=EIO; return -1; }
        if(!rc && (is("stat_small") || is("stat_large"))) {
            ++injected; st->st_size=is("stat_small") ? 0 : INT64_MAX;
        }
    }
    return rc;
}
ssize_t __wrap_read(int fd,void *buf,size_t n) {
    if(active && fd==leaf) {
        ++reads;
        if(prefix("growth-") && reads==1) {
            char *end; long old=strtol(mode+7,&end,10); assert(!*end && old>=0 && (size_t)old<=n);
            for(size_t i=(size_t)old;i<n;++i) assert(((const unsigned char *)buf)[i]==0);
            ++growth_checked; ++injected;
        }
        if(is("eintr") && reads==1) { ++injected; errno=EINTR; return -1; }
        if(is("read_eio") || prefix("read_close_")) {
            if(reads>1) { ++injected; errno=EIO; return -1; }
            if(n>1) n=1;
        }
        if(is("short") && n>3) { n=3; ++injected; }
    }
    ssize_t got=__real_read(fd,buf,n);
    if(active && fd==leaf && got>0) read_bytes+=(int)got;
    return got;
}
ssize_t __wrap___read_chk(int fd,void *buf,size_t n,size_t capacity) {
    assert(n<=capacity); return __wrap_read(fd,buf,n);
}
int __wrap_close(int fd) {
    int fail=0;
    if(active) {
        ++closes;
        if(fd==leaf) {
            ++file_closes;
            fail=suffix("close_eio") || suffix("close_eintr") || is("reuse_file");
        } else if(fd==walker) {
            ++walk_closes; fail=prefix("walk_") && walk_closes==1; walker=-1;
        } else if(fd==next_fd) { ++next_closes; next_fd=-1; }
        else if(fd==parent) { ++parent_closes; fail=is("parent_close"); }
    }
    int rc=__real_close(fd);
    if(fail) {
        assert(rc==0); ++injected;
        reused=__real_open("/dev/null",O_RDONLY|O_CLOEXEC); assert(reused==fd);
        errno=suffix("eintr") ? EINTR : EIO; return -1;
    }
    return rc;
}
void contract_fault_finish(void) {
    if(!active) return;
    int checked=0;
    if(reused>=0) { assert(fcntl(reused,F_GETFD)>=0); assert(!__real_close(reused)); checked=1; }
    active=0;
    fprintf(stderr,"{\"open2\":%d,\"opens\":%d,\"reads\":%d,\"stats\":%d,\"injected\":%d,\"closes\":%d,\"file_closes\":%d,\"parent_closes\":%d,\"walk_closes\":%d,\"next_closes\":%d,\"read_bytes\":%d,\"reuse_checked\":%d,\"leaf_seen\":%d,\"growth_checked\":%d}\n",open2,opens,reads,stats,injected,closes,file_closes,parent_closes,walk_closes,next_closes,read_bytes,checked,leaf>=0,growth_checked);
}
