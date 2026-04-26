@echo off
chcp 65001 >nul
echo ============================================================
echo   TCPO Explorer PY — Instalacion
echo ============================================================
echo.

:: Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado.
    echo.
    echo  1. Abrí tu navegador y andá a: https://www.python.org/downloads/
    echo  2. Descargá la version 3.11 o superior
    echo  3. Durante la instalacion, TILDA la opcion "Add Python to PATH"
    echo  4. Volvé a ejecutar este archivo
    echo.
    pause
    exit /b 1
)

:: Verificar version >= 3.11
python -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo [AVISO] Se recomienda Python 3.11 o superior.
    python --version
    echo Continuando de todas formas...
    echo.
)

python --version
echo.

:: Crear entorno virtual si no existe
if not exist ".venv\Scripts\activate.bat" (
    echo Creando entorno virtual...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo Entorno virtual creado.
    echo.
)

:: Instalar dependencias
echo Instalando dependencias ^(puede tardar 2-3 minutos la primera vez^)...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Fallo la instalacion de dependencias.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Instalacion completada exitosamente!
echo ============================================================
echo.
echo  Para abrir el programa: doble click en  iniciar.bat
echo.
pause
