# -*- coding: utf-8 -*-
"""
Impaginazione: quanto testo entra in una slide.

Regole:
  * preghiere ("unica")  -> tutto su UNA slide; la grandezza si sceglie da sola;
  * salmo               -> una strofa + ritornello (R.) per slide, mai divisa;
  * canti               -> una strofa per slide (piu' strofe se ci stanno);
  * letture ("testo")   -> testo lungo diviso in piu' slide, a grandezza fissa.
"""
import math
import re

MARCA = "\u2063"   # segna internamente le righe in grassetto (ritornelli dei canti)

LARGHEZZA_PT = (13.333 - 1.4) * 72   # larghezza utile del testo
ALTEZZA_PT = 5.6 * 72                # altezza utile del testo


def righe_necessarie(t: str, size: int) -> int:
    n = len(t.lstrip(MARCA)) * (1.07 if t.startswith(MARCA) else 1.0)
    per_riga = max(8, int(LARGHEZZA_PT / (size * 0.53) * 0.93))
    return max(1, math.ceil(n / per_riga))


def altezza(blocchi, size, verso) -> float:
    """Stima dell'altezza occupata dal testo (in punti)."""
    h = 0.0
    for i, b in enumerate(blocchi):
        for r in b:
            h += righe_necessarie(r, size) * size * 1.26 + (0 if verso else 12)
        if i > 0:
            h += 22
    return h


def entra(blocchi, size, verso, budget=ALTEZZA_PT) -> bool:
    return altezza(blocchi, size, verso) <= budget


def spezza_parole(t, size, verso):
    out, cur = [], ""
    for w in t.split():
        prova = (cur + " " + w).strip()
        if cur and not entra([[prova]], size, verso):
            out.append(cur)
            cur = w
        else:
            cur = prova
    if cur:
        out.append(cur)
    return out


def frammenti(riga, size, verso):
    """Divide una riga in pezzi che entrano da soli in una slide."""
    if verso and entra([[riga]], size, verso):
        return [riga]
    out = []
    for f in re.split(r"(?<=[.!?:;,»])\s+", riga):
        out.extend([f] if entra([[f]], size, verso) else spezza_parole(f, size, verso))
    # un pezzo troppo corto ("Fratelli,") non resta da solo: lo unisco al successivo
    i = 0
    while i < len(out) - 1:
        unito = out[i] + " " + out[i + 1]
        if len(out[i]) < 25 and entra([[unito]], size, verso):
            out[i:i + 2] = [unito]
        else:
            i += 1
    return out


def blocchi_da_atomi(atomi):
    """Ricostruisce blocchi/righe; pezzi della stessa riga tornano uniti."""
    blocchi, ultimo = [], None
    for at in atomi:
        for bi, li, t in at:
            if blocchi and ultimo and ultimo[0] == bi:
                if ultimo[1] == li:
                    blocchi[-1][-1] += " " + t.lstrip(MARCA)
                else:
                    blocchi[-1].append(t)
            else:
                blocchi.append([t])
            ultimo = (bi, li)
    return blocchi


def riempi(atomi, size, verso, budget):
    slides, cur = [], []
    for at in atomi:
        if cur and not entra(blocchi_da_atomi(cur + [at]), size, verso, budget):
            slides.append(cur)
            cur = [at]
        else:
            cur.append(at)
    if cur:
        slides.append(cur)
    return slides


