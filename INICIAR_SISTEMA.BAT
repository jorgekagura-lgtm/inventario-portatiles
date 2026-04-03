@echo off
title Servidor Inventario EASD
color 0A

:: 1. CAMBIA ESTA RUTA POR LA DE TU CARPETA REAL
cd /d "C:\Ruta\A\Tu\Carpeta\De\Proyecto"

echo ==========================================
echo    ENCENDIENDO SISTEMA DESDE EL ESCRITORIO
echo ==========================================
echo.
echo [1/3] Iniciando Python en la carpeta correcta...
start /min python app.py

echo [2/3] Tu llave (IP) es: 85.48.80.238
echo [3/3] Abriendo Tunel...
npx localtunnel --port 5000 --subdomain easd-test-jorge
pause