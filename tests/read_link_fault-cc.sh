#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
link=("$script_dir/read_link_fault.c" -Wl,--wrap=readlinkat)
for argument in "$@"; do
    case "$argument" in -c|-S|-E|--version) link=();; esac
done
exec "${FS_READLINK_CC:-gcc}" "$@" "${link[@]}"
