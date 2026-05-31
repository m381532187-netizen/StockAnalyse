@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo   Stock Bottom Score  -  interactive mode
echo   A-share: 600519   HK: 0700.HK   name: ok
echo ================================================
python score.py
echo.
pause
