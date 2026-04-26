@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Ejecuta primero setup.bat
    pause & exit /b 1
)

:: Obtener IP de Tailscale
set TS_IP=
for /f "tokens=2 delims=:" %%a in ('tailscale ip 2^>nul') do (
    set RAW=%%a
    set RAW=!RAW: =!
    echo !RAW! | findstr /R "^100\." >nul 2>&1
    if not errorlevel 1 set TS_IP=!RAW!
)

:: Obtener IP local
set LOCAL_IP=
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4"') do (
    set RAW=%%a
    set RAW=!RAW: =!
    echo !RAW! | findstr /R "^192\." >nul 2>&1
    if not errorlevel 1 set LOCAL_IP=!RAW!
)

call .venv\Scripts\activate

echo.
echo ============================================================
echo   TCPO Explorer PY — Modo Servidor
echo ============================================================
echo.
if defined TS_IP (
    echo   URL para tu companero ^(Tailscale^):
    echo   http://!TS_IP!:8501
) else (
    echo   Tailscale no detectado o no conectado.
)
echo.
if defined LOCAL_IP (
    echo   URL en red local:
    echo   http://!LOCAL_IP!:8501
)
echo.
echo   Tu browser:  http://localhost:8501
echo ============================================================
echo.
start "" http://localhost:8501
streamlit run app/main.py
