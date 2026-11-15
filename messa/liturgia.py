# -*- coding: utf-8 -*-
"""
Recupero della liturgia del giorno dal sito della CEI.

Punti di attenzione (analisi funzionale, par. 8: il sito puo' cambiare):
  * la data richiesta viene CONFRONTATA con quella scritta nella pagina, cosi' non si
    generano mai slide del giorno sbagliato;
  * se la lettura "normale" della pagina non trova le sezioni, si usa un metodo di riserva
    basato sul solo testo.
"""
import dataclasses
import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from .errori import ErroreMessa

URL = "https://www.chiesacattolica.it/liturgia-del-giorno/"

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

COLORI_LITURGICI = {
    "verde": "3FA34D", "bianco": "F5F5F5", "rosso": "D64545", "viola": "9B6BC4",
    "rosa": "E58FB0", "nero": "9A9A9A", "oro": "D4AF37",
}

TITOLI_NOTI = ["antifona", "colletta", "prima lettura", "salmo responsoriale", "seconda lettura",
               "acclamazione al vangelo", "vangelo", "sulle offerte", "antifona alla comunione",
               "dopo la comunione", "lettura"]

_BLOCCHI = {"p", "div", "li", "ul", "ol", "blockquote", "section", "article"}


@dataclass
class Liturgia:
    data: dt.date
    nome: str = ""
    colore_nome: str = "verde"
    colore_hex: str = COLORI_LITURGICI["verde"]
    sezioni: dict = field(default_factory=dict)   # formulario in uso: titolo normalizzato -> lista di blocchi
    avvisi: list = field(default_factory=list)
    data_pagina: dt.date = None                    # data scritta nella pagina del sito
    formulari: list = field(default_factory=list)  # [{"etichetta": str, "sezioni": {...}}]: piu' messe nello stesso giorno
    etichetta_formulario: str = None               # es. "Messa della notte" (solo se i formulari sono piu' d'uno)

    def trova(self, chiavi):
        for k in chiavi:
            if self.sezioni.get(k):
                return self.sezioni[k]
        return None

    def con_formulario(self, i: int):
        """Copia della liturgia che usa il formulario numero i (0 = il primo)."""
        if len(self.formulari) <= 1:
            return self
        i = max(0, min(int(i), len(self.formulari) - 1))
        f = self.formulari[i]
        return dataclasses.replace(self, sezioni=f["sezioni"], etichetta_formulario=f["etichetta"])


# ----------------------------------------------------------------------------
# lettura della pagina
# ----------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip().lower()


def pulisci_testo(raw: str) -> list:
    """Testo -> lista di blocchi; ogni blocco e' una lista di righe."""
    righe = [re.sub(r"[ \t\xa0]+", " ", r).strip() for r in raw.split("\n")]
    blocchi, corrente = [], []
    for r in righe:
        if r:
            corrente.append(r)
        elif corrente:
            blocchi.append(corrente)
            corrente = []
    if corrente:
        blocchi.append(corrente)
    return blocchi


def _leggi_sezione(h2: Tag) -> str:
    buf, saltati = [], set(id(d) for d in h2.descendants)
    for el in h2.next_elements:
        if isinstance(el, Tag):
            if el.name in ("h1", "h2", "footer", "img"):   # fine della sezione
                break
            if el.name in ("h3", "h4", "script", "style", "noscript"):
                # il sottotitolo-riassunto delle letture non si legge
                saltati.update(id(d) for d in el.descendants)
                continue
            if el.name == "br":
                buf.append("\n")
            elif el.name in _BLOCCHI:
                buf.append("\n\n")
        elif type(el) is NavigableString and id(el) not in saltati:
            buf.append(str(el))
    return "".join(buf)


# Una nuova messa (formulario) inizia quando ricompare una di queste parti d'apertura.
_INIZIO_FORMULARIO = {"antifona", "colletta"}
_ETICHETTA_MESSA = re.compile(r"\bmessa\b|vigilia|\bnotte\b|aurora", re.I)


