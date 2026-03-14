@echo off
title Campaign In A Box
cd /d "%~dp0"

echo.
echo  ==========================================
echo   Campaign In A Box
echo   Starting Dashboard...
echo  ==========================================
echo.

REM Try venv first, fall back to system Python
if exist "venv\Scripts\streamlit.exe" (
    set STREAMLIT="%~dp0venv\Scripts\streamlit.exe"
) else (
    set STREAMLIT=streamlit
)

if exist "venv\Scripts\python.exe" (
    set PYTHON="%~dp0venv\Scripts\python.exe"
) else (
    set PYTHON=python
)

REM Launch dashboard
%STREAMLIT% run ui\dashboard\app.py --server.port=8501 --server.headless=false

REM Keep window open if streamlit exits with error
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [ERROR] Dashboard exited with code %ERRORLEVEL%
    pause
)
