/* SPDX-License-Identifier: Apache-2.0 */
#ifndef GOOSE_FS_H
#define GOOSE_FS_H
#include <stdint.h>
typedef struct { const uint8_t *data; int64_t len; } gf_input;
typedef struct { uint8_t *data; int64_t len; } gf_output;
typedef struct { int64_t *data; int64_t len; } gf_meta;
/* Private slice ABI; no pointers retained. meta = errno, byte count, entry count. */
int64_t gf_call(int64_t op, gf_input path, gf_input data, int64_t entries,
                gf_output out, gf_meta meta);
int64_t gf_metadata(gf_input path, gf_meta fields);
_Bool gf_missing(int64_t os_error);
#endif
