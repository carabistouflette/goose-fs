/* SPDX-License-Identifier: Apache-2.0 */
#ifndef GF_TEST_SUPPORT_H
#define GF_TEST_SUPPORT_H
#include "../native/fs.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static int64_t invoke(int op, const char *path, const char *data, uint8_t *out, int64_t cap, int64_t meta[3]) {
    return gf_call(op, (gf_input){(const uint8_t *)path, (int64_t)strlen(path)},
                   (gf_input){(const uint8_t *)data, (int64_t)strlen(data)}, 4096,
                   (gf_output){out, cap}, (gf_meta){meta, 3});
}
#endif
