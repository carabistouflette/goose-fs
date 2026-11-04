#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
exec "${SANITIZER_CC:-gcc}" "$@" -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie
