@echo off
cd /d "%~dp0\.."
python scripts\webp_batch_converter.py
if errorlevel 1 (
  echo.
  echo Nao foi possivel abrir o conversor.
  echo Confirme que o Python e as dependencias do projeto estao instalados.
  pause
)
