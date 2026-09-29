@echo off
powershell.exe -NoProfile -File "%~dp0retrieval\run_search.ps1"
if errorlevel 1 pause
