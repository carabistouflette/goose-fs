// SPDX-License-Identifier: Apache-2.0
// Test host bridge for the generated Goose path-validation target.
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "fs-fuzz.h"
#include "fs.h"

// Remapped only while compiling generated Goose C. Goose assertion/bounds
// failures call _Exit; abort lets libFuzzer preserve the triggering bytes.
_Noreturn void goose_fuzz_exit(int status) {
    if (status != 0) abort();
    _Exit(status);
}
int LLVMFuzzerInitialize(int *argc, char ***argv) {
    goose_init(*argc, *argv);
    atexit(goose_exit);
    return 0;
}
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size > INT64_MAX) return 0;
#ifdef GOOSE_FUZZ_SELF_TEST
    static const uint8_t probe[] = "libFuzzer Goose assertion bridge probe";
    if (size == sizeof(probe) - 1 && memcmp(data, probe, size) == 0)
        fuzz_assertion_probe(0);
#endif
    (void)fuzz_check((sl_u8){(uint8_t *)data, (int64_t)size});
    return 0;
}

// No invalid-path check may enter the native boundary, even if native validation
// would happen to return the same error. Link-only traps keep mutants away from I/O.
int64_t __wrap_gf_call(int64_t op, gf_input path, gf_input data, int64_t entries,
                      gf_output out, gf_meta meta) {
    (void)op; (void)path; (void)data; (void)entries; (void)out; (void)meta;
    fputs("unexpected native boundary\n", stderr);
    abort();
}
int64_t __wrap_gf_list(gf_input path, int64_t bytes, gf_output out, int64_t entries, gf_meta meta) {
    (void)path; (void)bytes; (void)out; (void)entries; (void)meta;
    fputs("unexpected native boundary\n", stderr);
    abort();
}
int64_t __wrap_gf_metadata(gf_input path, gf_meta fields) {
    (void)path; (void)fields;
    fputs("unexpected native boundary\n", stderr);
    abort();
}
