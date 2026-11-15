@echo off
setlocal
title Hollow Knight - Turkce Dil Paketi (Kaldirma)
cd /d "%~dp0"

python\python.exe patcher\hk-tr-patch.py --geri-al %*

echo.
pause
