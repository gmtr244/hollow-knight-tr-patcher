#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# windows/ ve linux/ içindeki ortak yama dosyaları birbirinden sapmasın.
set -eu
cd "$(dirname "$0")/.."
diff -r windows/patcher linux/patcher && echo "OK: windows/patcher == linux/patcher"