def impagina(blocchi, size, verso):
    """Testo lungo (letture): lista di slide; ogni slide e' una lista di blocchi."""
    atomi = []
    for bi, b in enumerate(blocchi):
        for li, riga in enumerate(b):
            marcata = riga.startswith(MARCA)
            for f in frammenti(riga.lstrip(MARCA), size, verso):
                atomi.append([(bi, li, (MARCA if marcata else "") + f)])
    if not atomi:
        return []

    # la riga introduttiva ("Dalla lettera di...") resta con l'inizio del testo
    blocco0 = [a for a in atomi if a[0][0] == atomi[0][0][0]]
    resto = atomi[len(blocco0):]
    if resto and sum(len(a[0][2]) for a in blocco0) < 140:
        incollato = [x for a in blocco0 for x in a] + resto[0]
        if entra(blocchi_da_atomi([incollato]), size, verso):
            atomi = [incollato] + resto[1:]

    # la chiusura breve ("Parola di Dio.") resta con la frase precedente
    if len(atomi) >= 2 and len(atomi[-1][0][2]) < 40:
        incollato = atomi[-2] + atomi[-1]
        if entra(blocchi_da_atomi([incollato]), size, verso):
            atomi = atomi[:-2] + [incollato]

    slides = riempi(atomi, size, verso, ALTEZZA_PT)
    n = len(slides)
    if n > 1:  # bilancia, per evitare un'ultima slide con poche parole
        for f in (0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95):
            prova = riempi(atomi, size, verso, ALTEZZA_PT * f)
            if len(prova) <= n:
                slides = prova
                break
    return [blocchi_da_atomi(sl) for sl in slides]


def e_verso(blocchi) -> bool:
    """Preghiere e salmi: righe corte, niente spazio tra una riga e l'altra."""
    righe = [r for b in blocchi for r in b if r]
    return bool(righe) and sum(len(r) for r in righe) / len(righe) < 75


def impagina_gruppi(gruppi, verso, massimo, minimo, unisci):
    """
    Ogni gruppo (lista di blocchi) deve stare INTERO su una slide.
    Sceglie la grandezza piu' grande (tra massimo e minimo) con cui tutti i
    gruppi entrano; se unisci=True mette piu' gruppi sulla stessa slide quando ci stanno.
    Un gruppo che non entra nemmeno alla grandezza minima viene diviso.
    Restituisce (slides, grandezza).
    """
    size = minimo
    for s in range(massimo, minimo - 1, -2):
        if all(entra(g, s, verso) for g in gruppi):
            size = s
            break
    slides, cur = [], []
    for g in gruppi:
        if not entra(g, size, verso):
            if cur:
                slides.append(cur)
                cur = []
            slides.extend(impagina(g, size, verso))
        elif unisci and cur and entra(cur + g, size, verso):
            cur = cur + g
        else:
            if cur:
                slides.append(cur)
            cur = list(g)
    if cur:
        slides.append(cur)
    return slides, size


def gruppi_salmo(blocchi):
    """Ritornello (R.) ripetuto dopo ogni strofa; ogni strofa+ritornello e' un gruppo."""
    rit, intro, strofe = None, [], []
    for b in blocchi:
        if rit is None and b and b[0].startswith("R."):
            rit = b
        elif rit is None:
            intro.append(b)
        else:
            strofe.append(b)
    if rit is None or not strofe:
        return [blocchi]
    gruppi = [intro + [rit]]
    for st in strofe:
        st = st[:-1] + [re.sub(r"\s*R\.?\s*$", "", st[-1])]  # tolgo il "R." finale
        gruppi.append([st, rit])
    return gruppi




# ----------------------------------------------------------------------------
# Letture e preghiere alternative
# ----------------------------------------------------------------------------

_RIFERIMENTO = re.compile(r"^\d?\s?[A-Za-zÀ-ÿ]{1,6}\s?\d+[,.:]\d+")      # es. "Sap 6,12-16", "1Ts 4,13-18"
_INTRODUZIONE = re.compile(r"^(Dal|Dalla|Dai|Dagli|Dall['’]|Lettura|Inizio)\b", re.I)
_ETICHETTA = re.compile(r"^(forma\s+(?:breve|lunga)|oppure)\s*:?\s*$", re.I)
_OPPURE = re.compile(r"^oppure\s*:?\s*$", re.I)


