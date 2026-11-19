// SPDX-License-Identifier: Apache-2.0
// Test host bridge for the generated Goose path-validation target.
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "fs-fuzz.h"

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
