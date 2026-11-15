# -*- coding: utf-8 -*-
"""
Archivio dei canti: legge il PDF (una pagina = un canto, titolo in prima riga)
ed estrae titolo, strofe e ritornelli (le righe in grassetto).
La prima lettura del PDF richiede qualche secondo; poi viene usata una copia salvata in cache/.
"""
import hashlib
import json
import re
from pathlib import Path

from .config import BASE
from .errori import ErroreMessa
from .impaginazione import MARCA

CARTELLA_CACHE = BASE / "cache"


def _leggi_pagina(page):
    """Una pagina del PDF -> (titolo, blocchi) oppure None se la pagina e' vuota."""
    righe = page.extract_text_lines(return_chars=True)
    if not righe:
        return None
    titolo = righe[0]["text"].strip()
    corpo = []
    for L in righe[1:]:
        chars = [c for c in L["chars"] if c["text"].strip()]
        if not chars:
            continue
        testo = re.sub(r"\s+", " ", L["text"]).strip()
        dim = max(c["size"] for c in chars)
        if dim <= 11 and testo.startswith("("):            # nota piccola con l'autore: non si canta
            continue
        if not corpo and re.fullmatch(r"\([^)]{1,30}\)", testo):
            continue
        grassetto = sum("Bold" in c["fontname"] for c in chars) / len(chars) >= 0.6
        corpo.append({"t": testo, "b": grassetto, "top": L["top"],
                      "bottom": L["bottom"], "size": dim})
    if not corpo:
        return None

    # le strofe sono separate da uno spazio verticale piu' grande del normale
    stacchi = sorted(abs(corpo[i]["top"] - corpo[i - 1]["bottom"]) for i in range(1, len(corpo)))
    mediano = stacchi[len(stacchi) // 2] if stacchi else 0
    soglia = max(1.6 * mediano, 0.3 * max(c["size"] for c in corpo))

    tutte_bold = sum(c["b"] for c in corpo) / len(corpo) > 0.85
    blocchi, cur = [], []
    for i, c in enumerate(corpo):
        if i > 0 and (c["top"] - corpo[i - 1]["bottom"]) > soglia and cur:
            blocchi.append(cur)
            cur = []
        cur.append((MARCA if (c["b"] and not tutte_bold) else "") + c["t"])
    if cur:
        blocchi.append(cur)
    return titolo, blocchi


def _firma(pdf: Path) -> str:
    st = pdf.stat()
    return hashlib.md5(f"{pdf.resolve()}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()


class ArchivioCanti:
    def __init__(self, pdf: Path):
        self.pdf = Path(pdf)
        self.canti = []        # [{"id": pagina, "titolo": ..., "blocchi": [[...]]}]
        self._carica()

    def _carica(self):
        if not self.pdf.exists():
            raise ErroreMessa("E04", str(self.pdf))
        cache = CARTELLA_CACHE / f"canti_{_firma(self.pdf)}.json"
        try:
            self.canti = json.loads(cache.read_text(encoding="utf-8"))
            return
        except (OSError, ValueError):
            pass
        try:
            import pdfplumber
            canti = []
            with pdfplumber.open(str(self.pdf)) as doc:
                for n, page in enumerate(doc.pages, 1):
                    r = _leggi_pagina(page)
                    if r:
                        canti.append({"id": n, "titolo": r[0], "blocchi": r[1]})
        except ErroreMessa:
            raise
        except Exception as e:
            raise ErroreMessa("E06", f"{self.pdf.name}: {str(e)[:100]}")
        if not canti:
            raise ErroreMessa("E06", f"{self.pdf.name}: non ho trovato canti nel documento.")
        self.canti = canti
        try:
            CARTELLA_CACHE.mkdir(exist_ok=True)
            for vecchio in CARTELLA_CACHE.glob("canti_*.json"):
                vecchio.unlink()
            cache.write_text(json.dumps(canti, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def titoli(self):
        """Elenco per popolare le select: [{"id", "titolo"}] in ordine alfabetico."""
        return [{"id": c["id"], "titolo": c["titolo"]} for c in self.canti]

    def per_id(self, id_canto):
        for c in self.canti:
            if c["id"] == id_canto:
                return c
        return None

    def per_titolo(self, titolo: str):
        """Cerca un canto per titolo esatto (ignorando maiuscole/apici); utile per i predefiniti."""
        n = _norm(titolo)
        for c in self.canti:
            if _norm(c["titolo"]) == n:
                return c
        return None


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[’'`´]", "", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()
