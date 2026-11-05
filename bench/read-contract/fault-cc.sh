#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
wrap=(-Wl,--wrap=syscall,--wrap=openat,--wrap=open,--wrap=fstat,--wrap=read,--wrap=__read_chk,--wrap=close)
for argument in "$@"; do
    case "$argument" in -c|-S|-E|--version) wrap=();; esac
done
exec "${READ_CONTRACT_CC:-gcc}" "$@" "${wrap[@]}"
