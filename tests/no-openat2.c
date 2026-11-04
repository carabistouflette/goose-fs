/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <sys/syscall.h>
#ifndef GF_DENIED_ERRNO
#define GF_DENIED_ERRNO ENOSYS
#endif
/* The native kernel currently uses syscall only for openat2. Force the real
 * descriptor walker without exposing a production test switch or feature cache. */
long __wrap_syscall(long number, ...) {
    assert(number == SYS_openat2);
    errno = GF_DENIED_ERRNO;
    return -1;
}
