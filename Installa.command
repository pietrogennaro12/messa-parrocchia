#!/bin/bash
# Installazione di "Messa Parrocchia" - da eseguire UNA SOLA VOLTA (doppio clic).
cd "$(dirname "$0")" || exit 1
clear
echo "=============================================="
echo "   Installazione di Messa Parrocchia"
echo "=============================================="
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python non è installato."
  echo "Si aprirà la pagina di download: installa Python 3, poi rilancia questo file."
  open "https://www.python.org/downloads/macos/"
  read -r -p "Premi Invio per chiudere..."
  exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "La versione di Python è troppo vecchia (serve la 3.9 o successiva)."
  open "https://www.python.org/downloads/macos/"
  read -r -p "Premi Invio per chiudere..."
  exit 1
fi

if [ "$(uname -m)" = "x86_64" ] && [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then
  echo "Nota: questo Terminale sta girando in modalità Intel (Rosetta) su un Mac con chip Apple."
  echo "Il programma si avvierà comunque correttamente."
  echo
fi

echo "1/4  Preparo l'ambiente..."
python3 -m venv .venv || { echo "Errore nella creazione dell'ambiente."; read -r -p "Invio per chiudere..."; exit 1; }

echo "2/4  Scarico i componenti necessari (serve Internet, ci vuole qualche minuto)..."
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.txt -q || { echo "Errore nell'installazione dei componenti."; read -r -p "Invio per chiudere..."; exit 1; }

echo "3/4  Preparo la finestra del programma..."
if ! .venv/bin/python -m pip install -r requirements-finestra.txt -q; then
  echo "     Nota: la finestra propria non è disponibile su questo computer:"
  echo "     il programma si aprirà comunque (in una finestra del browser)."
fi

echo "4/4  Rendo il programma avviabile con un doppio clic..."
chmod +x "Messa Parrocchia.app/Contents/MacOS/avvia" "Avvia con Terminale.command" Installa.command
xattr -dr com.apple.quarantine . 2>/dev/null
xattr -cr "Messa Parrocchia.app" 2>/dev/null

echo
echo "Fatto! Da ora usa l'icona \"Messa Parrocchia\" in questa cartella"
echo "(puoi trascinarla nel Dock o sul Desktop)."
echo
echo "Se l'icona non si apre: usa \"Avvia con Terminale.command\" e guarda il file"
echo "~/Library/Logs/Messa Parrocchia/avvio.log (dice cosa non va)."
echo
read -r -p "Premi Invio per chiudere questa finestra..."
