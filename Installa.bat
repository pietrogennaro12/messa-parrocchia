@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Installazione di Messa Parrocchia
echo ==============================================
echo    Installazione di Messa Parrocchia
echo ==============================================
echo.

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY goto senzapython

echo 1/4  Preparo l'ambiente...
%PY% -m venv .venv
if errorlevel 1 goto errore

echo 2/4  Scarico i componenti necessari (serve Internet, ci vuole qualche minuto)...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 goto errore

echo 3/4  Preparo la finestra del programma...
".venv\Scripts\python.exe" -m pip install -r requirements-finestra.txt -q
if errorlevel 1 (
  echo      Nota: la finestra propria non e' disponibile su questo computer:
  echo      il programma si aprira' comunque in una finestra di Edge.
)

echo 4/4  Creo il collegamento sul Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crea_collegamento.ps1"

echo.
echo Fatto! Da ora usa l'icona "Messa Parrocchia" sul Desktop
echo (oppure "Messa Parrocchia.vbs" in questa cartella).
echo.
pause
exit /b 0

:senzapython
echo Python non e' installato (oppure e' troppo vecchio: serve la versione 3.9 o successiva).
echo.
echo Si aprira' la pagina di download. Durante l'installazione:
echo    - spunta "Add python.exe to PATH" nella prima schermata
echo Poi fai di nuovo doppio clic su questo file.
start "" "https://www.python.org/downloads/windows/"
echo.
pause
exit /b 1

:errore
echo.
echo Qualcosa non ha funzionato. Controlla la connessione a Internet e riprova.
echo Se il problema continua, copia il messaggio qui sopra e mandalo a chi ti ha dato il programma.
echo.
pause
exit /b 1
