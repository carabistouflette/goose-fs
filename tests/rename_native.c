/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "../native/handles.c"
#include <assert.h>
#include <dirent.h>
#include <linux/openat2.h>
#include <stdarg.h>
#include <stdio.h>
#include <sys/syscall.h>

#ifndef GF_RENAME_FORCE_FALLBACK
#define GF_RENAME_FORCE_FALLBACK 0
#endif
static int force_walk, rename_mode, rename_calls, replace_calls, no_replace_calls;
static int sync_mode, sync_calls, readable_fail_at, readable_calls;
static int close_at, close_calls, close_after_rename, reuse_on_close, reused = -1, fail_walk_open, target_opens;
long __real_syscall(long,...);
int __real_renameat(int,const char *,int,const char *);
int __real_openat(int,const char *,int,...);
int __real_close(int);
int __real_fsync(int);
static int injected_rename(int from,const char *source,int to,const char *target,unsigned flags,bool no_replace) {
    ++rename_calls;
    if (rename_mode == 1 || rename_mode == 3 || rename_mode == 4) {
        errno = rename_mode == 3 ? EINTR : rename_mode == 4 ? ENOSYS : EIO; return -1;
    }
    int rc = no_replace ? (int)__real_syscall(SYS_renameat2,from,source,to,target,flags) : __real_renameat(from,source,to,target);
    if (!rc && rename_mode == 2) { errno = EIO; return -1; }
    return rc;
}
long __wrap_syscall(long number,...) {
    va_list args;va_start(args,number);
    if (number == SYS_openat2) {
        int dir=va_arg(args,int);const char *path=va_arg(args,const char *);
        struct open_how *how=va_arg(args,struct open_how *);size_t size=va_arg(args,size_t);va_end(args);
        assert(how->flags & O_CLOEXEC);
        if (force_walk || GF_RENAME_FORCE_FALLBACK) { errno=ENOSYS;return -1; }
        return __real_syscall(number,dir,path,how,size);
    }
    assert(number == SYS_renameat2);
    int from=va_arg(args,int);const char *source=va_arg(args,const char *);
    int to=va_arg(args,int);const char *target=va_arg(args,const char *);
    unsigned flags=va_arg(args,unsigned);va_end(args);
    assert(flags == 1);++no_replace_calls;
    return injected_rename(from,source,to,target,flags,true);
}
int __wrap_renameat(int from,const char *source,int to,const char *target) {
    ++replace_calls;return injected_rename(from,source,to,target,0,false);
}
int __wrap_openat(int dir,const char *path,int flags,...) {
    assert(flags & O_CLOEXEC);
    int mode=0;if (flags&O_CREAT) { va_list args;va_start(args,flags);mode=va_arg(args,int);va_end(args); }
    if (flags&O_PATH) {
        if (fail_walk_open) { errno=EACCES;return -1; }
    } else {
        ++target_opens;
        if ((flags&O_DIRECTORY) && !strcmp(path,".")) {
            ++readable_calls;
            if (readable_fail_at==readable_calls) { errno=EACCES;return -1; }
        }
    }
    return __real_openat(dir,path,flags,mode);
}
int __wrap_fsync(int fd) {
    assert(!(fcntl(fd,F_GETFL)&O_PATH) && (fcntl(fd,F_GETFD)&FD_CLOEXEC));
    ++sync_calls;
    if ((sync_mode==1 && sync_calls==1) || (sync_mode==3 && sync_calls==2)) { errno=EIO;return -1; }
    if (sync_mode==2 && sync_calls==1) { errno=EINTR;return -1; }
    return __real_fsync(fd);
}
int __wrap_close(int fd) {
    int rc=__real_close(fd);
    if (close_after_rename && !rename_calls) return rc;
    ++close_calls;
    if (close_at && close_calls==close_at) {
        if (reuse_on_close) {
            int temp=open("/dev/null",O_RDONLY|O_CLOEXEC);assert(temp>=0);
            if (temp!=fd) { assert(dup3(temp,fd,O_CLOEXEC)==fd);assert(!__real_close(temp)); }
            reused=fd;
        }
        errno=EINTR;return -1;
    }
    return rc;
}
static gf_input text(const char *s) { return (gf_input){(const uint8_t *)s,(int64_t)strlen(s)}; }
static gf_meta three(int64_t *m) { return (gf_meta){m,3}; }
static int fd_count(void) {
    DIR *dir=opendir("/proc/self/fd");assert(dir);int n=0;while(readdir(dir))++n;assert(!closedir(dir));return n;
}
static void disarm(void) {
    force_walk=rename_mode=rename_calls=replace_calls=no_replace_calls=sync_mode=sync_calls=0;
    readable_fail_at=readable_calls=close_at=close_calls=close_after_rename=reuse_on_close=fail_walk_open=target_opens=0;
}
static void prepare(int dir) {
    disarm();unlinkat(dir,"source",0);unlinkat(dir,"target",0);
    int fd=__real_openat(dir,"source",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);assert(fd>=0);
    assert(write(fd,"new",3)==3 && !__real_close(fd));
}
static bool present(int dir,const char *name) { struct stat st;return fstatat(dir,name,&st,AT_SYMLINK_NOFOLLOW)==0; }
static int invoke(bool rooted,int64_t ctx,int64_t root,const char *source,const char *target,int flags,int64_t *m) {
    return (int)(rooted ? gf_root_rename(ctx,root,text("source"),text("target"),flags,(gf_meta){m,4}) :
                         gf_rename(text(source),text(target),flags,(gf_meta){m,4}));
}
int main(int argc,char **argv) {
    assert(argc==2);int before=fd_count();int64_t old[3],m[4];
    assert(!gf_context_create(three(old)));int64_t ctx=old[1];
    assert(!gf_root_open(ctx,text(argv[1]),three(old)));int64_t root=old[1];int dir=resources[root&(RESOURCES-1)].fd;
    char source[4096],target[4096],nested[4096],created[4096];
    assert(snprintf(source,sizeof source,"%s/source",argv[1])>0);
    assert(snprintf(target,sizeof target,"%s/target",argv[1])>0);
    assert(snprintf(nested,sizeof nested,"%s/nested/source",argv[1])>0);
    assert(snprintf(created,sizeof created,"%s/nested/created",argv[1])>0);
    assert(!mkdirat(dir,"nested",0700));int held=fd_count();
    for (int rooted=0;rooted<2;++rooted) {
        for (int flags=0;flags<4;++flags) {
            prepare(dir);assert(!invoke(rooted,ctx,root,source,target,flags,m));
            assert(!m[0] && m[1]==1 && m[2]==!!(flags&2) && !m[3]);
            assert(rename_calls==1 && sync_calls==((flags&2)?2:0));
            assert((flags&1)?no_replace_calls==1&&!replace_calls:replace_calls==1&&!no_replace_calls);
            assert(!present(dir,"source") && present(dir,"target"));assert(fd_count()==held);
            for (int mode=1;mode<=4;++mode) {
                prepare(dir);rename_mode=mode;
                assert(invoke(rooted,ctx,root,source,target,flags,m)==GF_SYSTEM);
                assert(m[0]==(mode==3?EINTR:mode==4?ENOSYS:EIO) && m[1]==2 && !m[2] && !m[3]);
                assert(rename_calls==1 && !sync_calls);
                assert(present(dir,"target")== (mode==2) && present(dir,"source")== (mode!=2));
                assert(fd_count()==held);
            }
        }
        for (int nth=1;nth<=2;++nth) {
            prepare(dir);readable_fail_at=nth;
            assert(invoke(rooted,ctx,root,source,target,2,m)==GF_SYSTEM && m[0]==EACCES && !m[1] && !m[2] && !m[3]);
            assert(!rename_calls && present(dir,"source") && !present(dir,"target"));assert(fd_count()==held);
        }
        for (int mode=1;mode<=3;++mode) {
            prepare(dir);sync_mode=mode;
            assert(invoke(rooted,ctx,root,source,target,2,m)==(mode==2?GF_OK:GF_SYSTEM));
            assert(m[0]==(mode==2?0:EIO) && m[1]==1 && m[2]==(mode==2) && !m[3]);
            assert(sync_calls==(mode==2?3:2) && rename_calls==1);assert(fd_count()==held);
        }
        for (int sync=0;sync<2;++sync) {
            for (int nth=1;nth<=(sync?4:2);++nth) {
                prepare(dir);close_at=nth;close_after_rename=1;reuse_on_close=1;
                assert(invoke(rooted,ctx,root,source,target,sync?2:0,m)==GF_SYSTEM);
                assert(m[0]==EINTR && m[1]==1 && m[2]==sync && m[3]==EINTR);
                assert(fcntl(reused,F_GETFD)&FD_CLOEXEC);assert(!__real_close(reused));reused=-1;
                assert(fd_count()==held);
            }
        }
        for (int primary=0;primary<2;++primary) {
            for (int nth=1;nth<=4;++nth) {
                prepare(dir);close_at=nth;close_after_rename=1;
                if (primary) sync_mode=1; else rename_mode=1;
                assert(invoke(rooted,ctx,root,source,target,2,m)==GF_SYSTEM);
                assert(m[0]==EIO && m[1]==(primary?1:2) && !m[2] && m[3]==EINTR);
                assert(fd_count()==held);
            }
        }
        // Failed next-open wins over the intermediate close error, but both survive.
        prepare(dir);force_walk=1;fail_walk_open=1;close_at=1;
        int rc=rooted ? (int)gf_root_rename(ctx,root,text("nested/source"),text("target"),0,(gf_meta){m,4}) :
                        (int)gf_rename(text(nested),text(target),0,(gf_meta){m,4});
        assert(rc==GF_SYSTEM && m[0]==EACCES && !m[1] && !m[2] && m[3]==EINTR && !rename_calls);
        disarm();assert(fd_count()==held);
        // Successful next-open plus failed old-close aborts and closes next once.
        force_walk=1;close_at=1;reuse_on_close=1;
        rc=rooted ? (int)gf_root_rename(ctx,root,text("nested/source"),text("target"),0,(gf_meta){m,4}) :
                    (int)gf_rename(text(nested),text(target),0,(gf_meta){m,4});
        assert(rc==GF_SYSTEM && m[0]==EINTR && !m[1] && !m[2] && m[3]==EINTR && !rename_calls);
        assert(fcntl(reused,F_GETFD)>=0);assert(!__real_close(reused));reused=-1;disarm();assert(fd_count()==held);
        for (int operand=0;operand<2;++operand) {
            for(int i=0;i<4;++i)m[i]=165;
            gf_input a=operand ? text(rooted?"source":source) : (gf_input){(uint8_t *)&m[3],1};
            gf_input b=operand ? (gf_input){(uint8_t *)&m[3],1} : text(rooted?"target":target);
            rc=rooted ? (int)gf_root_rename(ctx,root,a,b,0,(gf_meta){m,4}) : (int)gf_rename(a,b,0,(gf_meta){m,4});
            assert(rc==GF_INVALID);for(int i=0;i<4;++i)assert(m[i]==165);
        }
    }
    // Shared walker change also protects legacy read/list/create and typed metadata.
    for (int op=0;op<=2;++op) {
        disarm();force_walk=1;close_at=1;uint8_t bytes[32];int64_t legacy[3];
        const char *path=op==2?created:nested;
        assert(gf_call(op,text(path),text(op==2?"new":""),4,(gf_output){bytes,32},three(legacy))==GF_SYSTEM);
        assert(legacy[0]==EINTR && !legacy[1] && !legacy[2] && !target_opens);
        disarm();assert(!present(dir,"nested/created") && fd_count()==held);
    }
    force_walk=1;close_at=1;int64_t fields[18];
    assert(gf_metadata(text(nested),(gf_meta){fields,18})==GF_SYSTEM && fields[0]==EINTR && !target_opens);
    disarm();assert(fd_count()==held);
    assert(!gf_root_metadata(ctx,root,(gf_meta){fields,18}));
    assert(!gf_context_close(ctx,three(old)));assert(fd_count()==before);
    puts("rename uncertainty/sync/cleanup faults, fd reuse, metadata guards and legacy walker close errors passed");
}