def separa_alternative(blocchi):
    """
    Preghiere con alternative ("Oppure:"): restituisce una lista di preghiere,
    ognuna come lista di blocchi. La riga "Oppure:" non compare nelle slide.
    """
    alt = [[]]
    for b in blocchi:
        cur = []
        for r in b:
            if _OPPURE.match(r.strip()):
                if cur:
                    alt[-1].append(cur)
                    cur = []
                alt.append([])
            else:
                cur.append(r)
        if cur:
            alt[-1].append(cur)
    return [a for a in alt if a] or [blocchi]


def separa_lettura(blocchi):
    """
    Divide una lettura in "segmenti" (di solito uno; di piu' se c'e' la "Forma breve" o un'alternativa "Oppure:").
    Ogni segmento: {"etichetta": None | "Forma breve", "annuncio": [righe], "corpo": [paragrafi]}.
    L'annuncio e' la parte iniziale "Dal libro della Sapienza / Sap 6,12-16".
    """
    righe = [r for b in blocchi for r in b]
    segmenti, cur = [], {"etichetta": None, "righe": []}
    for r in righe:
        m = _ETICHETTA.match(r.strip())
        if m:
            if cur["righe"]:
                segmenti.append(cur)
            cur = {"etichetta": " ".join(m.group(1).split()).capitalize(), "righe": []}
        else:
            cur["righe"].append(r)
    if cur["righe"]:
        segmenti.append(cur)

    risultato = []
    for s in segmenti:
        rr = s["righe"]
        if s["etichetta"]:                       # salto il riassunto che precede l'introduzione
            for i, r in enumerate(rr[:4]):
                if _INTRODUZIONE.match(r):
                    rr = rr[i:]
                    break
        annuncio, corpo = [], rr
        for i, r in enumerate(rr[:4]):
            if _RIFERIMENTO.match(r.strip()):
                annuncio, corpo = rr[:i + 1], rr[i + 1:]
                break
        else:
            if rr and _INTRODUZIONE.match(rr[0]):
                annuncio, corpo = [rr[0]], rr[1:]
        risultato.append({"etichetta": s["etichetta"], "annuncio": annuncio, "corpo": corpo})
    return risultato


def analizza_salmo(blocchi):
    """Restituisce (intro, ritornello, strofe): ritornello = lista di righe oppure None."""
    rit, intro, strofe = None, [], []
    for b in blocchi:
        if rit is None and b and b[0].startswith("R."):
            rit = b
        elif rit is None:
            intro.append(b)
        else:
            strofe.append(b[:-1] + [re.sub(r"\s*R\.?\s*$", "", b[-1])])     # tolgo il "R." finale
    intro_righe = [r for b in intro for r in b]
    return intro_righe, rit, strofe


# ----------------------------------------------------------------------------
# Divisione omogenea delle letture (per paragrafi)
# ----------------------------------------------------------------------------

