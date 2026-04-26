@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Generando paquete para distribucion...

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
set ZIPNAME=TCPO_Explorer_PY_%dt:~0,8%.zip

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $dest = '%ZIPNAME%'; if (Test-Path $dest) { Remove-Item $dest }; $tmp = \"$env:TEMP\precios_tmp.db\"; Copy-Item 'data\precios.db' $tmp -Force; $items = @('app','src','requirements.txt','setup.bat','iniciar.bat','INSTRUCCIONES.txt'); Compress-Archive -Force -Path $items -DestinationPath $dest; Add-Type -Assembly 'System.IO.Compression.FileSystem'; $zip = [System.IO.Compression.ZipFile]::Open($dest,'Update'); [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$tmp,'data/precios.db') | Out-Null; $zip.Dispose(); Remove-Item $tmp; $mb = [math]::Round((Get-Item $dest).Length/1MB,1); Write-Host \"ZIP listo: $dest ($mb MB)\""

if not exist "%ZIPNAME%" (
    echo [ERROR] No se pudo crear el ZIP.
    pause
    exit /b 1
)

echo.
echo Compartilo por Google Drive, WeTransfer o Telegram.
echo.
echo Tu amigo solo necesita:
echo   1. Descomprimir el ZIP
echo   2. Instalar Python 3.11+ desde python.org  ^(tildar "Add to PATH"^)
echo   3. Doble click en  setup.bat     ^(solo la primera vez^)
echo   4. Doble click en  iniciar.bat   ^(cada vez que quiera abrir^)
echo.
pause
