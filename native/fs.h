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
/* Retained-resource ABI; meta = errno, count/token/position, eof. */
int64_t gf_context_create(gf_meta meta);
int64_t gf_context_close(int64_t context, gf_meta meta);
int64_t gf_file_open(int64_t context, gf_input path, int64_t options, int64_t permissions, gf_meta meta);
int64_t gf_file_close(int64_t context, int64_t file, gf_meta meta);
int64_t gf_file_duplicate(int64_t context, int64_t file, gf_meta meta);
int64_t gf_file_read(int64_t context, int64_t file, gf_output out, int64_t offset, _Bool positioned, gf_meta meta);
int64_t gf_file_write(int64_t context, int64_t file, gf_input data, int64_t offset, _Bool positioned, _Bool all, gf_meta meta);
int64_t gf_file_seek(int64_t context, int64_t file, int64_t offset, int64_t origin, gf_meta meta);
int64_t gf_file_truncate(int64_t context, int64_t file, int64_t size, gf_meta meta);
int64_t gf_file_sync(int64_t context, int64_t file, _Bool data_only, gf_meta meta);
int64_t gf_file_metadata(int64_t context, int64_t file, gf_meta fields);
#endif
