@echo off
setlocal
title Hollow Knight - Turkce Dil Paketi
cd /d "%~dp0"

echo ==========================================
echo  Hollow Knight - Turkce Dil Paketi
echo ==========================================
echo.

python\python.exe patcher\hk-tr-patch.py %*

echo.
pause
