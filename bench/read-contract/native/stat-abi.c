/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include <stdint.h>
#include <errno.h>
#include <sys/stat.h>
/* Rust-only libc layout bridge. Classification/error policy lives in Rust. */
int contract_fstat_mode(int fd, uint32_t *mode) {
    struct stat st;
    int rc=fstat(fd,&st);
    if (rc) return errno;
    *mode=(uint32_t)st.st_mode;
    return 0;
}
