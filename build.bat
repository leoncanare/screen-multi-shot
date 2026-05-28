@echo off
title Screenshot Multi-Shot — Build .exe
echo.
echo ============================================================
echo   Screenshot Multi-Shot — Generando .exe
echo ============================================================
echo.

echo [1/3] Instalando dependencias de build...
py -m pip install pyinstaller customtkinter playwright --quiet
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Fallo al instalar dependencias.
    pause
    exit /b 1
)

echo.
echo [2/3] Compilando ejecutable...
py -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "ScreenshotMultiShot" ^
    --collect-all customtkinter ^
    screenshot_gui.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Fallo al compilar.
    pause
    exit /b 1
)

echo.
echo [3/3] Listo!
echo.
echo  Ejecutable generado en: dist\ScreenshotMultiShot.exe
echo.
echo  NOTA: La primera vez que se ejecute el .exe,
echo  descargara Chromium automaticamente (~150 MB).
echo.
pause
