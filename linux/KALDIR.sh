#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Hollow Knight - Turkce Dil Paketi (kaldirma)
set -u
cd "$(dirname "$0")"

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
exec "$PY" patcher/hk-tr-patch.py --geri-al "$@"
