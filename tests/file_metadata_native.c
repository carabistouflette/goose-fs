/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "../native/handles.c"
#include <assert.h>
#include <stdio.h>
static int operation, fault, calls;
static int64_t expected_uid, expected_gid, expected_seconds[2], expected_nanos[2];
int __real_fchmod(int,mode_t);
int __real_fchown(int,uid_t,gid_t);
int __real_futimens(int,const struct timespec[2]);
static int error_before(void) {
    ++calls;
    if (fault==1 || fault==2 || fault==3) { errno=fault==1?EINTR:fault==2?EIO:EPERM;return -1; }
    return 0;
}
static int error_after(int rc) { if (!rc && fault==4) { errno=EIO;return -1; } return rc; }
int __wrap_fchmod(int fd,mode_t mode) {
    assert(operation==0 && mode==0640);
    if (error_before()) return -1;
    return error_after(__real_fchmod(fd,mode));
}
int __wrap_fchown(int fd,uid_t uid,gid_t gid) {
    assert(operation==1 && uid==(uid_t)expected_uid && gid==(gid_t)expected_gid);
    if (error_before()) return -1;
    return error_after(__real_fchown(fd,uid,gid));
}
int __wrap_futimens(int fd,const struct timespec times[2]) {
    assert(operation==2);
    for (int i=0;i<2;++i) assert(times[i].tv_sec==expected_seconds[i] && times[i].tv_nsec==expected_nanos[i]);
    if (error_before()) return -1;
    return error_after(__real_futimens(fd,times));
}
static gf_meta meta(int64_t *m) { return (gf_meta){m,3}; }
static gf_input text(const char *s) { return (gf_input){(const uint8_t *)s,(int64_t)strlen(s)}; }
static int mutate(int64_t ctx,int64_t file,int64_t *m) {
    if (operation==0) return (int)gf_file_set_permissions(ctx,file,0640,meta(m));
    if (operation==1) return (int)gf_file_set_owner(ctx,file,-1,-1,meta(m));
    return (int)gf_file_set_times(ctx,file,2,-2,123456789,2,2200000000,987654321,meta(m));
}
int main(int argc,char **argv) {
    assert(argc==2);char path[4096];assert(snprintf(path,sizeof path,"%s/file",argv[1])>0);
    int64_t m[3];assert(!gf_context_create(meta(m)));int64_t ctx=m[1];
    assert(!gf_file_open(ctx,text(path),4,0600,meta(m)));int64_t file=m[1];
    int fd=resources[file&(RESOURCES-1)].fd;
    assert(write(fd,"unchanged",9)==-1 && errno==EBADF); // Read-only creation is intentional.
    assert(lseek(fd,3,SEEK_SET)==3);
    expected_uid=expected_gid=-1;
    expected_seconds[0]=-2;expected_seconds[1]=2200000000;
    expected_nanos[0]=123456789;expected_nanos[1]=987654321;
    for (operation=0;operation<3;++operation) {
        for (int mode=1;mode<=4;++mode) {
            assert(!__real_fchmod(fd,0600));
            struct timespec initial[2]={{.tv_sec=10,.tv_nsec=0},{.tv_sec=20,.tv_nsec=0}};
            assert(!__real_futimens(fd,initial));fault=mode;calls=0;
            assert(mutate(ctx,file,m)==GF_SYSTEM && calls==1);
            assert(m[0]==(mode==1?EINTR:mode==3?EPERM:EIO) && !m[1] && !m[2]);
            if (operation==0 && mode==4) { struct stat st;assert(!fstat(fd,&st) && (st.st_mode&07777)==0640); }
            if (operation==2 && mode==4) {
                struct stat st;assert(!fstat(fd,&st));
                assert(st.st_atim.tv_sec==-2 && st.st_atim.tv_nsec==123456789);
                assert(st.st_mtim.tv_sec==2200000000 && st.st_mtim.tv_nsec==987654321);
            }
            fault=0;calls=0;assert(!mutate(ctx,file,m) && calls==1 && !m[0]);
        }
    }
    assert(lseek(fd,0,SEEK_CUR)==3);
    operation=2;fault=0;calls=0;
    expected_seconds[0]=expected_seconds[1]=0;expected_nanos[0]=UTIME_OMIT;expected_nanos[1]=UTIME_NOW;
    assert(!gf_file_set_times(ctx,file,0,INT64_MIN,INT64_MIN,1,INT64_MAX,INT64_MAX,meta(m)) && calls==1);
    calls=0;
    assert(gf_file_set_permissions(ctx,file,-1,meta(m))==GF_INVALID);
    assert(gf_file_set_permissions(ctx,file,010000,meta(m))==GF_INVALID);
    assert(gf_file_set_owner(ctx,file,-2,-1,meta(m))==GF_INVALID);
    assert(gf_file_set_owner(ctx,file,-1,UINT32_MAX,meta(m))==GF_INVALID);
    assert(gf_file_set_times(ctx,file,2,0,-1,0,0,0,meta(m))==GF_INVALID);
    assert(gf_file_set_times(ctx,file,0,0,0,2,0,1000000000,meta(m))==GF_INVALID);
    assert(gf_file_set_times(ctx,file,3,0,0,0,0,0,meta(m))==GF_INVALID && !calls);
    assert(!m[0] && !m[1] && !m[2]);
    assert(!gf_root_open(ctx,text(argv[1]),meta(m)));int64_t root=m[1];
    for (operation=0;operation<3;++operation) {
        calls=0;assert(mutate(ctx,root,m)==GF_SYSTEM && m[0]==EBADF && !calls);
    }
    assert(!gf_file_close(ctx,file,meta(m)));
    for (operation=0;operation<3;++operation) {
        calls=0;assert(mutate(ctx,file,m)==GF_SYSTEM && m[0]==EBADF && !calls);
    }
    assert(!gf_context_close(ctx,meta(m)));
    puts("File metadata single-call errors, effect-then-EIO, lock recovery, ignored times and token guards passed");
}