def _formatta_etichetta(testo: str) -> str:
    t = " ".join(testo.split()).strip(" -–:")
    return t[:1].upper() + t[1:].lower() if t else t


def _etichetta_h2(h2):
    """Titolo che precede il formulario ("Messa della notte"...), se si trova."""
    for prec in h2.find_all_previous(["h1", "h2", "h3", "h4", "h5"], limit=8):
        t = _norm(prec.get_text())
        if t and t not in TITOLI_NOTI and _ETICHETTA_MESSA.search(t):
            return _formatta_etichetta(prec.get_text())
    return None


def _sezioni_da_h2(soup):
    """Restituisce (formulari, ci_sono_alternative): formulari = [{"etichetta", "sezioni"}]."""
    gruppi, corrente, doppioni = [], None, False
    for h2 in soup.find_all("h2"):
        nome = _norm(h2.get_text())
        if not nome:
            continue
        if corrente is None or (nome in corrente["sezioni"] and nome in _INIZIO_FORMULARIO):
            corrente = {"etichetta": _etichetta_h2(h2), "sezioni": {}}
            gruppi.append(corrente)
        if nome in corrente["sezioni"]:
            doppioni = True                      # alternative nello stesso formulario: tengo la prima
            continue
        corrente["sezioni"][nome] = pulisci_testo(_leggi_sezione(h2))
        if nome in TITOLI_NOTI and corrente["etichetta"] is None:
            corrente["etichetta"] = _etichetta_h2(h2)        # prima parte vera del formulario
    return gruppi, doppioni


def _sezioni_da_testo(soup):
    """Metodo di riserva: cerca i titoli noti come righe a se' stanti."""
    righe = [r.strip() for r in soup.get_text("\n").split("\n")]
    gruppi, corrente, titolo, buf, doppioni = [], None, None, [], False
    recenti = []                                   # ultime righe non vuote, per l'etichetta

    def chiudi():
        nonlocal doppioni
        if corrente is not None and titolo:
            if titolo in corrente["sezioni"]:
                doppioni = True
            else:
                corrente["sezioni"][titolo] = pulisci_testo("\n".join(buf))

    for r in righe:
        n = _norm(r)
        if n in TITOLI_NOTI:
            chiudi()
            if corrente is None or (n in corrente["sezioni"] and n in _INIZIO_FORMULARIO):
                etichetta = next((_formatta_etichetta(x) for x in reversed(recenti[-8:])
                                  if _ETICHETTA_MESSA.search(x) and _norm(x) not in TITOLI_NOTI), None)
                corrente = {"etichetta": etichetta, "sezioni": {}}
                gruppi.append(corrente)
            titolo, buf = n, []
        elif titolo and (n.startswith("conferenza episcopale") or n.startswith("copyright")):
            chiudi()
            titolo = None
        elif titolo:
            buf.append(r)
        if n:
            recenti.append(r)
    chiudi()
    return gruppi, doppioni


def leggi_data_pagina(soup):
    """Data scritta nella pagina (dal titolo o dall'intestazione), oppure None."""
    testi = []
    if soup.title:
        testi.append(soup.title.get_text())
    testi.append(soup.get_text(" ")[:3000])
    for t in testi:
        m = re.search(r"(\d{1,2})\s+([A-Za-zì]+)\s+(\d{4})", t)
        while m:
            mese = m.group(2).lower()
            if mese in MESI:
                try:
                    return dt.date(int(m.group(3)), MESI.index(mese) + 1, int(m.group(1)))
                except ValueError:
                    pass
            m = re.search(r"(\d{1,2})\s+([A-Za-zì]+)\s+(\d{4})", t[m.end():])
    return None


