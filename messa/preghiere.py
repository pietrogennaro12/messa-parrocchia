# -*- coding: utf-8 -*-
"""
Preghiere dei fedeli: lettura del PDF locale.

Il documento viene letto per paragrafi: gli "a capo" dovuti solo all'impaginazione
del PDF vengono eliminati, mentre le righe vuote tra un paragrafo e l'altro restano.
In config.json si puo' indicare un intervallo di pagine (es. "3-4") se il PDF
contiene piu' celebrazioni.
"""
import re
from pathlib import Path

from .errori import ErroreMessa


def _pagine_richieste(testo: str, totale: int):
    """'3-4' -> [3, 4]; '2,5' -> [2, 5]; vuoto -> tutte."""
    testo = (testo or "").strip()
    if not testo:
        return list(range(1, totale + 1))
    pagine = set()
    for parte in re.split(r"[,;]\s*", testo):
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", parte)
        if m:
            pagine.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif parte.isdigit():
            pagine.add(int(parte))
    scelte = sorted(p for p in pagine if 1 <= p <= totale)
    if not scelte:
        raise ErroreMessa("E06", f"Pagine «{testo}» non valide: il PDF ha {totale} pagine.")
    return scelte


def leggi_preghiere(pdf: Path, pagine: str = "") -> list:
    """Restituisce una lista di blocchi; ogni blocco e' una lista di righe (paragrafi)."""
    pdf = Path(pdf)
    if not pdf.exists():
        raise ErroreMessa("E05", str(pdf))
    try:
        import pdfplumber
        righe_pagina = []
        with pdfplumber.open(str(pdf)) as doc:
            for n in _pagine_richieste(pagine, len(doc.pages)):
                for L in doc.pages[n - 1].extract_text_lines(return_chars=True):
                    dim = max((c["size"] for c in L["chars"]), default=0)
                    righe_pagina.append((L["top"], L["bottom"], re.sub(r"\s+", " ", L["text"]).strip(), dim))
                righe_pagina.append(None)          # stacco di pagina
    except ErroreMessa:
        raise
    except Exception as e:
        raise ErroreMessa("E06", f"{pdf.name}: {str(e)[:100]}")

    # raggruppo in blocchi dove lo spazio verticale e' piu' grande del normale
    blocchi, cur, prec = [], [], None
    vere = [x for x in righe_pagina if x]
    stacchi = sorted(abs(r[0] - p[1]) for r, p in zip(vere[1:], vere))
    mediano = stacchi[len(stacchi) // 2] if stacchi else 0
    soglia = max(1.6 * mediano, 4)
    dimensioni = sorted(x[3] for x in vere)
    dim_normale = dimensioni[len(dimensioni) // 2] if dimensioni else 0
    for r in righe_pagina:
        if r is None:
            prec = None
            continue
        if not r[2]:
            continue
        titolo = dim_normale and r[3] > 1.15 * dim_normale       # titolo del documento: resta a parte
        stacco = prec is not None and (r[0] - prec[1]) > soglia
        if cur and (stacco or titolo or (prec is not None and prec[3] > 1.15 * dim_normale)):
            blocchi.append(cur)
            cur = []
        cur.append(r[2])
        prec = r
    if cur:
        blocchi.append(cur)

    # elimino gli a capo "tecnici": una riga che non finisce con punteggiatura continua nella successiva
    risultato = []
    for b in blocchi:
        righe, corrente = [], ""
        for t in b:
            corrente = f"{corrente} {t}".strip() if corrente else t
            if re.search(r"[.:;!?»”\"]$", t):
                righe.append(corrente)
                corrente = ""
        if corrente:
            righe.append(corrente)
        risultato.append([re.sub(r"(\w)- (\w)", r"\1\2", r) for r in righe])
    if not risultato:
        raise ErroreMessa("E06", f"{pdf.name}: nessun testo trovato (forse è una scansione?).")
    return risultato
