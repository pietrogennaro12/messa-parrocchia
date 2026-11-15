# -*- coding: utf-8 -*-
"""
Apertura del programma in una FINESTRA PROPRIA (senza barra degli indirizzi e senza schede).

Tre livelli, dal migliore al piu' semplice:

  1. "finestra"  finestra nativa con pywebview (Mac: motore di Safari; Windows: motore di Edge/WebView2)
  2. "app"       finestra "senza barra" di Edge / Chrome / Brave, se installati (profilo separato)
  3. "browser"   il browser di sempre

Se un livello non e' disponibile si passa al successivo: il programma si apre comunque.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from .config import BASE

TITOLO = "Messa Parrocchia"
LARGHEZZA, ALTEZZA = 1180, 940
SOGLIA_APERTURA = 3.0          # una finestra "senza barra" chiusa prima di tre secondi = non ha funzionato


def _log(testo):
    try:
        from .server import log
        log(testo)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# icone e nome dell'applicazione (impostazioni "estetiche": mai bloccanti)
# ----------------------------------------------------------------------------

def _impostazioni_mac():
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSBundle
        info = NSBundle.mainBundle().localizedInfoDictionary() or NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = TITOLO                         # nome nel menu in alto, al posto di "Python"
        icona = NSImage.alloc().initByReferencingFile_(str(BASE / "messa.png"))
        NSApplication.sharedApplication().setApplicationIconImage_(icona)
    except Exception as e:
        _log(f"Icona/nome macOS non impostati: {e}")


def _impostazioni_windows(finestra):
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("it.parrocchia.messa")
    except Exception:
        pass
    try:                                                      # icona della finestra e della barra delle applicazioni
        import System.Drawing as disegno                      # noqa  (pythonnet, installato con pywebview)
        finestra.native.Icon = disegno.Icon(str(BASE / "messa.ico"))
    except Exception as e:
        _log(f"Icona Windows non impostata: {e}")


# ----------------------------------------------------------------------------
# 1. finestra nativa (pywebview)
# ----------------------------------------------------------------------------

def con_webview(url: str) -> bool:
    """True se la finestra e' stata mostrata (e poi chiusa dall'utente). Deve girare nel thread principale."""
    try:
        import webview
    except Exception:
        return False
    windows = sys.platform.startswith("win")
    try:
        finestra = webview.create_window(TITOLO, url, width=LARGHEZZA, height=ALTEZZA,
                                         min_size=(860, 600), text_select=True)
        mostrata = threading.Event()
        con_evento = True
        try:
            finestra.events.shown += mostrata.set
            if windows:
                finestra.events.shown += lambda: _impostazioni_windows(finestra)
        except Exception:
            con_evento = False                                # versione di pywebview senza l'evento
        if sys.platform == "darwin":
            _impostazioni_mac()
        webview.start(gui="edgechromium" if windows else None)   # blocca finche' la finestra e' aperta
        return mostrata.is_set() or not con_evento
    except Exception as e:
        _log(f"Finestra pywebview non disponibile: {e}")
        return False


# ----------------------------------------------------------------------------
# 2. finestra "senza barra" di un browser Chromium gia' installato
# ----------------------------------------------------------------------------

def trova_chromium():
    candidati = []
    if sys.platform.startswith("win"):
        cartelle = [os.environ.get(v) for v in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
        relativi = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                    r"BraveSoftware\Brave-Browser\Application\brave.exe"]
        candidati = [Path(c) / r for r in relativi for c in cartelle if c]
    elif sys.platform == "darwin":
        candidati = [Path(p) for p in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium")]
    for c in candidati:
        if c.exists():
            return str(c)
    for nome in ("msedge", "chrome", "google-chrome", "chromium", "chromium-browser", "brave"):
        trovato = shutil.which(nome)
        if trovato:
            return trovato
    return None


def con_chromium(url: str) -> bool:
    """True se la finestra e' stata aperta e poi chiusa dall'utente."""
    exe = trova_chromium()
    if not exe:
        return False
    try:
        profilo = BASE / "cache" / "profilo_finestra"          # profilo separato: il processo dura quanto la finestra
        profilo.mkdir(parents=True, exist_ok=True)
        comando = [exe, f"--app={url}", f"--user-data-dir={profilo}", f"--window-size={LARGHEZZA},{ALTEZZA}",
                   "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"]
        inizio = time.monotonic()
        subprocess.Popen(comando).wait()
        return (time.monotonic() - inizio) > SOGLIA_APERTURA
    except Exception as e:
        _log(f"Finestra {exe} non disponibile: {e}")
        return False


# ----------------------------------------------------------------------------

def apri(url: str, servizio, modalita: str = "auto") -> str:
    """
    Apre il programma. Restituisce "finestra" o "app" (la funzione torna quando l'utente chiude la
    finestra: il programma puo' terminare) oppure "browser" (aperto e basta: serve il controllo di inattivita').
    modalita: "auto" (finestra se possibile) oppure "browser" (solo browser).
    """
    if modalita != "browser":
        servizio.modalita = "finestra"
        if con_webview(url):
            return "finestra"
        if con_chromium(url):
            return "app"
    servizio.modalita = "browser"
    webbrowser.open(url)
    return "browser"
