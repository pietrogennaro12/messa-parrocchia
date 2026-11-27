# -*- coding: utf-8 -*-
"""Configurazione salvata in config.json (nella cartella del programma)."""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
FILE_CONFIG = BASE / "config.json"

PREDEFINITA = {
    "parrocchia": "Parrocchia di Terranegra",
    "pdf_canti": "archivi/canti.pdf",
    "pdf_preghiere": "archivi/preghiere_fedeli.pdf",
    "pagine_preghiere": "",            # es. "3-4"; vuoto = tutto il PDF
    "risposta_preghiere": "Ascoltaci, o Signore",   # scritta in giallo alla fine di ogni preghiera dei fedeli
    "cartella_output": "~/Documents/Messe",
    "repository_aggiornamenti": "",     # indirizzo GitHub degli aggiornamenti, nella forma utente/nome
    "controllo_automatico": True,      # controlla se c'e' una versione nuova all'avvio
    "font": "Aptos",                   # se non c'e': "Calibri" o "Arial"
    # canti proposti all'avvio (titolo esatto come nel PDF); chiave = nome della select
    "canti_predefiniti": {"agnello": "AGNELLO DI DIO"},
}


def carica() -> dict:
    cfg = dict(PREDEFINITA)
    try:
        cfg.update(json.loads(FILE_CONFIG.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


def salva(cfg: dict) -> None:
    try:
        FILE_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def percorso(valore: str) -> Path:
    """Percorso assoluto: ~ viene espanso, i percorsi relativi partono dalla cartella del programma."""
    p = Path(valore).expanduser()
    return p if p.is_absolute() else BASE / p


def ricorda_cartella():
    """
    Mac: scrive dove si trova il programma in ~/Library/Application Support/Messa Parrocchia/cartella.txt.
    Cosi' l'icona "Messa Parrocchia" copiata altrove (es. sulla Scrivania) ritrova i file del programma.
    """
    if sys.platform != "darwin":
        return
    try:
        cartella = Path.home() / "Library" / "Application Support" / "Messa Parrocchia"
        cartella.mkdir(parents=True, exist_ok=True)
        (cartella / "cartella.txt").write_text(str(BASE) + "\n", encoding="utf-8")
    except OSError:
        pass
