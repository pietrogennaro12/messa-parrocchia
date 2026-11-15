#!/bin/bash
# Avvio di emergenza: se l'icona "Messa Parrocchia" non si apre, usa questo file (doppio clic).
# Si apre una finestra di Terminale: LASCIALA APERTA (puoi ridurla a icona). Chiudendola si chiude il programma.
cd "$(dirname "$0")" || exit 1
clear
if [ ! -x ".venv/bin/python" ]; then
  echo "Il programma non è ancora installato."
  echo "Fai prima doppio clic su Installa.command, poi riprova."
  echo
  read -r -p "Premi Invio per chiudere..."
  exit 1
fi
echo "Messa Parrocchia è in funzione."
echo "Lascia aperta questa finestra (puoi ridurla a icona): chiuderla chiude il programma."
echo
.venv/bin/python app.py
