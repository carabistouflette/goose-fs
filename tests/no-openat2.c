/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <sys/syscall.h>
#ifndef GF_DENIED_ERRNO
#define GF_DENIED_ERRNO ENOSYS
#endif
/* Force only the parent walker; preserve the actual rename primitive. */
long __real_syscall(long, ...);
long __wrap_syscall(long number, ...) {
    if (number == SYS_openat2) { errno = GF_DENIED_ERRNO; return -1; }
    assert(number == SYS_renameat2);
    va_list args; va_start(args,number);
    int from = va_arg(args,int); const char *source = va_arg(args,const char *);
    int to = va_arg(args,int); const char *target = va_arg(args,const char *);
    unsigned int flags = va_arg(args,unsigned int); va_end(args);
    return __real_syscall(number,from,source,to,target,flags);
}
