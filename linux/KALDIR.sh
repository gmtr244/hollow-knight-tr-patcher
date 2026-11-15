#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -u
cd "$(dirname "$0")"

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
exec "$PY" patcher/hk-tr-patch.py --geri-al "$@"
