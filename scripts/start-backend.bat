@echo off
setlocal
cd /d "%~dp0.."
title Summary Meeting - Backend Local
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-helper.ps1"
if errorlevel 1 (
  echo.
  echo Backend local khong khoi dong duoc. Hay xem loi o tren.
  pause
)
