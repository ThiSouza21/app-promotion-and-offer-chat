@echo off
setlocal
chcp 65001 >nul
title Achadinhos - mantenha esta janela aberta
cd /d "%~dp0"
if errorlevel 1 goto folder_error

py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 goto run_py
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 goto run_python

echo Para iniciar o Achadinhos, instale o Python 3.10 ou mais recente:
echo https://www.python.org/downloads/
echo No instalador, marque "Add Python to PATH".
echo Depois, feche esta janela e clique neste arquivo novamente.
pause
exit /b 1

:run_py
py -3 app.py
if errorlevel 1 goto app_error
exit /b 0

:run_python
python app.py
if errorlevel 1 goto app_error
exit /b 0

:folder_error
echo Nao foi possivel abrir a pasta do aplicativo.
echo Extraia o ZIP para uma pasta do seu computador antes de iniciar.
pause
exit /b 1

:app_error
echo.
echo O aplicativo nao conseguiu iniciar ou foi interrompido.
echo Leia a mensagem acima para identificar o problema.
pause
exit /b 1
