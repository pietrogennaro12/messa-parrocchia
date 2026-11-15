# -*- coding: utf-8 -*-
"""Configurazione salvata in config.json (nella cartella del programma)."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
FILE_CONFIG = BASE / "config.json"

PREDEFINITA = {
    "parrocchia": "Parrocchia di Terranegra",
    "pdf_canti": "archivi/canti.pdf",
    "pdf_preghiere": "archivi/preghiere_fedeli.pdf",
    "pagine_preghiere": "",            # es. "3-4"; vuoto = tutto il PDF
    "cartella_output": "~/Documents/Messe",
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
