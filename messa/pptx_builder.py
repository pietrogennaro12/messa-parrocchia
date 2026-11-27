# -*- coding: utf-8 -*-
"""
Costruzione del file PowerPoint (16:9, sfondo nero, testo bianco, barra del colore liturgico).

Il "piano" e' una lista di voci, nell'ordine delle slide:
  {"tipo": "frontespizio", "data": date, "celebrazione": str, "parrocchia": str}
  {"tipo": "vuota"}
  {"tipo": "segnaposto", "titolo": str}
  {"tipo": "testo", "titolo": str, "blocchi": [[...]], "modo": "unica" | "salmo" | "testo" | "preghiere",
   "risposta": str (solo "preghiere": la risposta dell'assemblea, in giallo dopo ogni intenzione)}
  {"tipo": "canto", "titolo": str, "titolo_canto": str, "blocchi": [[...]]}
"""
import re

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from . import impaginazione as imp
from .errori import ErroreMessa
from .impaginazione import MARCA, MARCA_ORO, senza_marca
from .preghiere import e_intenzione

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

# Aspetto
SFONDO = "000000"
COLORE_TESTO = "FFFFFF"
COLORE_TITOLO = "F2C94C"       # oro: titoli e ritornello del salmo
COLORE_SECONDARIO = "A6A6A6"

# Grandezze del carattere (punti)
DIM_MASSIMA = 54               # preghiere, salmo, canti: la piu' grande che permette di tenere tutto insieme
DIM_MINIMA = 34                # ...mai sotto questo valore (se non basta, il testo si divide)
DIM_LETTURE = 50               # letture e Vangelo: grandezza fissa, uguale in tutte le slide
DIM_INTESTAZIONE = 24          # titolo in alto a sinistra


def _rgb(h):
    return RGBColor.from_string(h)


# Parole che nei titoli restano minuscole ("Natale del Signore", "Domenica delle Palme")
_MINUSCOLE = {"di", "del", "dello", "della", "dei", "degli", "delle", "da", "dal", "dalla", "dai", "dagli",
              "e", "ed", "a", "al", "alla", "alle", "ai", "agli", "in", "nel", "nella", "nei", "nelle",
              "per", "con", "su", "sul", "sulla", "o", "il", "lo", "la", "le", "i", "gli", "un", "una",
              "tra", "fra", "sopra"}


def formatta_nome(nome: str) -> str:
    """
    'NATALE DEL SIGNORE' -> 'Natale del Signore';
    'XXXII DOMENICA DEL TEMPO ORDINARIO - ANNO A' -> 'XXXII Domenica del Tempo Ordinario - Anno A'.
    Un nome scritto a mano (con maiuscole e minuscole) non viene toccato.
    """
    if nome != nome.upper():
        return nome.strip()
    stato = {"prima": True, "prec": ""}

    def parola(m):
        w = m.group(0)
        low = w.lower()
        # numero romano: "XXXII", "IV"...; una lettera sola ("I") solo a inizio nome ("I Domenica di Avvento"),
        # altrimenti e' l'articolo ("Tutti i fedeli defunti")
        romano = re.fullmatch(r"[IVXLC]+", w) and (len(w) > 1 or (w in ("I", "V", "X") and stato["prima"]))
        if romano:
            out = w
        elif re.fullmatch(r"[A-C]", w) and stato["prec"] == "anno":
            out = w                                              # "Anno A"
        elif "’" in w or "'" in w:                               # "DELL’AURORA" -> "dell’Aurora"
            art, resto = re.split(r"[’']", low, maxsplit=1)
            art = art.capitalize() if stato["prima"] else art
            out = art + w[len(art)] + resto.capitalize()
        elif low in _MINUSCOLE and not stato["prima"]:
            out = low
        else:
            out = low.capitalize()
        stato["prima"], stato["prec"] = False, low
        return out

    return re.sub(r"[^\W_]+(?:[’'][^\W_]+)?", parola, nome).strip()