def _partizione(n, altezza_gruppo, limite):
    """
    Divide n elementi in gruppi contigui: prima il numero MINIMO di gruppi,
    poi altezze il piu' possibile uguali tra loro. Restituisce [(inizio, fine), ...].
    """
    if n == 0:
        return []
    k, i = 0, 0
    while i < n:
        j = i + 1
        while j < n and altezza_gruppo(i, j + 1) <= limite:
            j += 1
        i, k = j, k + 1
    inf = float("inf")
    dp = [[inf] * (n + 1) for _ in range(k + 1)]
    da = [[0] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = 0.0
    for g in range(1, k + 1):
        for j in range(g, n + 1):
            for i in range(g - 1, j):
                h = altezza_gruppo(i, j)
                if h > limite and j - i > 1:
                    continue
                c = dp[g - 1][i] + h * h
                if c < dp[g][j]:
                    dp[g][j], da[g][j] = c, i
    if dp[k][n] == inf:
        return [(i, i + 1) for i in range(n)]
    gruppi, j = [], n
    for g in range(k, 0, -1):
        i = da[g][j]
        gruppi.append((i, j))
        j = i
    return gruppi[::-1]


def spezza_bilanciato(testo, size, verso=False):
    """Paragrafo troppo lungo: lo divide in parti di lunghezza simile, alle frasi (poi alle virgole)."""
    if entra([[testo]], size, verso):
        return [testo]
    pezzi = []
    for frase in re.split(r"(?<=[.!?»”])\s+", testo):
        if entra([[frase]], size, verso):
            pezzi.append(frase)
            continue
        for parte in re.split(r"(?<=[;:,])\s+", frase):
            pezzi.extend([parte] if entra([[parte]], size, verso) else spezza_parole(parte, size, verso))

    def alt(i, j):
        return altezza([[" ".join(pezzi[i:j])]], size, verso)
    return [" ".join(pezzi[i:j]) for i, j in _partizione(len(pezzi), alt, ALTEZZA_PT)]


def impagina_paragrafi(paragrafi, size):
    """
    Letture: i paragrafi restano interi (si dividono solo quelli troppo lunghi per una slide)
    e le slide hanno quantita' di testo simili. Restituisce (slide, paragrafi_divisi);
    ogni slide e' una lista di paragrafi.
    """
    paragrafi = [p for p in paragrafi if p.strip()]
    coda = None
    if len(paragrafi) >= 2 and len(paragrafi[-1]) < 40:          # "Parola di Dio." resta con l'ultimo paragrafo
        coda, paragrafi = paragrafi[-1], paragrafi[:-1]
    elementi, divisi = [], 0
    for p in paragrafi:
        parti = spezza_bilanciato(p, size)
        divisi += len(parti) - 1
        elementi.extend([x] for x in parti)
    if coda:
        if elementi:
            elementi[-1] = elementi[-1] + [coda]
        else:
            elementi = [[coda]]

    def alt(i, j):
        return altezza([[r for el in elementi[i:j] for r in el]], size, False)
    slides = [[r for el in elementi[i:j] for r in el] for i, j in _partizione(len(elementi), alt, ALTEZZA_PT)]
    return slides, divisi


# ----------------------------------------------------------------------------
# Grandezza del carattere slide per slide
# ----------------------------------------------------------------------------

def migliore_dimensione(blocchi, verso, massimo, minimo, passo=2):
    """La grandezza piu' grande (tra massimo e minimo) con cui il testo entra; None se non entra."""
    for s in range(massimo, minimo - 1, -passo):
        if entra(blocchi, s, verso):
            return s
    return None


def impagina_individuale(gruppi, verso, massimo, minimo, passo=4):
    """
    Ogni gruppo = una slide, ciascuna alla PROPRIA grandezza (la piu' grande che permette di
    tenere tutto insieme). Un gruppo che non entra nemmeno alla grandezza minima viene diviso.
    Restituisce [(blocchi, grandezza), ...].
    """
    out = []
    for g in gruppi:
        s = migliore_dimensione(g, verso, massimo, minimo, passo)
        if s:
            out.append((g, s))
        else:
            out.extend((sl, minimo) for sl in impagina(g, minimo, verso))
    return out


def impagina_compatta(gruppi, verso, massimo, minimo, soglia=44, passo=2):
    """
    Testi fissi divisi in strofe (Gloria, Credo...): ogni strofa resta intera; strofe vicine
    stanno sulla stessa slide finche' il carattere resta grande (almeno 'soglia' punti).
    Restituisce [(blocchi, grandezza), ...].
    """
    slides, cur = [], None
    for g in gruppi:
        if cur is None:
            cur = list(g)
            continue
        s = migliore_dimensione(cur + g, verso, massimo, minimo, passo)
        if s and s >= soglia:
            cur = cur + g
        else:
            slides.append(cur)
            cur = list(g)
    if cur:
        slides.append(cur)
    return impagina_individuale(slides, verso, massimo, minimo, passo)
