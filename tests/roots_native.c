/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "../native/handles.c"
#include <assert.h>
#include <dirent.h>
#include <linux/openat2.h>
#include <stdarg.h>
#include <stdio.h>
#include <sys/syscall.h>

static int tracked_root = -1, lookup_error, dup_error, open_error, stat_error, truncate_error, close_error;
static int parent_calls, fallback_calls, close_calls;
long __real_syscall(long, ...);
int __real_openat(int, const char *, ...);
int __real_fcntl(int, int, ...);
int __real_fstat(int, struct stat *);
int __real_ftruncate(int, off_t);
int __real_close(int);
long __wrap_syscall(long number, ...) {
    assert(number == SYS_openat2);
    va_list args; va_start(args,number);
    int dir=va_arg(args,int); const char *path=va_arg(args,const char *);
    struct open_how *how=va_arg(args,struct open_how *); size_t size=va_arg(args,size_t);va_end(args);
    assert(how->flags & O_CLOEXEC);
    if (dir == tracked_root) {
        ++parent_calls; assert(!strcmp(path,"child"));
        assert(how->resolve == (RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS));
        assert(how->flags == (O_PATH | O_DIRECTORY | O_CLOEXEC));
        if (lookup_error) { errno=lookup_error; return -1; }
    }
    return __real_syscall(number,dir,path,how,size);
}
int __wrap_openat(int dir, const char *path, int flags, ...) {
    int mode=0;
    if (flags & O_CREAT) { va_list args;va_start(args,flags);mode=va_arg(args,int);va_end(args); }
    assert(flags & O_CLOEXEC);
    if ((flags & O_PATH) && !strcmp(path,"child")) {
        struct stat parent,root;
        assert(!__real_fstat(dir,&parent) && !__real_fstat(tracked_root,&root));
        assert(parent.st_dev == root.st_dev && parent.st_ino == root.st_ino);
        ++fallback_calls; assert(flags == (O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
    }
    if (open_error && !(flags & O_PATH)) { errno=open_error;return -1; }
    return __real_openat(dir,path,flags,mode);
}
int __wrap_fcntl(int fd, int command, ...) {
    assert(command == F_DUPFD_CLOEXEC);
    va_list args;va_start(args,command);int lower=va_arg(args,int);va_end(args);
    if (dup_error) { errno=dup_error;return -1; }
    int result=__real_fcntl(fd,command,lower);
    if (result >= 0) assert(__real_fcntl(result,F_GETFD) & FD_CLOEXEC);
    return result;
}
int __wrap_fstat(int fd, struct stat *out) {
    if (stat_error) { errno=stat_error;return -1; }
    return __real_fstat(fd,out);
}
int __wrap_ftruncate(int fd, off_t size) {
    if (truncate_error) { errno=truncate_error;return -1; }
    return __real_ftruncate(fd,size);
}
int __wrap_close(int fd) {
    int rc=__real_close(fd);
    if (close_error && fd == tracked_root) { ++close_calls;errno=close_error;return -1; }
    return rc;
}
static gf_meta meta(int64_t out[3]) { return (gf_meta){out,3}; }
static gf_input text(const char *value) { return (gf_input){(const uint8_t *)value,(int64_t)strlen(value)}; }
static int descriptors(void) {
    DIR *dir=opendir("/proc/self/fd");assert(dir);int n=0;while (readdir(dir)) ++n;assert(!closedir(dir));return n;
}
int main(int argc, char **argv) {
    assert(argc == 2);int before=descriptors();int64_t out[3],fields[18];uint8_t bytes[16];
    assert(!gf_context_create(meta(out)));int64_t ctx=out[1];
    assert(!gf_root_open(ctx,text(argv[1]),meta(out)));int64_t root=out[1];
    tracked_root=resources[root & (RESOURCES-1)].fd;
    assert(!gf_root_mkdir(ctx,root,text("child"),meta(out)));
    assert(!gf_root_create(ctx,root,text("child/file"),text("safe"),meta(out)));
    int owned=descriptors();
    int errors[]={EINVAL,EXDEV,EAGAIN,ELOOP,EACCES};
    for (size_t i=0;i<sizeof errors/sizeof *errors;++i) {
        lookup_error=errors[i];parent_calls=fallback_calls=0;
        assert(gf_root_read(ctx,root,text("child/file"),(gf_output){bytes,4},meta(out)) == GF_SYSTEM);
        assert(out[0] == errors[i] && !out[1] && parent_calls == 1 && !fallback_calls);
        assert(descriptors() == owned);
    }
    int fallback[]={ENOSYS,EPERM};
    for (size_t i=0;i<sizeof fallback/sizeof *fallback;++i) {
        lookup_error=fallback[i];parent_calls=fallback_calls=0;
        assert(!gf_root_read(ctx,root,text("child/file"),(gf_output){bytes,4},meta(out)));
        assert(out[1] == 4 && !memcmp(bytes,"safe",4) && parent_calls == 1 && fallback_calls == 1);
        assert(descriptors() == owned);
    }
    lookup_error=0;dup_error=EMFILE;
    assert(gf_root_read(ctx,root,text("."),(gf_output){bytes,4},meta(out)) == GF_SYSTEM && out[0] == EMFILE);
    assert(gf_root_open_at(ctx,root,text("."),meta(out)) == GF_SYSTEM && out[0] == EMFILE && !out[1]);
    dup_error=0;assert(descriptors() == owned);
    open_error=EIO;
    assert(gf_file_open_at(ctx,root,text("child/file"),2,0600,meta(out)) == GF_SYSTEM && out[0] == EIO && !out[1]);
    open_error=0;assert(descriptors() == owned);
    stat_error=EIO;
    assert(gf_file_open_at(ctx,root,text("child/file"),2|32,0600,meta(out)) == GF_SYSTEM && out[0] == EIO && !out[1]);
    stat_error=0;truncate_error=ENOSPC;
    assert(gf_file_open_at(ctx,root,text("child/file"),2|32,0600,meta(out)) == GF_SYSTEM && out[0] == ENOSPC && !out[1]);
    truncate_error=0;assert(descriptors() == owned);
    assert(!gf_root_read(ctx,root,text("child/file"),(gf_output){bytes,4},meta(out)) && !memcmp(bytes,"safe",4));
    assert(!gf_file_open_at(ctx,root,text("child/file"),0,0600,meta(out)));int64_t file=out[1];
    assert(!gf_root_metadata(ctx,root,(gf_meta){fields,18}));assert(fields[1] == 2);
    assert(gf_root_read(ctx,root,text("child/file"),(gf_output){(uint8_t *)out,4},meta(out)) == GF_INVALID);
    assert(gf_root_metadata_at(ctx,root,(gf_input){(uint8_t *)fields,4},(gf_meta){fields,18}) == GF_INVALID);
    close_error=EINTR;close_calls=0;
    assert(gf_root_close(ctx,root,meta(out)) == GF_SYSTEM && out[0] == EINTR && close_calls == 1);
    close_error=0;
    assert(gf_root_close(ctx,root,meta(out)) == GF_SYSTEM && out[0] == EBADF);
    assert(!gf_file_read(ctx,file,(gf_output){bytes,4},0,true,meta(out)) && !memcmp(bytes,"safe",4));
    assert(!gf_context_close(ctx,meta(out)));assert(descriptors() == before);
    puts("Root resolver flags/fallback/error injection, cleanup, kind/lifetime and CLOEXEC checks passed");
}
