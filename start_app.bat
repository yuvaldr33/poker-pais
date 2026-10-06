@echo off
chcp 65001 >nul
title פוקר פייס
cd /d "%~dp0"
python server.py
pause
