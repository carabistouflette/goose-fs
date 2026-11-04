/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "../native/fs_internal.h"
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <unistd.h>
static int synthetic, position, read_error, stream_error, parent_error, open_error, fdopen_error;
struct dirent *__real_readdir(DIR *);
int __real_closedir(DIR *);
int __real_close(int);
int __real_openat(int,const char *,...);
DIR *__real_fdopendir(int);
struct dirent *__wrap_readdir(DIR *dir) {
    if (!synthetic) return __real_readdir(dir);
    static struct dirent entry;
    if (position==2) { errno=read_error;return NULL; }
    memset(&entry,0,sizeof entry);entry.d_type=DT_REG;
    memset(entry.d_name,position ? 'b' : 'a',position ? 1 : 100);
    ++position;return &entry;
}
int __wrap_closedir(DIR *dir) {
    int rc=__real_closedir(dir);
    if (stream_error) { errno=stream_error;return -1; }
    return rc;
}
int __wrap_close(int fd) {
    int rc=__real_close(fd);
    if (parent_error) { errno=parent_error;return -1; }
    return rc;
}
int __wrap_openat(int dir,const char *path,int flags,...) {
    if (open_error && !(flags&O_PATH)) { errno=open_error;return -1; }
    int mode=0;if (flags&O_CREAT) { va_list args;va_start(args,flags);mode=va_arg(args,int);va_end(args); }
    return __real_openat(dir,path,flags,mode);
}
DIR *__wrap_fdopendir(int fd) {
    if (fdopen_error) { errno=fdopen_error;return NULL; }
    return __real_fdopendir(fd);
}
static gf_input text(const char *s) { return (gf_input){(const uint8_t *)s,(int64_t)strlen(s)}; }
static int fds(void) {
    DIR *dir=opendir("/proc/self/fd");assert(dir);int count=0;
    while (__real_readdir(dir)) ++count;
    assert(!__real_closedir(dir));return count;
}
int main(int argc,char **argv) {
    assert(argc==2);int before=fds();int64_t old[3],m[4];
    assert(!gf_context_create((gf_meta){old,3}));int64_t ctx=old[1];
    assert(!gf_root_open(ctx,text(argv[1]),(gf_meta){old,3}));int64_t root=old[1];
    int held=fds();uint8_t out[66];gf_output stage={out+1,64};gf_meta meta={m,4};
    synthetic=1;
    for (int rooted=0;rooted<2;++rooted) {
        for (int fault=0;fault<6;++fault) {
            memset(out,0xcc,sizeof out);position=0;
            read_error=fault==1 ? EIO : 0;stream_error=fault==2 ? EIO : 0;
            parent_error=fault==3 ? EINTR : 0;open_error=fault==4 ? EACCES : 0;fdopen_error=fault==5 ? ENOMEM : 0;
            int64_t code=rooted ? gf_root_list_sized(ctx,root,text("."),105,stage,2,meta) : gf_list(text(argv[1]),105,stage,2,meta);
            assert(code==(fault ? GF_SYSTEM : GF_NEED_SPACE));
            assert(m[0]==(fault==3 ? EINTR : fault==4 ? EACCES : fault==5 ? ENOMEM : fault ? EIO : 0));
            assert(!m[1] && !m[2] && m[3]==(fault ? 0 : 105));
            for (size_t i=0;i<sizeof out;++i) assert(out[i]==0xcc); /* No writes resume after spill. */
            read_error=stream_error=parent_error=open_error=fdopen_error=0;
            assert(fds()==held);
        }
        for (int budget=0;budget<2;++budget) {
            position=0;
            int64_t code=rooted ? gf_root_list_sized(ctx,root,text("."),budget ? 104 : 105,stage,budget ? 2 : 1,meta) : gf_list(text(argv[1]),budget ? 104 : 105,stage,budget ? 2 : 1,meta);
            assert(code==GF_LIMIT && !m[0] && !m[1] && !m[2] && !m[3]);
        }
    }
    synthetic=0;
    // Reject aliases covering the fourth slot before clearing metadata.
    for (int rooted=0;rooted<2;++rooted) {
        for (int alias=0;alias<2;++alias) {
            for (int i=0;i<4;++i) m[i]=165;
            gf_input path=alias ? (gf_input){(uint8_t *)&m[3],1} : text(rooted ? "." : argv[1]);
            gf_output output=alias ? stage : (gf_output){(uint8_t *)&m[3],8};
            int64_t code=rooted ? gf_root_list_sized(ctx,root,path,105,output,2,meta) : gf_list(path,105,output,2,meta);
            assert(code==GF_INVALID);for(int i=0;i<4;++i) assert(m[i]==165);
        }
        for (int len=3;len<=5;len+=2) {
            for(int i=0;i<4;++i) m[i]=165;
            int64_t code=rooted ? gf_root_list_sized(ctx,root,text("."),105,stage,2,(gf_meta){m,len}) : gf_list(text(argv[1]),105,stage,2,(gf_meta){m,len});
            assert(code==GF_INVALID);for(int i=0;i<4;++i) assert(m[i]==165);
        }
        assert((rooted ? gf_root_list_sized(ctx,root,text("."),63,stage,2,meta) : gf_list(text(argv[1]),63,stage,2,meta))==GF_INVALID);
        assert(!m[0] && !m[1] && !m[2] && !m[3]);
    }
    assert(!gf_context_close(ctx,(gf_meta){old,3}));assert(fds()==before);
    puts("listing spill/limits/read/open/fdopendir/stream-close/parent-close faults and meta4 guards passed");
}
