# -*- coding: utf-8 -*-
"""Testi fissi (Gloria, Credo, Confesso, ...): file .txt nella cartella testi/, modificabili a mano."""
from .config import BASE
from .errori import ErroreMessa
from .impaginazione import MARCA

CARTELLA_TESTI = BASE / "testi"


def carica_testo(nome: str) -> list:
    """
    Legge testi/<nome>.txt e restituisce una lista di blocchi (strofe); ogni blocco e' una lista di righe.
    Righe vuote = separazione tra strofe; '#' = commento; **riga** = grassetto.
    """
    percorso = CARTELLA_TESTI / f"{nome}.txt"
    try:
        grezzo = percorso.read_text(encoding="utf-8-sig")
    except OSError:
        raise ErroreMessa("E09", str(percorso))
    blocchi, cur = [], []
    for riga in grezzo.splitlines():
        r = riga.strip()
        if r.startswith("#"):
            continue
        if not r:
            if cur:
                blocchi.append(cur)
                cur = []
            continue
        if len(r) > 4 and r.startswith("**") and r.endswith("**"):
            r = MARCA + r[2:-2].strip()
        cur.append(r)
    if cur:
        blocchi.append(cur)
    if not blocchi:
        raise ErroreMessa("E09", f"{percorso.name} è vuoto.")
    return blocchi
