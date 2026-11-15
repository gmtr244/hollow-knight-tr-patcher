#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Hollow Knight - Turkce Dil Paketi (kurulum)
set -u
cd "$(dirname "$0")"

PY=python3
if ! "$PY" -c "import UnityPy" >/dev/null 2>&1; then
  if [ ! -x .venv/bin/python ]; then
    echo "Gerekli Python paketleri kuruluyor (ilk sefer, internet gerekir)..."
    "$PY" -m venv .venv || { echo "HATA: venv olusturulamadi (python3-venv kurulu mu?)"; exit 1; }
    .venv/bin/pip install --quiet --upgrade pip >/dev/null 2>&1
    .venv/bin/pip install --quiet "UnityPy==1.25.4" || { echo "HATA: UnityPy kurulamadi"; exit 1; }
  fi
  PY=.venv/bin/python
fi

exec "$PY" patcher/hk-tr-patch.py "$@"