# Titoli "di servizio" che NON sono il nome della celebrazione (es. il blocco sull'accessibilita').
_RUMORE = re.compile(r"\bLIS\b|sottotitol|\baudio\b|liturgia della parola|colore liturgico|grandezza testo|"
                     r"conferenza episcopale|^messa del giorno$|lettura a schermo|calendario|santo del giorno|"
                     r"liturgia delle ore|le opere e i giorni|cerca|agenda|cookie|privacy|newsletter", re.I)
_PAROLE_CELEBRAZIONE = re.compile(
    r"DOMENICA|SETTIMANA|SOLENNIT|FESTA|MEMORIA|NATALE|PASQUA|EPIFANIA|PENTECOSTE|ASCENSIONE|TRINIT|CORPO|"
    r"SANGUE|IMMACOLAT|ASSUNZIONE|DEDICAZIONE|SANTI|DEFUNTI|AVVENTO|QUARESIMA|TEMPO|OTTAVA|BATTESIMO|"
    r"PRESENTAZIONE|CRISTO RE|SANTISSIM|MADRE|SACRO CUORE|CONVERSIONE|CATTEDRA|TRASFIGURAZIONE|ESALTAZIONE|"
    r"ANNUNCIAZIONE|VISITAZIONE|LUNED|MARTED|MERCOLED|GIOVED|VENERD|SABATO|VIGILIA", re.I)


def _nome_da_titolo(soup):
    """Dal titolo della pagina: 'Liturgia del giorno 25 Dicembre 2026 - NATALE DEL SIGNORE - sito ufficiale...'."""
    if not soup.title:
        return None
    t = " ".join(soup.title.get_text().split())
    m = re.match(r"^Liturgia del giorno\s+\d{1,2}\s+\S+\s+\d{4}\s*[-–]\s*(.+?)\s*[-–]\s*sito\b", t, re.I)
    if m:
        nome = m.group(1)
    else:
        parti = re.split(r"\s+-\s+", t)
        nome = parti[1] if len(parti) > 2 else None
    return nome.strip() if nome and not _RUMORE.search(nome) else None


def _nome_da_intestazioni(soup):
    """Cerca tra i titoli che precedono la liturgia quello che sembra il nome della celebrazione."""
    migliore, punteggio_migliore = None, 3
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        t = " ".join(h.get_text().split())
        if _norm(t) in TITOLI_NOTI:
            break                                    # qui comincia la liturgia
        if not (6 <= len(t) <= 120) or _RUMORE.search(t):
            continue
        punti = 0
        if t == t.upper() and sum(c.isalpha() for c in t) >= 4:
            punti += 3
        if _PAROLE_CELEBRAZIONE.search(t):
            punti += 4
        if h.name == "h3":
            punti += 1
        if punti > punteggio_migliore:
            migliore, punteggio_migliore = t, punti
    return migliore


def _info_giorno(soup):
    """Nome della celebrazione, nome e colore liturgico."""
    nome = _nome_da_titolo(soup) or _nome_da_intestazioni(soup) or ""
    m = re.search(r"Colore Liturgico\s*([A-Za-zàèéìòù]+)", soup.get_text(" "))
    colore = m.group(1).lower() if m else "verde"
    return nome, colore, COLORI_LITURGICI.get(colore, COLORI_LITURGICI["oro"])


