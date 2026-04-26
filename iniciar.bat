@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] El programa no esta instalado todavia.
    echo Por favor ejecuta primero:  setup.bat
    pause
    exit /b 1
)

call .venv\Scripts\activate
echo Abriendo TCPO Explorer PY...
start "" http://localhost:8501
streamlit run app/main.py
