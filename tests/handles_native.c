/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "../native/fs.h"
#include <assert.h>
#include <stdio.h>
/* Include the production unit to seed the otherwise unreachable serial limit.
 * All ordinary behavior is also tested through the independently built .so. */
#include "../native/handles.c"
#include <stdarg.h>
#include <stdlib.h>

static int fault_read, fault_write, fault_close, fault_stat, fault_truncate;
static int fault_sync, fault_seek, fault_dup, calls_read, calls_write, calls_close;
static int fault_lock, calls_lock;
static int fault_sleep, calls_sleep;
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t wake = PTHREAD_COND_INITIALIZER;
static bool block_read, entered_read, release_read;
ssize_t __real_read(int, void *, size_t);
ssize_t __real_pread(int, void *, size_t, off_t);
#ifdef __GLIBC__
ssize_t __real___read_chk(int, void *, size_t, size_t);
ssize_t __real___pread_chk(int, void *, size_t, off_t, size_t);
#endif
ssize_t __real_write(int, const void *, size_t);
ssize_t __real_pwrite(int, const void *, size_t, off_t);
int __real_close(int);
int __real_fstat(int, struct stat *);
int __real_ftruncate(int, off_t);
int __real_fsync(int);
int __real_fdatasync(int);
off_t __real_lseek(int, off_t, int);
int __real_fcntl(int, int, ...);
int __real_flock(int, int);
int __real_nanosleep(const struct timespec *, struct timespec *);
int __wrap_nanosleep(const struct timespec *delay, struct timespec *remaining) {
    ++calls_sleep;
    if (fault_sleep == EINTR) {
        fault_sleep = 0; *remaining = *delay; remaining->tv_nsec /= 2;
        errno = EINTR; return -1;
    }
    if (fault_sleep) { errno = fault_sleep; return -1; }
    return __real_nanosleep(delay,remaining);
}
int __wrap_flock(int fd, int operation) {
    ++calls_lock;
    assert((operation & LOCK_UN) || (operation & LOCK_NB));
    if (fault_lock == EINTR) { fault_lock = 0; errno = EINTR; return -1; }
    if (fault_lock) { errno = fault_lock; return -1; }
    return __real_flock(fd,operation);
}
static ssize_t read_fault(int fd, void *out, size_t n, off_t off, bool positioned) {
    pthread_mutex_lock(&gate);
    if (block_read) {
        entered_read = true; pthread_cond_broadcast(&wake);
        while (!release_read) pthread_cond_wait(&wake, &gate);
    }
    pthread_mutex_unlock(&gate);
    if (fault_read) {
        ++calls_read;
        if (fault_read == 1 && calls_read == 1) { errno = EINTR; return -1; }
        if (fault_read == 2) { errno = EIO; return -1; }
        if (n > 2) n = 2;
    }
    return positioned ? __real_pread(fd, out, n, off) : __real_read(fd, out, n);
}
ssize_t __wrap_read(int fd, void *out, size_t n) { return read_fault(fd,out,n,0,false); }
ssize_t __wrap_pread(int fd, void *out, size_t n, off_t off) { return read_fault(fd,out,n,off,true); }
#ifdef __GLIBC__
ssize_t __wrap___read_chk(int fd, void *out, size_t n, size_t capacity) {
    if (n > capacity) return __real___read_chk(fd,out,n,capacity);
    return read_fault(fd,out,n,0,false);
}
ssize_t __wrap___pread_chk(int fd, void *out, size_t n, off_t off, size_t capacity) {
    if (n > capacity) return __real___pread_chk(fd,out,n,off,capacity);
    return read_fault(fd,out,n,off,true);
}
#endif
static ssize_t write_fault(int fd, const void *data, size_t n, off_t off, bool positioned) {
    if (fault_write) {
        ++calls_write;
        if (fault_write == 1 && calls_write == 1) { errno = EINTR; return -1; }
        if (fault_write == 2 && calls_write > 1) { errno = ENOSPC; return -1; }
        if (fault_write == 3) return 0;
        if (n > 1) n = 1;
    }
    return positioned ? __real_pwrite(fd,data,n,off) : __real_write(fd,data,n);
}
ssize_t __wrap_write(int fd, const void *data, size_t n) { return write_fault(fd,data,n,0,false); }
ssize_t __wrap_pwrite(int fd, const void *data, size_t n, off_t off) { return write_fault(fd,data,n,off,true); }
int __wrap_close(int fd) {
    int rc = __real_close(fd);
    if (fault_close) { ++calls_close; errno = calls_close == 1 ? EINTR : EIO; return -1; }
    return rc;
}
int __wrap_fstat(int fd, struct stat *out) {
    if (fault_stat) { errno = EIO; return -1; }
    return __real_fstat(fd,out);
}
int __wrap_ftruncate(int fd, off_t size) {
    if (fault_truncate) { errno = ENOSPC; return -1; }
    return __real_ftruncate(fd,size);
}
int __wrap_fsync(int fd) {
    if (fault_sync) { if (fault_sync-- == 2) { errno = EINTR; return -1; } errno = EIO; return -1; }
    return __real_fsync(fd);
}
int __wrap_fdatasync(int fd) {
    if (fault_sync) { if (fault_sync-- == 2) { errno = EINTR; return -1; } errno = EIO; return -1; }
    return __real_fdatasync(fd);
}
off_t __wrap_lseek(int fd, off_t offset, int origin) {
    if (fault_seek) { errno = EIO; return -1; }
    return __real_lseek(fd,offset,origin);
}
int __wrap_fcntl(int fd, int cmd, ...) {
    assert(cmd == F_DUPFD_CLOEXEC);
    va_list args; va_start(args,cmd); int value = va_arg(args,int); va_end(args);
    if (fault_dup) { errno = EMFILE; return -1; }
    return __real_fcntl(fd,cmd,value);
}
static gf_meta meta(int64_t out[3]) { return (gf_meta){out,3}; }
static gf_input input(const char *text) { return (gf_input){(const uint8_t *)text,(int64_t)strlen(text)}; }
static int64_t make_context(void) {
    int64_t out[3]; assert(!gf_context_create(meta(out))); assert(!out[0]); return out[1];
}
static int64_t open_handle(int64_t ctx, const char *path) {
    int64_t out[3]; assert(!gf_file_open(ctx,input(path),2,0600,meta(out))); return out[1];
}
static int64_t threaded_context, threaded_file;
static void *reader(void *unused) {
    (void)unused; uint8_t data[6]; int64_t out[3];
    assert(!gf_file_read(threaded_context,threaded_file,(gf_output){data,6},0,true,meta(out)));
    assert(out[1] == 6 && !memcmp(data,"abcdef",6)); return NULL;
}
static void *closer(void *unused) {
    (void)unused; int64_t out[3]; assert(!gf_context_close(threaded_context,meta(out))); return NULL;
}
int main(int argc, char **argv) {
    assert(argc == 2); char path[4096];
    assert(snprintf(path,sizeof path,"%s/file",argv[1]) > 0);
    int fd = open(path,O_CREAT|O_EXCL|O_WRONLY|O_CLOEXEC,0600); assert(fd >= 0);
    assert(__real_write(fd,"abcdef",6) == 6); assert(!__real_close(fd));
    int64_t ctx=make_context(), out[3], file=open_handle(ctx,path); uint8_t data[8];
    fault_lock=EINTR; calls_lock=0;
    assert(!gf_file_try_lock(ctx,file,2,meta(out)) && calls_lock == 2);
    assert(!gf_file_try_lock(ctx,file,0,meta(out)));
    int errors[] = { EAGAIN, EACCES, ENOLCK, EIO };
    for (size_t i=0; i<sizeof errors/sizeof *errors; ++i) {
        fault_lock=errors[i]; calls_lock=0;
        assert(gf_file_try_lock(ctx,file,1,meta(out)) == GF_SYSTEM);
        assert(out[0] == errors[i] && !out[1] && !out[2] && calls_lock == 1);
    }
    fault_lock=0;
    fault_sleep=EINTR; calls_sleep=0;
    assert(!gf_lock_pause() && calls_sleep == 2);
    fault_sleep=EPERM; calls_sleep=0;
    assert(gf_lock_pause() == EPERM && calls_sleep == 1);
    fault_sleep=0;
    for (int positioned = 0; positioned < 2; ++positioned) {
        fault_read=1; calls_read=0;
        assert(!gf_file_read(ctx,file,(gf_output){data,6},0,positioned,meta(out)));
        assert(out[1] == 2 && !out[2] && calls_read == 2);
        fault_read=2;
        assert(gf_file_read(ctx,file,(gf_output){data,6},0,positioned,meta(out)) == GF_SYSTEM);
        assert(out[0] == EIO && !out[1] && !out[2]); fault_read=0;
        fault_write=1; calls_write=0;
        assert(!gf_file_write(ctx,file,input("ABC"),0,positioned,true,meta(out)));
        assert(out[1] == 3 && calls_write == 4);
        fault_write=2; calls_write=0;
        assert(gf_file_write(ctx,file,input("DEF"),0,positioned,true,meta(out)) == GF_SYSTEM);
        assert(out[0] == ENOSPC && out[1] == 1);
        fault_write=3; calls_write=0;
        assert(gf_file_write(ctx,file,input("G"),0,positioned,false,meta(out)) == GF_SYSTEM);
        assert(out[0] == EIO && !out[1]); fault_write=0;
    }
    fault_dup=1; assert(gf_file_duplicate(ctx,file,meta(out)) == GF_SYSTEM && out[0] == EMFILE && !out[1]); fault_dup=0;
    assert(!gf_file_duplicate(ctx,file,meta(out))); assert(!gf_file_close(ctx,out[1],meta(out)));
    fault_seek=1; assert(gf_file_seek(ctx,file,0,0,meta(out)) == GF_SYSTEM && out[0] == EIO); fault_seek=0;
    fault_truncate=1; assert(gf_file_truncate(ctx,file,0,meta(out)) == GF_SYSTEM && out[0] == ENOSPC); fault_truncate=0;
    for (int data_only=0; data_only<2; ++data_only) {
        fault_sync=2; assert(gf_file_sync(ctx,file,data_only,meta(out)) == GF_SYSTEM && out[0] == EIO && !fault_sync);
    }
    fault_stat=1; assert(gf_file_open(ctx,input(path),2|32,0600,meta(out)) == GF_SYSTEM && out[0] == EIO); fault_stat=0;
    struct stat st; assert(!stat(path,&st) && st.st_size > 0);
    fault_truncate=1; assert(gf_file_open(ctx,input(path),2|32,0600,meta(out)) == GF_SYSTEM && out[0] == ENOSPC); fault_truncate=0;
    fault_close=1; calls_close=0;
    assert(gf_file_close(ctx,file,meta(out)) == GF_SYSTEM && out[0] == EINTR && calls_close == 1); fault_close=0;
    assert(gf_file_close(ctx,file,meta(out)) == GF_SYSTEM && out[0] == EBADF);
    int64_t f1=open_handle(ctx,path), f2=open_handle(ctx,path);
    fault_close=1; calls_close=0;
    assert(gf_context_close(ctx,meta(out)) == GF_SYSTEM && out[0] == EINTR && calls_close == 2); fault_close=0;
    assert(gf_file_close(ctx,f1,meta(out)) == GF_SYSTEM && out[0] == EBADF);
    assert(gf_file_close(ctx,f2,meta(out)) == GF_SYSTEM && out[0] == EBADF);
    /* An empty unrelated context must not wait on blocked I/O's entry lock. */
    threaded_context=make_context(); threaded_file=open_handle(threaded_context,path);
    int raw=open(path,O_WRONLY|O_TRUNC); assert(raw >= 0); assert(__real_write(raw,"abcdef",6) == 6); assert(!__real_close(raw));
    int64_t unrelated=make_context(); pthread_t r,w;
    block_read=true; assert(!pthread_create(&r,NULL,reader,NULL));
    pthread_mutex_lock(&gate); while (!entered_read) pthread_cond_wait(&wake,&gate); pthread_mutex_unlock(&gate);
    assert(!gf_context_close(unrelated,meta(out)));
    assert(!pthread_create(&w,NULL,closer,NULL));
    pthread_mutex_lock(&gate); release_read=true; pthread_cond_broadcast(&wake); pthread_mutex_unlock(&gate);
    assert(!pthread_join(r,NULL)); assert(!pthread_join(w,NULL)); block_read=false;
    /* Saturation cannot wrap IDs or mutate a target; existing tokens still work. */
    ctx=make_context(); file=open_handle(ctx,path);
    serial=(uint64_t)INT64_MAX >> SLOT_BITS;
    assert(gf_context_create(meta(out)) == GF_LIMIT && !out[0] && !out[1]);
    assert(gf_file_open(ctx,input(path),2|32,0600,meta(out)) == GF_LIMIT && !out[0] && !out[1]);
    assert(!stat(path,&st) && st.st_size == 6);
    assert(gf_file_duplicate(ctx,file,meta(out)) == GF_LIMIT && !out[0]);
    assert(!gf_file_read(ctx,file,(gf_output){data,6},0,true,meta(out)) && out[1] == 6);
    assert(!gf_context_close(ctx,meta(out)));
    assert(!unlink(path)); puts("retained-handle injected failures, cleanup, blocked-I/O isolation and generation saturation passed");
}