def analizza_html(html: str, data: dt.date) -> Liturgia:
    """Trasforma l'HTML della pagina in un oggetto Liturgia (senza controllare la data)."""
    soup = BeautifulSoup(html, "html.parser")
    liturgia = Liturgia(data=data)

    def noti(gruppi):
        return sum(1 for g in gruppi for k in g["sezioni"] if k in TITOLI_NOTI)

    gruppi, doppioni = _sezioni_da_h2(soup)
    if noti(gruppi) < 2:
        gruppi, doppioni = _sezioni_da_testo(soup)
        if gruppi:
            liturgia.avvisi.append("La pagina del sito ha una struttura diversa dal solito: "
                                   "ho usato un metodo di lettura alternativo. Controlla i testi.")
    gruppi = [g for g in gruppi if any(k in TITOLI_NOTI for k in g["sezioni"])]
    for g in gruppi:
        g["sezioni"] = {k: v for k, v in g["sezioni"].items() if v}

    if len(gruppi) > 1:                            # etichette sempre presenti e diverse tra loro
        etichette = [g["etichetta"] for g in gruppi]
        for i, g in enumerate(gruppi, 1):
            if not g["etichetta"]:
                g["etichetta"] = f"Formulario {i}"
            elif etichette.count(g["etichetta"]) > 1:
                g["etichetta"] = f"{g['etichetta']} ({i})"
    liturgia.formulari = gruppi
    liturgia.sezioni = gruppi[0]["sezioni"] if gruppi else {}
    if len(gruppi) > 1:
        liturgia.etichetta_formulario = gruppi[0]["etichetta"]
    if doppioni:
        liturgia.avvisi.append("Per alcune parti il sito propone più alternative: ho usato la prima. "
                               "Controlla i testi.")
    liturgia.nome, liturgia.colore_nome, liturgia.colore_hex = _info_giorno(soup)
    liturgia.data_pagina = leggi_data_pagina(soup)
    return liturgia


# ----------------------------------------------------------------------------
# scaricamento
# ----------------------------------------------------------------------------

def _indirizzi(data: dt.date):
    d = data.strftime("%Y%m%d")
    return [f"{URL}?data-liturgia={d}", f"{URL}liturgie-del-{d}/"]


def _scarica(url: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (messa-parrocchia)"}, timeout=25)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        # distinguo "senza rete" da "sito che non risponde"
        try:
            requests.head("https://www.google.com", timeout=5)
        except Exception:
            raise ErroreMessa("E01", str(e)[:120])
        raise ErroreMessa("E02", "Il sito non risponde.")
    except requests.exceptions.RequestException as e:
        raise ErroreMessa("E02", str(e)[:120])
    if r.status_code == 404:
        raise ErroreMessa("E03", "Pagina non trovata (404).")
    if r.status_code >= 400:
        raise ErroreMessa("E02", f"Risposta del sito: {r.status_code}.")
    r.encoding = "utf-8"
    return r.text


def recupera_liturgia(data: dt.date, html_prova: str = None) -> Liturgia:
    """
    Scarica e analizza la liturgia della data richiesta.
    html_prova: percorso di un file HTML da usare al posto del sito (solo per prove).
    """
    if html_prova:
        liturgia = analizza_html(Path(html_prova).read_text(encoding="utf-8"), data)
        _controlla(liturgia, data, solo_avviso=True)
        return liturgia

    ultimo_errore, trovata_altra_data = None, None
    for url in _indirizzi(data):
        try:
            html = _scarica(url)
        except ErroreMessa as e:
            if e.codice in ("E01", "E02"):
                raise
            ultimo_errore = e
            continue
        liturgia = analizza_html(html, data)
        d_pagina = liturgia.data_pagina
        if d_pagina is not None and d_pagina != data:
            trovata_altra_data = d_pagina
            continue                       # il sito ha restituito un altro giorno: provo l'indirizzo successivo
        _controlla(liturgia, data)
        return liturgia

    if trovata_altra_data:
        raise ErroreMessa("E03", f"Il sito ha restituito la liturgia del "
                                 f"{trovata_altra_data.strftime('%d/%m/%Y')} invece che del "
                                 f"{data.strftime('%d/%m/%Y')}.")
    raise ultimo_errore or ErroreMessa("E03")


def _controlla(liturgia: Liturgia, data: dt.date, solo_avviso=False):
    if not liturgia.sezioni:
        raise ErroreMessa("E03", "Nella pagina non ho trovato testi liturgici.")
    d = liturgia.data_pagina
    if d is None:
        liturgia.avvisi.append("Non sono riuscito a verificare la data scritta nella pagina del sito.")
    elif d != data and solo_avviso:
        liturgia.avvisi.append(f"ATTENZIONE: la pagina è del {d.strftime('%d/%m/%Y')}.")
