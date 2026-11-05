/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <sys/types.h>
static int64_t mode,calls;
void gf_test_link_mode(int64_t value) { mode=value;calls=0; }
int64_t gf_test_link_calls(void) { return calls; }
ssize_t __wrap_readlinkat(int dir,const char *name,char *out,size_t cap) {
    (void)dir;(void)name;++calls;
    if (calls==1 || mode==0) { memset(out,'q',cap);return (ssize_t)cap; }
    if (mode==1) { memcpy(out,"new",3);return 3; }
    errno=EIO;return -1;
}
