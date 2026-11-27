# -*- coding: utf-8 -*-
"""
Preghiere dei fedeli: lettura del PDF locale.

Il documento viene letto per paragrafi: gli "a capo" dovuti solo all'impaginazione
del PDF vengono eliminati, mentre le righe vuote tra un paragrafo e l'altro restano.
In config.json si puo' indicare un intervallo di pagine (es. "3-4") se il PDF
contiene piu' celebrazioni.

Correzioni automatiche:
  * LIGATURE: alcuni PDF (es. creati da Word con certi caratteri) scrivono "ti", "tt" e "tti" come un unico
    simbolo che poi si legge come "<", "@" e ":" ("noi < preghiamo", "perme@e", "tu: i fratelli").
    Si riconoscono dalla LARGHEZZA del simbolo (un due punti vero e' stretto, quello che nasconde "tti" e'
    largo il triplo) e si rimettono le lettere giuste. Le ligature "vere" (ﬁ ﬂ ﬃ...) diventano lettere normali.
  * TITOLO DEL DOCUMENTO ("Preghiere dei fedeli - 21/22 novembre") scartato: la slide del titolo la crea il programma.
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


LIGATURE_UNICODE = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
_SIMBOLI = ":<@"
_TITOLO_DOCUMENTO = re.compile(r"^\s*(preghiere?\s+dei\s+fedeli|preghiera\s+universale)", re.I)
_SOSPETTI = re.compile(r"[<>@^~|]|(?<=[A-Za-zÀ-ÿ]):(?=[A-Za-zÀ-ÿ])")


def ripara_riga(riga):
    """
    riga: una riga di pdfplumber (con "text" e "chars"). Restituisce (testo corretto, simboli riparati).
    Sostituisce i simboli che nascondono una ligatura: ":" largo -> "tti", "<" -> "ti", "@" stretta -> "tt".
    """
    scelte = []
    for c in riga["chars"]:
        t = c["text"]
        if t not in _SIMBOLI:
            continue
        rapporto = (c["x1"] - c["x0"]) / c["size"] if c.get("size") else 0
        if t == ":" and rapporto > 0.5:          # due punti vero: ~0,27; la ligatura "tti": ~0,86
            scelte.append("tti")
        elif t == "<":
            scelte.append("ti")
        elif t == "@" and rapporto < 0.8:        # chiocciola vera: ~0,94; la ligatura "tt": ~0,63
            scelte.append("tt")
        else:
            scelte.append(t)
    testo, i, riparati = [], 0, 0
    for ch in riga["text"]:
        if ch in _SIMBOLI:
            nuovo = scelte[i] if i < len(scelte) else ch
            i += 1
            riparati += nuovo != ch
            testo.append(nuovo)
        else:
            testo.append(LIGATURE_UNICODE.get(ch, ch))
    return "".join(testo), riparati


def _senza_punteggiatura(t: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", t.lower()).split())


def e_intenzione(blocco, risposta="Ascoltaci, o Signore") -> bool:
    """
    True se il paragrafo e' una vera intenzione di preghiera, dopo la quale l'assemblea risponde.
    NON lo sono: la preghiera conclusiva ("... Per Cristo nostro Signore. Amen"), l'invito iniziale
    ("... e diciamo insieme") e i paragrafi che contengono gia' la risposta.
    """
    testo = " ".join(blocco).strip()
    basso = testo.lower()
    if risposta and " " + _senza_punteggiatura(risposta) + " " in " " + _senza_punteggiatura(testo) + " ":
        return False                                                  # la risposta c'e' gia' (anche con altra punteggiatura)
    if re.search(r"per cristo,? nostro signore\.?(\s*amen\.?)?$", basso) or re.search(r"\bamen\.?$", basso):
        return False
    if re.search(r"\b(diciamo|rispondiamo|invochiamo)(\s+insieme)?\s*[:.]?$", basso) or \
            re.search(r"\bpreghiamo\s+insieme\s*[:.]?$", basso):
        return False
    return bool(testo)


def analizza_preghiere(pdf: Path, pagine: str = ""):
    """Come leggi_preghiere, ma restituisce anche (blocchi, info) con quante correzioni sono state fatte."""
    blocchi, info = _leggi(pdf, pagine)
    return blocchi, info


def leggi_preghiere(pdf: Path, pagine: str = "") -> list:
    """Restituisce una lista di blocchi; ogni blocco e' una lista di righe (paragrafi)."""
    return _leggi(pdf, pagine)[0]


def _leggi(pdf: Path, pagine: str = ""):
    pdf = Path(pdf)
    if not pdf.exists():
        raise ErroreMessa("E05", str(pdf))
    try:
        import pdfplumber
        righe_pagina, riparati = [], 0
        with pdfplumber.open(str(pdf)) as doc:
            for n in _pagine_richieste(pagine, len(doc.pages)):
                for L in doc.pages[n - 1].extract_text_lines(return_chars=True):
                    dim = max((c["size"] for c in L["chars"]), default=0)
                    testo, n_riparati = ripara_riga(L)
                    riparati += n_riparati
                    righe_pagina.append((L["top"], L["bottom"], re.sub(r"\s+", " ", testo).strip(), dim))
                righe_pagina.append(None)          # stacco di pagina
    except ErroreMessa:
        raise
    except Exception as e:
        raise ErroreMessa("E06", f"{pdf.name}: {str(e)[:100]}")

    # raggruppo in blocchi dove lo spazio verticale e' piu' grande del normale
    blocchi, cur, prec, sono_titoli = [], [], None, []
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
        if not cur:
            sono_titoli.append(bool(titolo))
        cur.append(r[2])
        prec = r
    if cur:
        blocchi.append(cur)

    # il titolo del documento ("Preghiere dei fedeli - 21/22 novembre") non e' una preghiera
    titolo_scartato = None
    if blocchi and (sono_titoli[0] or _TITOLO_DOCUMENTO.match(" ".join(blocchi[0]))) and len(blocchi) > 1:
        titolo_scartato = " ".join(blocchi[0])
        blocchi, sono_titoli = blocchi[1:], sono_titoli[1:]

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
    sospetti = len(_SOSPETTI.findall(" ".join(r for b in risultato for r in b)))
    return risultato, {"riparati": riparati, "sospetti": sospetti, "titolo_scartato": titolo_scartato}
