@echo off
chcp 65001 >nul
title פוקר פייס - גישה מהטלפון
cd /d "%~dp0"
echo.
echo  בטלפון (מחובר לאותו Wi-Fi של הבית) פתחו את הכתובת:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do for /f "tokens=*" %%b in ("%%a") do echo    http://%%b:8777
echo  (אם מופיעות כמה כתובות, הנכונה בדרך כלל מתחילה ב-10.100 או 192.168)
echo.
python server.py --lan
pause
