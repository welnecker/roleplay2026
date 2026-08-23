@echo off
setlocal
cd /d "%~dp0\..\.."

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE (
  where py >nul 2>nul
  if %ERRORLEVEL%==0 set "PYTHON_EXE=py -3"
)
if not defined PYTHON_EXE (
  where python >nul 2>nul
  if %ERRORLEVEL%==0 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
  echo Python nao encontrado.
  echo Instale Python 3 e execute este arquivo novamente.
  pause
  exit /b 1
)

%PYTHON_EXE% -c "import streamlit, PIL" >nul 2>nul
if not %ERRORLEVEL%==0 (
  echo Instalando dependencias locais do editor...
  %PYTHON_EXE% -m pip install -r "tools\roteiro_editor_local\requirements-local.txt"
  if not %ERRORLEVEL%==0 (
    echo Falha ao instalar Streamlit/Pillow.
    pause
    exit /b 1
  )
)

echo Abrindo Editor Local de Roteiros V2...
%PYTHON_EXE% -m streamlit run "tools\roteiro_editor_local\app.py" --server.headless false

endlocal