class Costruttore:
    def __init__(self, font: str, colore_barra: str):
        self.font = font
        self.colore = colore_barra
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(13.333), Inches(7.5)

    # --- elementi base ------------------------------------------------------
    def _slide(self):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])      # layout vuoto
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = _rgb(SFONDO)
        barra = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, self.prs.slide_width, Inches(0.16))
        barra.fill.solid()
        barra.fill.fore_color.rgb = _rgb(self.colore)
        barra.line.fill.background()
        return s

    @staticmethod
    def _testo(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
        tf = slide.shapes.add_textbox(x, y, w, h).text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = 0
        return tf

    def _run(self, p, testo, size, colore=COLORE_TESTO, bold=False):
        r = p.add_run()
        r.text = testo
        r.font.size, r.font.bold, r.font.name = Pt(size), bold, self.font
        r.font.color.rgb = _rgb(colore)
        return r

    # --- tipi di slide ------------------------------------------------------
    def frontespizio(self, data, celebrazione, parrocchia, sottotitolo=None):
        """
        Titolo principale: la ricorrenza (es. "XXXIII Domenica del Tempo Ordinario"), in grassetto e nel
        COLORE LITURGICO del giorno. Sottotitolo: la data. Se il nome non c'e', la data fa da titolo.
        """
        s = self._slide()
        W = self.prs.slide_width
        tf = self._testo(s, Inches(0.8), Inches(1.2), W - Inches(1.6), Inches(5.1), MSO_ANCHOR.MIDDLE)
        nome = formatta_nome(celebrazione or "")
        nome = re.sub(r"\s+[-–]\s+", "\u00a0– ", nome)       # "Ordinario – Anno A": se va a capo, il trattino resta sulla prima riga
        testo_data = f"{GIORNI[data.weekday()].capitalize()} {data.day} {MESI[data.month - 1]} {data.year}"
        if nome:
            dim_titolo = 54 if len(nome) <= 34 else 48 if len(nome) <= 52 else 42
            righe = [(parrocchia.upper(), 28, COLORE_TITOLO, True, 20),
                     (nome, dim_titolo, self.colore, True, 16),
                     (testo_data, 34, COLORE_TESTO, False, 14),
                     (sottotitolo or "", 30, COLORE_TITOLO, False, 14)]          # es. "Messa della notte"
        else:
            righe = [(parrocchia.upper(), 28, COLORE_TITOLO, True, 20),
                     (testo_data, 54, COLORE_TESTO, True, 14),
                     (sottotitolo or "", 30, COLORE_TITOLO, False, 14)]
        primo = True
        for t, size, col, bold, sotto in righe:
            if not t:
                continue
            p = tf.paragraphs[0] if primo else tf.add_paragraph()
            primo = False
            p.alignment = PP_ALIGN.CENTER
            p.space_after = Pt(sotto)
            self._run(p, t, size, col, bold)

    def vuota(self):
        self._slide()

    def segnaposto(self, titolo):
        s = self._slide()
        tf = self._testo(s, Inches(0.8), Inches(2.5), self.prs.slide_width - Inches(1.6),
                         Inches(2.5), MSO_ANCHOR.MIDDLE)
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        self._run(tf.paragraphs[0], titolo.upper(), 54, COLORE_TITOLO, True)

    def testo(self, titolo, blocchi, num, tot, size, verso, allinea="sinistra"):
        s = self._slide()
        W = self.prs.slide_width
        tf = self._testo(s, Inches(0.7), Inches(0.36), W - Inches(3.4), Inches(0.7))
        self._run(tf.paragraphs[0], titolo.upper(), DIM_INTESTAZIONE, COLORE_TITOLO, True)
        if tot > 1:
            tf2 = self._testo(s, W - Inches(2.7), Inches(0.38), Inches(2.0), Inches(0.6))
            tf2.paragraphs[0].alignment = PP_ALIGN.RIGHT
            self._run(tf2.paragraphs[0], f"{num}/{tot}", 22, COLORE_SECONDARIO)

        tf = self._testo(s, Inches(0.7), Inches(1.2), W - Inches(1.4), Inches(5.9), MSO_ANCHOR.MIDDLE)
        primo = True
        for i, b in enumerate(blocchi):
            for j, riga in enumerate(b):
                p = tf.paragraphs[0] if primo else tf.add_paragraph()
                primo = False
                p.line_spacing = 1.05
                p.space_after = Pt(0 if verso else 12)
                if allinea == "centro":
                    p.alignment = PP_ALIGN.CENTER
                if j == 0 and i > 0:
                    p.space_before = Pt(22)
                marcata = riga.startswith(MARCA)
                oro = riga.startswith(MARCA_ORO)                          # risposta dell'assemblea: giallo e grassetto
                riga = senza_marca(riga)
                ritornello = riga.startswith("R.") or oro
                self._run(p, riga, size, COLORE_TITOLO if ritornello else COLORE_TESTO,
                          bold=ritornello or marcata)

    def annuncio(self, titolo, righe, ritornello=None):
        """Slide che annuncia una lettura: titolo grande + "Dal libro della Sapienza / Sap 6,12-16"."""
        s = self._slide()
        W = self.prs.slide_width
        tf = self._testo(s, Inches(0.8), Inches(0.9), W - Inches(1.6), Inches(5.9), MSO_ANCHOR.MIDDLE)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        p.space_after = Pt(28)
        self._run(p, titolo.upper(), 54 if len(titolo) <= 24 else 46, COLORE_TITOLO, True)
        for r in righe:
            p = tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            p.space_after = Pt(10)
            self._run(p, r, 44)
        for j, r in enumerate(ritornello or []):
            p = tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            p.space_before = Pt(26 if j == 0 else 0)
            self._run(p, r, 44, COLORE_TITOLO, True)

    # --- sezioni con impaginazione -----------------------------------------
    def sezione_testo(self, titolo, blocchi, modo, risposta=None):
        if modo == "lettura":
            return self._lettura(titolo, blocchi)
        if modo == "salmo":
            return self._salmo(titolo, blocchi)
        if modo == "unica":
            return self._preghiera(titolo, blocchi)
        if modo == "fisso":
            # testo fisso a strofe: strofe intere, piu' strofe per slide se il carattere resta grande
            slides = imp.impagina_compatta([[b] for b in blocchi], True, DIM_MASSIMA, DIM_MINIMA)
            for k, (g, size) in enumerate(slides, 1):
                self.testo(titolo, g, k, len(slides), size, True)
            return
        # "preghiere dei fedeli": prima UNA slide con il solo titolo, poi UNA slide per ogni preghiera; alla fine
        # di ogni intenzione la risposta dell'assemblea in giallo e grassetto (come il ritornello del salmo)
        self.segnaposto(titolo)
        risposta = (risposta or "").strip()
        gruppi = [[b, [MARCA_ORO + risposta]] if risposta and e_intenzione(b, risposta) else [b] for b in blocchi]
        verso = imp.e_verso(blocchi)
        slides = imp.impagina_individuale(gruppi, verso, DIM_MASSIMA, DIM_MINIMA)
        for k, (g, size) in enumerate(slides, 1):
            self.testo(titolo, g, k, len(slides), size, verso)

    def _lettura(self, titolo, blocchi):
        """Annuncio + testo diviso per paragrafi in slide omogenee (+ eventuale forma breve)."""
        for seg in imp.separa_lettura(blocchi):
            tit = titolo if not seg["etichetta"] else f"{titolo} · {seg['etichetta']}"
            if seg["annuncio"]:
                self.annuncio(tit, seg["annuncio"])
            slides, _ = imp.impagina_paragrafi(seg["corpo"], DIM_LETTURE)
            for k, righe in enumerate(slides, 1):
                self.testo(tit, [righe], k, len(slides), DIM_LETTURE, False)

    def _salmo(self, titolo, blocchi):
        intro, rit, strofe = imp.analizza_salmo(blocchi)
        if rit is None or not strofe:                       # struttura insolita: tutto insieme
            self._preghiera(titolo, blocchi)
            return
        self.annuncio(titolo, intro, rit)
        gruppi = [[st, rit] for st in strofe]               # ritornello dopo OGNI strofa
        slides, size = imp.impagina_gruppi(gruppi, True, DIM_MASSIMA, DIM_MINIMA, False)
        for k, g in enumerate(slides, 1):
            self.testo(titolo, g, k, len(slides), size, True)

    def _preghiera(self, titolo, blocchi):
        """Preghiera intera su una slide; le alternative ("Oppure:") su slide separate."""
        for n, alt in enumerate(imp.separa_alternative(blocchi)):
            tit = titolo if n == 0 else f"{titolo} · oppure"
            verso = imp.e_verso(alt)
            slides = imp.impagina_individuale([alt], verso, DIM_MASSIMA, DIM_MINIMA, 2)
            for k, (g, size) in enumerate(slides, 1):
                self.testo(tit, g, k, len(slides), size, verso)

    def canto(self, titolo, titolo_canto, blocchi):
        slides = imp.impagina_individuale([[b] for b in blocchi], True, DIM_MASSIMA, DIM_MINIMA)
        for k, (g, size) in enumerate(slides, 1):
            self.testo(f"{titolo} · {titolo_canto}", g, k, len(slides), size, True, "centro")

    def salva(self, percorso):
        self.prs.save(str(percorso))


def costruisci(piano, font, colore_barra, percorso):
    """Crea il .pptx; restituisce il numero di slide. Errori -> E08."""
    try:
        c = Costruttore(font, colore_barra)
        for v in piano:
            t = v["tipo"]
            if t == "frontespizio":
                c.frontespizio(v["data"], v["celebrazione"], v["parrocchia"], v.get("sottotitolo"))
            elif t == "vuota":
                c.vuota()
            elif t == "segnaposto":
                c.segnaposto(v["titolo"])
            elif t == "testo":
                c.sezione_testo(v["titolo"], v["blocchi"], v["modo"], v.get("risposta"))
            elif t == "canto":
                c.canto(v["titolo"], v["titolo_canto"], v["blocchi"])
        c.salva(percorso)
        return len(c.prs.slides)
    except ErroreMessa:
        raise
    except PermissionError:
        raise ErroreMessa("E08", "Non riesco a scrivere il file: è aperto in PowerPoint? Chiudilo e riprova.")
    except Exception as e:
        raise ErroreMessa("E08", str(e)[:150])
