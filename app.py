#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Messa Parrocchia - avvio del programma.
Apre l'interfaccia in una finestra propria (se possibile) o nel browser;
il programma si chiude quando chiudi la finestra (o la scheda del browser).
"""
import argparse
import platform
import sys
import traceback
import threading
import time

from messa import __version__, config, finestra
from messa.server import Servizio, avvia, log

TIMEOUT_INATTIVITA = 600   # secondi senza segnali dalla pagina -> il programma si chiude


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="(solo prove) usa un file HTML al posto del sito della CEI")
    ap.add_argument("--porta", type=int, default=0)
    ap.add_argument("--no-browser", action="store_true", help="non apre nessuna finestra (solo prove)")
    ap.add_argument("--browser", action="store_true", help="apre il browser invece della finestra propria")
    a = ap.parse_args()

    config.ricorda_cartella()
    servizio = Servizio(html_prova=a.html)
    server = avvia(servizio, a.porta)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log(f"Messa Parrocchia {__version__} | Avviato su {url} | Python {platform.python_version()} {platform.machine()} su {platform.system()}")
    print(f"Messa Parrocchia in funzione su {url}")
    if not a.no_browser:
        modo = finestra.apri(url, servizio, "browser" if a.browser else "auto")
        log(f"Aperto in modalità: {modo}")
        if modo in ("finestra", "app"):          # l'utente ha chiuso la finestra: il programma finisce
            server.shutdown()
            sys.exit(0)

    try:
        while True:
            time.sleep(5)
            if time.time() - servizio.ultimo_ping > TIMEOUT_INATTIVITA:
                log("Chiuso per inattività")
                break
    except KeyboardInterrupt:
        pass
    server.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:                      # senza finestre un errore passerebbe inosservato: lo scrivo nel log
        log(traceback.format_exc())
        raise
