#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -eu
cd "$(dirname "$0")/.."
diff -r windows/patcher linux/patcher && echo "OK: windows/patcher == linux/patcher"
