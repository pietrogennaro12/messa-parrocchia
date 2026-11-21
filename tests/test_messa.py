# -*- coding: utf-8 -*-
"""Test automatici. Avvio:  python -m unittest discover -s tests -v"""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests
from pptx import Presentation

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))

from messa import impaginazione as imp                       # noqa: E402
from messa import liturgia as lit                            # noqa: E402
from messa.canti import ArchivioCanti                        # noqa: E402
from messa.errori import ErroreMessa                         # noqa: E402
from messa.generatore import genera, prepara_piano           # noqa: E402
from messa.preghiere import leggi_preghiere                  # noqa: E402
from messa.sezioni import SEZIONI                            # noqa: E402
from messa import config                                     # noqa: E402

HTML = (QUI / "pagina_cei_esempio.html").read_text(encoding="utf-8")
HTML8 = (QUI / "pagina_cei_8novembre.html").read_text(encoding="utf-8")
DATA = dt.date(2026, 11, 7)
DATA8 = dt.date(2026, 11, 8)
HTML_NATALE = (QUI / "pagina_cei_natale.html").read_text(encoding="utf-8")
DATA_NATALE = dt.date(2026, 12, 25)
HTML9 = (QUI / "pagina_cei_9novembre.html").read_text(encoding="utf-8")
DATA9 = dt.date(2026, 11, 9)


class TestLiturgia(unittest.TestCase):
    def test_sezioni_e_giorno(self):
        l = lit.analizza_html(HTML, DATA)
        for k in ("colletta", "prima lettura", "salmo responsoriale", "vangelo", "sulle offerte", "dopo la comunione"):
            self.assertIn(k, l.sezioni)
        self.assertIn("XXXI", l.nome)
        self.assertEqual(l.colore_nome, "verde")
        self.assertEqual(l.data_pagina, DATA)

    def test_sottotitolo_delle_letture_non_incluso(self):
        l = lit.analizza_html(HTML, DATA)
        self.assertTrue(l.sezioni["prima lettura"][0][0].startswith("Dalla lettera"))

    def test_metodo_di_riserva(self):
        html = ("<html><title>Liturgia del giorno 07 Novembre 2026 - X</title><body>"
                "<p>Colletta</p><p>Dio onnipotente.<br>Per Cristo.</p>"
                "<p>Vangelo</p><p>In quel tempo.</p><p>Conferenza Episcopale Italiana</p></body></html>")
        l = lit.analizza_html(html, DATA)
        self.assertIn("colletta", l.sezioni)
        self.assertEqual(l.sezioni["vangelo"][0][0], "In quel tempo.")
        self.assertTrue(l.avvisi)

    def test_data_sbagliata_dal_sito_E03(self):
        altra = HTML.replace("07 Novembre 2026", "09 Novembre 2026")
        with mock.patch.object(lit, "_scarica", return_value=altra):
            with self.assertRaises(ErroreMessa) as c:
                lit.recupera_liturgia(DATA)
        self.assertEqual(c.exception.codice, "E03")

    def test_data_giusta_al_secondo_tentativo(self):
        altra = HTML.replace("07 Novembre 2026", "09 Novembre 2026")
        with mock.patch.object(lit, "_scarica", side_effect=[altra, HTML]):
            self.assertEqual(lit.recupera_liturgia(DATA).data_pagina, DATA)

    def test_nessuna_connessione_E01(self):
        with mock.patch("requests.get", side_effect=requests.exceptions.ConnectionError("x")), \
             mock.patch("requests.head", side_effect=requests.exceptions.ConnectionError("x")):
            with self.assertRaises(ErroreMessa) as c:
                lit.recupera_liturgia(DATA)
        self.assertEqual(c.exception.codice, "E01")

    def test_sito_non_disponibile_E02(self):
        risposta = mock.Mock(status_code=503, text="")
        with mock.patch("requests.get", return_value=risposta):
            with self.assertRaises(ErroreMessa) as c:
                lit.recupera_liturgia(DATA)
        self.assertEqual(c.exception.codice, "E02")


class TestArchivi(unittest.TestCase):
    def test_canti_mancante_E04(self):
        with self.assertRaises(ErroreMessa) as c:
            ArchivioCanti(Path("/non/esiste.pdf"))
        self.assertEqual(c.exception.codice, "E04")

    def test_pdf_illeggibile_E06(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "rotto.pdf"
            f.write_bytes(b"questo non e' un pdf")
            with self.assertRaises(ErroreMessa) as c:
                ArchivioCanti(f)
            self.assertEqual(c.exception.codice, "E06")
            with self.assertRaises(ErroreMessa) as c:
                leggi_preghiere(f)
            self.assertEqual(c.exception.codice, "E06")

    def test_preghiere_mancante_E05(self):
        with self.assertRaises(ErroreMessa) as c:
            leggi_preghiere(Path("/non/esiste.pdf"))
        self.assertEqual(c.exception.codice, "E05")

    def test_preghiere_lette(self):
        blocchi = leggi_preghiere(QUI / "preghiere_esempio.pdf")
        self.assertGreaterEqual(len(blocchi), 5)
        self.assertTrue(any("Ascoltaci, o Signore" in r for b in blocchi for r in b))


class TestImpaginazione(unittest.TestCase):
    def test_preghiera_su_una_sola_slide(self):
        l = lit.analizza_html(HTML, DATA)
        for chiave in ("colletta", "sulle offerte", "dopo la comunione"):
            slides, size = imp.impagina_gruppi([l.sezioni[chiave]], True, 50, 34, False)
            self.assertEqual(len(slides), 1, chiave)
            self.assertGreaterEqual(size, 34)

    def test_salmo_una_strofa_per_slide_con_ritornello(self):
        l = lit.analizza_html(HTML, DATA)
        slides, _ = imp.impagina_gruppi(imp.gruppi_salmo(l.sezioni["salmo responsoriale"]), True, 50, 34, False)
        self.assertEqual(len(slides), 4)                       # intestazione + 3 strofe
        for s in slides[1:]:
            ultimo = s[-1][-1]
            self.assertTrue(ultimo.startswith("R."))           # ritornello dopo ogni strofa
            self.assertFalse(any(r.rstrip().endswith(" R.") for b in s for r in b))

    def test_lettura_lunga_divisa_senza_perdere_testo(self):
        l = lit.analizza_html(HTML, DATA)
        orig = " ".join(r for b in l.sezioni["vangelo"] for r in b).split()
        slides = imp.impagina(l.sezioni["vangelo"], 44, False)
        self.assertGreater(len(slides), 1)
        ricomposto = " ".join(r for s in slides for b in s for r in b).split()
        self.assertEqual(orig, ricomposto)                    # stesso testo, stesso ordine


class TestGenerazione(unittest.TestCase):
    def setUp(self):
        self.cfg = config.carica()
        self.cfg["pdf_preghiere"] = str(QUI / "preghiere_esempio.pdf")
        self.lit = lit.analizza_html(HTML, DATA)

    def test_ordine_fisso_e_sezioni_escluse(self):
        # selezione data in ordine inverso: l'ordine finale deve restare quello del documento
        scelte = {"canto_finale", "vangelo", "colletta", "frontespizio", "salmo"}
        piano, avvisi = prepara_piano(DATA, scelte, {}, self.lit, None, ErroreMessa("E04"), self.cfg)
        titoli = [v.get("titolo", v["tipo"]) for v in piano]
        self.assertEqual(titoli, ["frontespizio", "Colletta", "Salmo", "Vangelo", "Canto finale"])
        self.assertEqual([a["codice"] for a in avvisi], ["E04"])   # canto richiesto ma archivio assente

    def test_canto_non_selezionato_E07(self):
        arch = mock.Mock()
        piano, avvisi = prepara_piano(DATA, {"gloria"}, {"gloria": None}, self.lit, arch, None, self.cfg)
        self.assertEqual(avvisi[0]["codice"], "E07")
        self.assertEqual(piano[0]["tipo"], "segnaposto")

    def test_sezione_non_prevista_non_genera_slide(self):
        piano, avvisi = prepara_piano(DATA, {"seconda_lettura"}, {}, self.lit, None, None, self.cfg)
        self.assertEqual(piano, [])
        self.assertEqual(avvisi[0]["codice"], "INFO")

    def test_file_pptx_valido(self):
        scelte = {s["id"] for s in SEZIONI if s["fonte"] in ("sistema", "cei", "fisso", "preghiere", "scelta")}
        piano, _ = prepara_piano(DATA, scelte, {}, self.lit, None, None, self.cfg)
        with tempfile.TemporaryDirectory() as d:
            n, dest = genera(piano, self.cfg, self.lit.colore_hex, Path(d), "prova.pptx")
            self.assertGreater(n, 5)
            p = Presentation(str(dest))
            self.assertEqual(len(p.slides), n)
            self.assertAlmostEqual(p.slide_width / p.slide_height, 16 / 9, places=2)
            # un secondo salvataggio con lo stesso nome richiede conferma
            self.assertIsNone(genera(piano, self.cfg, self.lit.colore_hex, Path(d), "prova.pptx")[0])

    def test_errore_generazione_E08(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "file"
            f.write_text("x")
            with self.assertRaises(ErroreMessa) as c:
                genera([{"tipo": "vuota"}], self.cfg, "3FA34D", f / "sotto", "a.pptx")   # cartella impossibile
            self.assertEqual(c.exception.codice, "E08")


def _testo(slide):
    return [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.strip()]


class TestMiglioramenti(unittest.TestCase):
    """Annunci delle letture, paragrafi, alternative, frontespizio ripetuto."""

    def setUp(self):
        self.cfg = config.carica()
        self.cfg["pdf_preghiere"] = str(QUI / "preghiere_esempio.pdf")
        self.lit = lit.analizza_html(HTML8, DATA8)

    def _deck(self, scelte):
        piano, _ = prepara_piano(DATA8, set(scelte), {}, self.lit, None, None, self.cfg)
        d = tempfile.mkdtemp()
        n, dest = genera(piano, self.cfg, self.lit.colore_hex, Path(d), "t.pptx")
        return Presentation(str(dest))

    def test_annuncio_lettura(self):
        segmenti = imp.separa_lettura(self.lit.sezioni["prima lettura"])
        self.assertEqual(len(segmenti), 1)
        self.assertEqual(segmenti[0]["annuncio"], ["Dal libro della Sapienza", "Sap 6,12-16"])
        self.assertFalse(any("Sap 6,12-16" in r for r in segmenti[0]["corpo"]))

    def test_forma_breve_con_proprio_annuncio(self):
        seg = imp.separa_lettura(self.lit.sezioni["seconda lettura"])
        self.assertEqual([s["etichetta"] for s in seg], [None, "Forma breve"])
        self.assertEqual(seg[1]["annuncio"][-1], "1Ts 4,13-14")          # il riassunto della forma breve non c'e'
        self.assertNotIn("Forma breve:", [r for s in seg for r in s["corpo"]])

    def test_slide_annuncio_nel_file(self):
        p = self._deck({"prima_lettura", "vangelo"})
        primo = _testo(p.slides[0])
        self.assertTrue(primo[0].startswith("PRIMA LETTURA"))
        self.assertIn("Dal libro della Sapienza", primo[0])
        self.assertIn("Sap 6,12-16", primo[0])
        titoli = [_testo(s)[0].split("\n")[0] for s in p.slides]
        self.assertIn("VANGELO", titoli)

    def test_lettura_per_paragrafi_senza_perdere_testo(self):
        for chiave in ("prima lettura", "seconda lettura", "vangelo"):
            for seg in imp.separa_lettura(self.lit.sezioni[chiave]):
                slides, _ = imp.impagina_paragrafi(seg["corpo"], 50)
                orig = " ".join(seg["corpo"]).split()
                self.assertEqual(orig, " ".join(r for s in slides for r in s).split(), chiave)

    def test_paragrafi_interi_quando_possibile(self):
        paragrafi = ["Prima frase breve.", "Seconda frase breve e un po' piu' lunga.", "Terza.", "Quarta frase di prova."]
        slides, divisi = imp.impagina_paragrafi(paragrafi, 50)
        self.assertEqual(divisi, 0)
        for s in slides:                     # nessun paragrafo e' stato spezzato
            for r in s:
                self.assertIn(r, paragrafi)

    def test_slide_omogenee(self):
        corpo = imp.separa_lettura(self.lit.sezioni["vangelo"])[0]["corpo"]
        slides, _ = imp.impagina_paragrafi(corpo, 50)
        alt = [imp.altezza([s], 50, False) for s in slides[:-1]]        # l'ultima puo' essere piu' corta
        self.assertGreater(len(alt), 3)
        self.assertLess(max(alt) - min(alt), imp.ALTEZZA_PT * 0.35)

    def test_colletta_alternative_su_slide_separate(self):
        alt = imp.separa_alternative(self.lit.sezioni["colletta"])
        self.assertEqual(len(alt), 2)
        self.assertFalse(any("Oppure" in r for a in alt for b in a for r in b))
        p = self._deck({"colletta"})
        self.assertEqual(len(p.slides), 2)
        self.assertTrue(_testo(p.slides[0])[0].startswith("COLLETTA"))
        self.assertIn("OPPURE", _testo(p.slides[1])[0])
        self.assertNotIn("Oppure", " ".join(_testo(p.slides[0]) + _testo(p.slides[1])))

    def test_frontespizio_ripetuto(self):
        piano, _ = prepara_piano(DATA8, {"frontespizio", "atto_penitenziale", "professione_fede"}, {}, self.lit,
                                 None, None, self.cfg,
                                 {"atto_penitenziale": "frontespizio", "professione_fede": "frontespizio"})
        d = tempfile.mkdtemp()
        genera(piano, self.cfg, self.lit.colore_hex, Path(d), "t.pptx")
        p = Presentation(str(Path(d) / "t.pptx"))
        self.assertEqual(len(p.slides), 3)
        testi = [" ".join(_testo(s)) for s in p.slides]
        self.assertEqual(testi[0], testi[1])
        self.assertEqual(testi[0], testi[2])
        self.assertIn("PARROCCHIA DI TERRANEGRA", testi[0])

    def test_carattere_piu_grande(self):
        p = self._deck({"prima_lettura", "salmo", "colletta"})
        dim = set()
        for s in p.slides:
            for sh in s.shapes:
                if sh.has_text_frame:
                    for para in sh.text_frame.paragraphs:
                        for r in para.runs:
                            if r.font.size:
                                dim.add(r.font.size.pt)
        self.assertIn(50.0, dim)                  # letture a 50 punti
        self.assertTrue(all(d >= 22 for d in dim))
        corpo = [d for d in dim if d > 30]
        self.assertGreaterEqual(min(corpo), 34)


class TestVarianti(unittest.TestCase):
    """Gloria canto/preghiera, Atto penitenziale, Professione di fede, testi fissi."""

    def setUp(self):
        self.cfg = config.carica()
        self.lit = lit.analizza_html(HTML8, DATA8)

    def _piano(self, scelte, varianti=None, canti=None, archivio=None):
        return prepara_piano(DATA8, set(scelte), canti or {}, self.lit, archivio, None, self.cfg, varianti)

    def _deck(self, scelte, varianti=None):
        piano, avvisi = self._piano(scelte, varianti)
        d = tempfile.mkdtemp()
        genera(piano, self.cfg, self.lit.colore_hex, Path(d), "t.pptx")
        return Presentation(str(Path(d) / "t.pptx")), avvisi

    def test_testi_fissi_completi(self):
        from messa.testi import carica_testo
        attese = {"gloria": ("Gloria a Dio nell’alto dei cieli", "Amen."),
                  "credo": ("Credo in un solo Dio,", "Amen."),
                  "promesse_battesimali": ("Rinunciate a Satana?", "Amen"),
                  "confesso": ("Confesso a Dio onnipotente", "il Signore Dio nostro."),
                  "pieta_di_noi": ("Pietà di noi, Signore.", "E donaci la tua salvezza.")}
        for nome, (inizio, fine) in attese.items():
            righe = [r.lstrip(imp.MARCA) for b in carica_testo(nome) for r in b]
            self.assertTrue(righe[0].startswith(inizio), nome)
            self.assertTrue(righe[-1].endswith(fine), nome)

    def test_gloria_come_preghiera(self):
        piano, avvisi = self._piano({"gloria"}, {"gloria": "preghiera"})
        self.assertEqual(avvisi, [])                       # nessun canto richiesto
        self.assertEqual(piano[0]["modo"], "fisso")
        p, _ = self._deck({"gloria"}, {"gloria": "preghiera"})
        testo = " ".join(" ".join(_testo(s)) for s in p.slides)
        self.assertIn("Gloria a Dio nell’alto dei cieli", testo)
        self.assertIn("nella gloria di Dio Padre.", testo)
        self.assertGreaterEqual(len(p.slides), 3)

    def test_gloria_come_canto_richiede_il_canto(self):
        arch = mock.Mock()
        piano, avvisi = self._piano({"gloria"}, {"gloria": "canto"}, {"gloria": None}, arch)
        self.assertEqual(avvisi[0]["codice"], "E07")
        # predefinito = canto (comportamento precedente)
        piano, avvisi = self._piano({"gloria"}, None, {"gloria": None}, arch)
        self.assertEqual(avvisi[0]["codice"], "E07")

    def test_professione_di_fede_opzioni(self):
        for var, atteso in (("credo", "Credo in un solo Dio"), ("promesse", "Rinunciate a Satana")):
            p, _ = self._deck({"professione_fede"}, {"professione_fede": var})
            testo = " ".join(" ".join(_testo(s)) for s in p.slides)
            self.assertIn(atteso, testo, var)
            self.assertIn("PROFESSIONE DI FEDE", _testo(p.slides[0])[0])

    def test_promesse_risposte_in_grassetto(self):
        p, _ = self._deck({"professione_fede"}, {"professione_fede": "promesse"})
        grassetti = set()
        for s in p.slides:
            for sh in s.shapes:
                if sh.has_text_frame:
                    for para in sh.text_frame.paragraphs:
                        for r in para.runs:
                            if r.font.bold and r.text in ("Rinuncio", "Credo"):
                                grassetti.add(r.text)
        self.assertEqual(grassetti, {"Rinuncio", "Credo"})

    def test_atto_penitenziale_opzioni(self):
        for var, atteso in (("confesso", "Confesso a Dio onnipotente"), ("pieta", "Contro di te abbiamo peccato.")):
            p, _ = self._deck({"atto_penitenziale"}, {"atto_penitenziale": var})
            self.assertIn(atteso, " ".join(" ".join(_testo(s)) for s in p.slides), var)

    def test_pieta_di_noi_su_una_slide(self):
        p, _ = self._deck({"atto_penitenziale"}, {"atto_penitenziale": "pieta"})
        self.assertEqual(len(p.slides), 1)

    def test_strofe_mai_divise(self):
        from messa.testi import carica_testo
        for nome in ("gloria", "credo", "promesse_battesimali", "confesso"):
            blocchi = carica_testo(nome)
            for sl, size in imp.impagina_compatta([[b] for b in blocchi], True, 54, 34):
                self.assertGreaterEqual(size, 34)
            ricomposto = [r for sl, _ in imp.impagina_compatta([[b] for b in blocchi], True, 54, 34)
                          for b in sl for r in b]
            self.assertEqual(ricomposto, [r for b in blocchi for r in b], nome)   # stesso testo, stesso ordine

    def test_ordine_fisso_con_varianti(self):
        scelte = {"professione_fede", "gloria", "atto_penitenziale", "frontespizio"}
        piano, _ = self._piano(scelte, {"gloria": "preghiera", "atto_penitenziale": "confesso",
                                         "professione_fede": "credo"})
        titoli = [v.get("titolo", v["tipo"]) for v in piano]
        self.assertEqual(titoli, ["frontespizio", "Atto penitenziale · Confesso", "Gloria",
                                  "Professione di fede · Credo"])

    def test_testo_mancante_E09(self):
        from messa import testi
        with mock.patch.object(testi, "CARTELLA_TESTI", Path("/non/esiste")):
            piano, avvisi = self._piano({"gloria"}, {"gloria": "preghiera"})
        self.assertEqual(avvisi[0]["codice"], "E09")
        self.assertEqual(piano[0]["tipo"], "segnaposto")

    def test_frontespizio_ripetuto_serve_la_celebrazione(self):
        from messa.generatore import usa_frontespizio
        self.assertTrue(usa_frontespizio({"atto_penitenziale"}, {"atto_penitenziale": "frontespizio"}))
        self.assertFalse(usa_frontespizio({"atto_penitenziale"}, {"atto_penitenziale": "confesso"}))


class _ArchivioFinto:
    def per_id(self, i):
        return {"id": int(i), "titolo": f"CANTO {i}", "blocchi": [["Riga uno", "Riga due"]]}


class TestFormulariEExtra(unittest.TestCase):
    def setUp(self):
        self.cfg = config.carica()
        self.natale = lit.analizza_html(HTML_NATALE, DATA_NATALE)

    # --- più messe nello stesso giorno ---
    def test_formulari_riconosciuti(self):
        self.assertEqual([f["etichetta"] for f in self.natale.formulari], ["Messa della notte", "Messa del giorno"])
        self.assertEqual(self.natale.etichetta_formulario, "Messa della notte")

    def test_giorno_normale_un_solo_formulario(self):
        l = lit.analizza_html(HTML8, DATA8)
        self.assertEqual(len(l.formulari), 1)
        self.assertIsNone(l.etichetta_formulario)

    def test_cambio_formulario_cambia_i_testi(self):
        for i, inizio in ((0, "O Dio, che hai illuminato"), (1, "O Dio, che in modo mirabile")):
            f = self.natale.con_formulario(i)
            self.assertTrue(f.trova(["colletta"])[0][0].startswith(inizio), i)
            self.assertEqual(f.etichetta_formulario, self.natale.formulari[i]["etichetta"])
        self.assertIn("Verbo", " ".join(r for b in self.natale.con_formulario(1).trova(["vangelo"]) for r in b))
        self.assertIs(self.natale.con_formulario(99).sezioni, self.natale.formulari[1]["sezioni"])   # indice fuori scala

    def test_alternative_nella_stessa_messa_non_sono_formulari(self):
        html = HTML8.replace("<h2>Salmo Responsoriale</h2>", "<h2>Prima Lettura</h2><p>Altra lettura.</p><h2>Salmo Responsoriale</h2>")
        l = lit.analizza_html(html, DATA8)
        self.assertEqual(len(l.formulari), 1)
        self.assertTrue(any("alternative" in a for a in l.avvisi))

    def test_frontespizio_con_nome_della_messa(self):
        for i, etichetta in ((0, "Messa della notte"), (1, "Messa del giorno")):
            f = self.natale.con_formulario(i)
            piano, _ = prepara_piano(DATA_NATALE, {"frontespizio", "colletta"}, {}, f, None, None, self.cfg)
            d = tempfile.mkdtemp()
            genera(piano, self.cfg, f.colore_hex, Path(d), "t.pptx")
            p = Presentation(str(Path(d) / "t.pptx"))
            self.assertIn(etichetta, " ".join(_testo(p.slides[0])))
        # giorno normale: nessuna riga in piu'
        l = lit.analizza_html(HTML8, DATA8)
        piano, _ = prepara_piano(DATA8, {"frontespizio"}, {}, l, None, None, self.cfg)
        self.assertIsNone(piano[0]["sottotitolo"])

    def test_server_propone_i_formulari(self):
        from messa.server import Servizio
        sv = Servizio(html_prova=str(QUI / "pagina_cei_natale.html"))
        r = sv.carica_liturgia("2026-12-25")
        self.assertEqual([f["etichetta"] for f in r["formulari"]], ["Messa della notte", "Messa del giorno"])
        self.assertIn("colletta", r["formulari"][1]["disponibili"])

    # --- canti aggiuntivi ---
    def _piano(self, scelte, extra, canti=None):
        l = lit.analizza_html(HTML8, DATA8)
        return prepara_piano(DATA8, set(scelte), canti or {}, l, _ArchivioFinto(), None, self.cfg, None, extra)

    def test_extra_subito_dopo_la_sezione(self):
        piano, avvisi = self._piano({"frontespizio", "colletta", "vangelo", "sulle_offerte"},
                                    [{"id": 5, "dopo": "vangelo", "etichetta": "Canto di ringraziamento"}])
        self.assertEqual([v.get("titolo", v["tipo"]) for v in piano],
                         ["frontespizio", "Colletta", "Vangelo", "Canto di ringraziamento", "Preghiera sulle offerte"])
        self.assertEqual(piano[3]["titolo_canto"], "CANTO 5")
        self.assertEqual(avvisi, [])

    def test_piu_extra_nello_stesso_punto_restano_in_ordine(self):
        piano, _ = self._piano({"vangelo"}, [{"id": 1, "dopo": "vangelo", "etichetta": "Primo"},
                                             {"id": 2, "dopo": "vangelo", "etichetta": "Secondo"}])
        self.assertEqual([v["titolo"] for v in piano], ["Vangelo", "Primo", "Secondo"])

    def test_extra_dopo_una_sezione_non_selezionata(self):
        piano, _ = self._piano({"frontespizio", "canto_finale"}, [{"id": 3, "dopo": "canto_comunione", "etichetta": ""}],
                               {"finale": 9})
        self.assertEqual([v.get("titolo", v["tipo"]) for v in piano], ["frontespizio", "Canto aggiuntivo", "Canto finale"])

    def test_extra_senza_nome_e_posizione_sconosciuta(self):
        piano, _ = self._piano({"frontespizio"}, [{"id": 4, "dopo": "boh", "etichetta": "  "}])
        self.assertEqual(piano[-1]["titolo"], "Canto aggiuntivo")          # in fondo

    def test_extra_senza_canto_E07(self):
        piano, avvisi = self._piano({"frontespizio"}, [{"id": None, "dopo": "frontespizio", "etichetta": "Alla Madonna"}])
        self.assertEqual(avvisi[0]["codice"], "E07")
        self.assertEqual(avvisi[0]["sezione"], "Alla Madonna")
        self.assertEqual(piano[-1], {"tipo": "segnaposto", "titolo": "Alla Madonna"})

    def test_extra_nel_file_pptx(self):
        piano, _ = self._piano({"vangelo"}, [{"id": 7, "dopo": "vangelo", "etichetta": "Alla Madonna"}])
        d = tempfile.mkdtemp()
        genera(piano, self.cfg, "3FA34D", Path(d), "t.pptx")
        p = Presentation(str(Path(d) / "t.pptx"))
        intestazioni = [_testo(sl)[0].split("\n")[0] for sl in p.slides]
        self.assertIn("ALLA MADONNA · CANTO 7", intestazioni)
        self.assertGreater(intestazioni.index("ALLA MADONNA · CANTO 7"), intestazioni.index("VANGELO"))


class TestNomeCelebrazione(unittest.TestCase):
    """Il nome della celebrazione non deve mai essere un titolo di servizio (es. blocco LIS)."""

    def test_nome_dal_titolo_della_pagina(self):
        self.assertEqual(lit.analizza_html(HTML_NATALE, DATA_NATALE).nome, "NATALE DEL SIGNORE")
        self.assertEqual(lit.analizza_html(HTML9, DATA9).nome, "DEDICAZIONE DELLA BASILICA LATERANENSE – FESTA")
        self.assertEqual(lit.analizza_html(HTML8, DATA8).nome, "XXXII DOMENICA DEL TEMPO ORDINARIO - ANNO A")

    def test_il_blocco_LIS_non_e_il_nome(self):
        self.assertIn("Liturgia della Parola in LIS", HTML_NATALE)           # la pagina di prova lo contiene
        for l in (lit.analizza_html(HTML_NATALE, DATA_NATALE),):
            self.assertNotIn("LIS", l.nome)
            self.assertNotIn("sottotitol", l.nome.lower())

    def test_senza_titolo_utile_si_cerca_tra_le_intestazioni(self):
        html = HTML_NATALE.replace(
            "<title>Liturgia del giorno 25 Dicembre 2026 - NATALE DEL SIGNORE - sito ufficiale della CEI - Chiesacattolica.it</title>",
            "<title>Liturgia del giorno</title>")
        self.assertNotIn("NATALE DEL SIGNORE -", html)
        l = lit.analizza_html(html, DATA_NATALE)
        self.assertEqual(l.nome, "NATALE DEL SIGNORE")                       # salta il blocco LIS

    def test_solo_titoli_di_servizio_nome_vuoto(self):
        html = ("<html><head><title>Liturgia del giorno</title></head><body><h1>Messa del Giorno</h1>"
                "<h3>Liturgia della Parola in LIS, sottotitolazione e audio</h3><p>Colore Liturgico verde</p>"
                "<h2>Colletta</h2><p>Testo.</p><h2>Vangelo</h2><p>Altro testo.</p></body></html>")
        l = lit.analizza_html(html, DATA)
        self.assertEqual(l.nome, "")                                         # meglio vuoto che sbagliato
        self.assertEqual(l.colore_nome, "verde")

    def test_nome_scritto_a_mano_resta_com_e(self):
        from messa.pptx_builder import formatta_nome
        self.assertEqual(formatta_nome("Natale del Signore – Messa di mezzanotte"), "Natale del Signore – Messa di mezzanotte")
        self.assertEqual(formatta_nome("NATALE DEL SIGNORE"), "Natale del Signore")
        self.assertEqual(formatta_nome("XXXII DOMENICA DEL TEMPO ORDINARIO - ANNO A"), "XXXII Domenica del Tempo Ordinario - Anno A")
        self.assertEqual(formatta_nome("DEDICAZIONE DELLA BASILICA LATERANENSE – FESTA"), "Dedicazione della Basilica Lateranense – Festa")
        self.assertEqual(formatta_nome("SABATO DELLA XXXI SETTIMANA DEL TEMPO ORDINARIO (ANNO PARI)"),
                         "Sabato della XXXI Settimana del Tempo Ordinario (Anno Pari)")
        self.assertEqual(formatta_nome("SOLENNITÀ DEI SANTI PIETRO E PAOLO"), "Solennità dei Santi Pietro e Paolo")
        self.assertEqual(formatta_nome("MESSA DELL’AURORA"), "Messa dell’Aurora")
        self.assertEqual(formatta_nome("I DOMENICA DI AVVENTO - ANNO B"), "I Domenica di Avvento - Anno B")

    def test_il_nome_puo_essere_corretto_a_mano(self):
        from messa.server import Servizio
        sv = Servizio(html_prova=str(QUI / "pagina_cei_natale.html"))
        sv.carica_liturgia("2026-12-25")
        piani = []
        with mock.patch("messa.server.prepara_piano", side_effect=lambda *a, **k: (piani.append(a[3]) or ([], []))), \
             mock.patch("messa.server.genera", return_value=(1, Path("/tmp/x.pptx"))), \
             mock.patch("messa.server.cfgmod.salva"):
            sv.genera({"data": "2026-12-25", "sezioni": ["frontespizio"], "nome_celebrazione": "Natale del Signore – Messa di mezzanotte"})
            sv.genera({"data": "2026-12-25", "sezioni": ["frontespizio"], "nome_celebrazione": "  "})
        self.assertEqual(piani[0].nome, "Natale del Signore – Messa di mezzanotte")
        self.assertEqual(piani[1].nome, "NATALE DEL SIGNORE")                # campo vuoto: resta il nome letto


class TestAlternativeNelleLetture(unittest.TestCase):
    def setUp(self):
        self.l = lit.analizza_html(HTML9, DATA9)
        self.cfg = config.carica()

    def test_prima_lettura_con_oppure(self):
        seg = imp.separa_lettura(self.l.sezioni["prima lettura"])
        self.assertEqual([s["etichetta"] for s in seg], [None, "Oppure"])
        self.assertEqual(seg[0]["annuncio"], ["Dal libro del profeta Ezechièle", "Ez 47,1-2.8-9.12"])
        self.assertEqual(seg[1]["annuncio"][-1], "1Cor 3,9c-11.16-17")
        tutti = [r for s in seg for r in s["corpo"]]
        self.assertNotIn("Oppure:", tutti)
        self.assertFalse(any("Voi siete il tempio di Dio." == r for r in tutti))   # il riassunto non si legge

    def test_alternative_nel_file(self):
        piano, _ = prepara_piano(DATA9, {"prima_lettura", "colletta"}, {}, self.l, None, None, self.cfg)
        d = tempfile.mkdtemp()
        genera(piano, self.cfg, self.l.colore_hex, Path(d), "t.pptx")
        p = Presentation(str(Path(d) / "t.pptx"))
        intest = [_testo(sl)[0].split("\n")[0] for sl in p.slides]
        self.assertIn("PRIMA LETTURA · OPPURE", intest)
        self.assertIn("COLLETTA · OPPURE", intest)
        annunci = [" ".join(_testo(sl)) for sl in p.slides if len(_testo(sl)) == 1 and _testo(sl)[0].startswith("PRIMA LETTURA")]
        self.assertTrue(any("Ez 47,1-2.8-9.12" in a for a in annunci))
        self.assertTrue(any("1Cor 3,9c-11.16-17" in a for a in annunci))

    def test_colore_bianco(self):
        self.assertEqual(self.l.colore_nome, "bianco")


class TestWindows(unittest.TestCase):
    """Le parti che dipendono dal sistema, simulate (i test girano anche su Mac/Linux)."""

    def setUp(self):
        from messa import dialoghi
        self.d = dialoghi

    def _win(self, stdout=b"", codice=0):
        return mock.patch.object(self.d.sys, "platform", "win32"), \
               mock.patch.object(self.d.subprocess, "run", return_value=mock.Mock(stdout=stdout, returncode=codice))

    def test_scelta_pdf_con_powershell(self):
        piattaforma, run = self._win("C:\\Archivio Canti\\Così è.pdf".encode("utf-8"))
        with piattaforma, run as r:
            risultato = self.d.scegli_pdf()
        self.assertEqual(risultato, "C:\\Archivio Canti\\Così è.pdf")           # accenti e spazi conservati
        comando = r.call_args[0][0]
        self.assertEqual(comando[0], "powershell")
        self.assertIn("-STA", comando)                                           # necessario per le finestre
        self.assertIn("OpenFileDialog", comando[-1])
        self.assertEqual(r.call_args[1]["creationflags"], self.d.CREATE_NO_WINDOW)   # niente finestra nera

    def test_scelta_cartella_con_powershell(self):
        piattaforma, run = self._win(b"C:\\Users\\Anna\\Documents\\Messe\r\n")
        with piattaforma, run as r:
            self.assertEqual(self.d.scegli_cartella(), "C:\\Users\\Anna\\Documents\\Messe")
        self.assertIn("FolderBrowserDialog", r.call_args[0][0][-1])

    def test_scelta_annullata(self):
        piattaforma, run = self._win(b"")
        with piattaforma, run:
            self.assertIsNone(self.d.scegli_pdf())

    def test_powershell_assente_ripiega_su_tk(self):
        piattaforma = mock.patch.object(self.d.sys, "platform", "win32")
        with piattaforma, mock.patch.object(self.d.subprocess, "run", side_effect=FileNotFoundError), \
             mock.patch.object(self.d, "_tk", return_value="C:\\x.pdf") as tk:
            self.assertEqual(self.d.scegli_pdf(), "C:\\x.pdf")
        tk.assert_called_once_with("file")

    def test_apici_nel_messaggio_non_rompono_lo_script(self):
        piattaforma, run = self._win(b"")
        with piattaforma, run as r:
            self.d.scegli_pdf("Scegli l'archivio")
        self.assertNotIn("l'archivio", r.call_args[0][0][-1])                    # gli apici singoli sono tolti

    def test_esplora_file(self):
        piattaforma, run = self._win()
        with piattaforma, run as r:
            self.d.mostra_nel_finder("C:\\Messe\\Messa_2026-11-08.pptx")
        self.assertEqual(r.call_args[0][0], ["explorer", "/select,C:\\Messe\\Messa_2026-11-08.pptx"])

    def test_nome_del_gestore_file(self):
        for piattaforma, atteso in (("win32", "Esplora file"), ("darwin", "Finder")):
            with mock.patch.object(self.d.sys, "platform", piattaforma):
                self.assertEqual(self.d.gestore_file(), atteso)

    def test_pythonw_usa_python_con_console(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "pythonw.exe").write_text("")
            (Path(d) / "python.exe").write_text("")
            with mock.patch.object(self.d.sys, "executable", str(Path(d) / "pythonw.exe")):
                self.assertTrue(self.d._python_con_console().endswith("python.exe"))

    def test_file_aperto_in_powerpoint(self):
        from messa import pptx_builder
        with mock.patch.object(pptx_builder.Costruttore, "salva", side_effect=PermissionError):
            with self.assertRaises(ErroreMessa) as c:
                pptx_builder.costruisci([{"tipo": "vuota"}], "Aptos", "3FA34D", Path("/tmp/x.pptx"))
        self.assertEqual(c.exception.codice, "E08")
        self.assertIn("PowerPoint", c.exception.dettaglio)

    def test_file_per_windows_presenti_e_ben_formati(self):
        radice = QUI.parent
        if not (radice / "Installa.bat").exists():
            self.skipTest("pacchetto Mac: i file per Windows non ci sono")
        for nome in ("Installa.bat", "crea_collegamento.ps1", "Messa Parrocchia.vbs"):
            dati = (radice / nome).read_bytes()
            self.assertIn(b"\r\n", dati, nome)                                   # fine riga di Windows
            self.assertNotIn(b"\n", dati.replace(b"\r\n", b""), nome)           # nessun a capo "a meta'"
        for nome in ("crea_collegamento.ps1", "Messa Parrocchia.vbs"):
            (radice / nome).read_bytes().decode("ascii")                         # PowerShell 5 / VBS: solo ASCII
        self.assertTrue((radice / "messa.ico").exists())
        bat = (radice / "Installa.bat").read_text(encoding="utf-8")
        self.assertIn(".venv\\Scripts\\python.exe", bat)
        self.assertIn("requirements.txt", bat)


class TestFrontespizioRipetuto(unittest.TestCase):
    """Il frontespizio ripetuto dopo sei punti della Messa."""

    PUNTI = ["Canto iniziale", "Vangelo", "Preghiera sulle offerte", "Santo", "Agnello di Dio", "Canto di comunione"]

    def setUp(self):
        self.cfg = config.carica()
        self.lit = lit.analizza_html(HTML8, DATA8)
        self.tutti = {s["id"] for s in SEZIONI}
        self.canti = {slot: 1 for slot in ("iniziale", "gloria", "alleluia", "offertorio", "santo", "pace",
                                           "agnello", "comunione", "finale")}

    def _piano(self, scelte=None, extra=None):
        return prepara_piano(DATA8, scelte if scelte is not None else self.tutti, self.canti, self.lit,
                             _ArchivioFinto(), None, self.cfg, None, extra)[0]

    def _prima_di_ogni_frontespizio(self, piano):
        out = []
        for i, v in enumerate(piano):
            if v["tipo"] == "frontespizio" and i > 0:
                out.append(piano[i - 1].get("titolo"))
        return out

    def test_sei_sezioni_in_piu_con_i_nomi_giusti(self):
        ripetute = [x for x in SEZIONI if x["id"].startswith("frontespizio_dopo_")]
        self.assertEqual(len(ripetute), 6)
        self.assertEqual(len(SEZIONI), 27)
        self.assertEqual(len({x["id"] for x in SEZIONI}), 27)                 # identificativi tutti diversi
        self.assertTrue(all(x["fonte"] == "sistema" for x in ripetute))

    def test_posizioni(self):
        self.assertEqual(self._prima_di_ogni_frontespizio(self._piano()), self.PUNTI)

    def test_slide_identiche_al_frontespizio_iniziale(self):
        piano = self._piano()
        fronti = [v for v in piano if v["tipo"] == "frontespizio"]
        self.assertEqual(len(fronti), 7)                                       # 1 iniziale + 6 ripetuti
        self.assertTrue(all(f == fronti[0] for f in fronti))

    def test_ognuna_si_puo_togliere(self):
        for sez in SEZIONI:
            if sez["id"].startswith("frontespizio_dopo_"):
                piano = self._piano(self.tutti - {sez["id"]})
                self.assertEqual(sum(v["tipo"] == "frontespizio" for v in piano), 6, sez["id"])

    def test_ordine_fisso_qualunque_sia_la_selezione(self):
        solo = {"frontespizio_dopo_vangelo", "vangelo", "canto_iniziale", "frontespizio_dopo_canto_iniziale"}
        piano = self._piano(solo)
        self.assertEqual([v.get("titolo", v["tipo"]) for v in piano],
                         ["Canto iniziale", "frontespizio", "Vangelo", "frontespizio"])

    def test_canti_aggiuntivi_dopo_il_frontespizio_ripetuto(self):
        extra = [{"id": 9, "dopo": "frontespizio_dopo_vangelo", "etichetta": "Dopo il Vangelo"}]
        piano = self._piano({"vangelo", "frontespizio_dopo_vangelo", "professione_fede"}, extra)
        self.assertEqual([v.get("titolo", v["tipo"]) for v in piano][:3], ["Vangelo", "frontespizio", "Dopo il Vangelo"])

    def test_nel_file_pptx(self):
        piano = self._piano({"canto_iniziale", "frontespizio_dopo_canto_iniziale", "colletta"})
        d = tempfile.mkdtemp()
        genera(piano, self.cfg, self.lit.colore_hex, Path(d), "t.pptx")
        p = Presentation(str(Path(d) / "t.pptx"))
        testi = [" ".join(_testo(sl)) for sl in p.slides]
        fronte = [t for t in testi if "PARROCCHIA DI TERRANEGRA" in t]
        self.assertEqual(len(fronte), 1)
        self.assertIn("Domenica 8 novembre 2026", fronte[0])
        self.assertTrue(testi[0].startswith("CANTO INIZIALE"))
        self.assertIn("PARROCCHIA DI TERRANEGRA", testi[testi.index(fronte[0])])


class _EventoFinto:
    """Imita l'evento 'shown' di pywebview: si aggiungono funzioni con +=, e scattano all'avvio."""
    def __init__(self):
        self.funzioni = []

    def __iadd__(self, f):
        self.funzioni.append(f)
        return self


def _webview_finto(mostra=True, errore=None, senza_eventi=False):
    modulo = mock.Mock()
    finestra = mock.Mock()
    finestra.events.shown = _EventoFinto()
    if senza_eventi:
        finestra.events = mock.Mock(spec=[])               # nessun attributo "shown"
    modulo.create_window.return_value = finestra

    def avvia(**kwargs):
        if errore:
            raise errore
        if mostra and not senza_eventi:
            for f in finestra.events.shown.funzioni:
                f()
    modulo.start.side_effect = avvia
    return modulo, finestra


class TestFinestraPropria(unittest.TestCase):
    """Apertura in finestra propria, con riserva su Edge/Chrome e poi sul browser."""

    def setUp(self):
        from messa import finestra
        self.f = finestra
        self.servizio = mock.Mock(modalita="browser")

    def test_finestra_nativa(self):
        modulo, finestra = _webview_finto()
        with mock.patch.dict(sys.modules, {"webview": modulo}), mock.patch.object(self.f.webbrowser, "open") as browser:
            esito = self.f.apri("http://127.0.0.1:1/", self.servizio)
        self.assertEqual(esito, "finestra")
        self.assertEqual(self.servizio.modalita, "finestra")
        browser.assert_not_called()                                       # nessuna scheda del browser
        args, kw = modulo.create_window.call_args
        self.assertEqual(args[0], "Messa Parrocchia")
        self.assertEqual(args[1], "http://127.0.0.1:1/")
        self.assertTrue(kw["text_select"])

    def test_su_windows_motore_edge(self):
        modulo, _ = _webview_finto()
        with mock.patch.dict(sys.modules, {"webview": modulo}), mock.patch.object(self.f.sys, "platform", "win32"):
            self.assertTrue(self.f.con_webview("http://x/"))
        self.assertEqual(modulo.start.call_args[1]["gui"], "edgechromium")    # mai il vecchio motore di Internet Explorer

    def test_pywebview_non_installato_ripiega_su_chromium(self):
        with mock.patch.dict(sys.modules, {"webview": None}), \
             mock.patch.object(self.f, "trova_chromium", return_value="/usr/bin/edge"), \
             mock.patch.object(self.f, "con_chromium", return_value=True) as app, \
             mock.patch.object(self.f.webbrowser, "open") as browser:
            self.assertEqual(self.f.apri("http://x/", self.servizio), "app")
        app.assert_called_once()
        browser.assert_not_called()

    def test_errore_di_pywebview_ripiega(self):
        modulo, _ = _webview_finto(errore=RuntimeError("WebView2 mancante"))
        with mock.patch.dict(sys.modules, {"webview": modulo}), \
             mock.patch.object(self.f, "con_chromium", return_value=False), \
             mock.patch.object(self.f.webbrowser, "open") as browser:
            self.assertEqual(self.f.apri("http://x/", self.servizio), "browser")
        browser.assert_called_once_with("http://x/")
        self.assertEqual(self.servizio.modalita, "browser")                   # l'interfaccia lo sa

    def test_finestra_mai_mostrata_ripiega(self):
        modulo, _ = _webview_finto(mostra=False)
        with mock.patch.dict(sys.modules, {"webview": modulo}), \
             mock.patch.object(self.f, "con_chromium", return_value=False), \
             mock.patch.object(self.f.webbrowser, "open"):
            self.assertEqual(self.f.apri("http://x/", self.servizio), "browser")

    def test_versione_senza_evento_shown_non_apre_due_finestre(self):
        modulo, _ = _webview_finto(senza_eventi=True)
        with mock.patch.dict(sys.modules, {"webview": modulo}):
            self.assertTrue(self.f.con_webview("http://x/"))                  # considerata riuscita

    def test_modalita_solo_browser(self):
        with mock.patch.object(self.f, "con_webview") as w, mock.patch.object(self.f, "con_chromium") as c, \
             mock.patch.object(self.f.webbrowser, "open") as browser:
            self.assertEqual(self.f.apri("http://x/", self.servizio, "browser"), "browser")
        w.assert_not_called()
        c.assert_not_called()
        browser.assert_called_once()

    # --- finestra "senza barra" di Edge/Chrome ---
    def test_comando_chromium(self):
        with tempfile.TemporaryDirectory() as d:
            processo = mock.Mock()
            with mock.patch.object(self.f, "trova_chromium", return_value="/x/msedge"), \
                 mock.patch.object(self.f, "BASE", Path(d)), \
                 mock.patch.object(self.f.subprocess, "Popen", return_value=processo) as popen, \
                 mock.patch.object(self.f.time, "monotonic", side_effect=[0, 60]):          # finestra rimasta aperta 60 s
                self.assertTrue(self.f.con_chromium("http://127.0.0.1:5/"))
            comando = popen.call_args[0][0]
            self.assertEqual(comando[0], "/x/msedge")
            self.assertIn("--app=http://127.0.0.1:5/", comando)
            self.assertTrue(any(c.startswith("--user-data-dir=") and "profilo_finestra" in c for c in comando))
            processo.wait.assert_called_once()                                  # il programma aspetta la chiusura

    def test_chromium_che_si_chiude_subito_non_vale(self):
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(self.f, "trova_chromium", return_value="/x/chrome"), \
             mock.patch.object(self.f, "BASE", Path(d)), \
             mock.patch.object(self.f.subprocess, "Popen", return_value=mock.Mock()), \
             mock.patch.object(self.f.time, "monotonic", side_effect=[0, 0.4]):         # affidato a un'istanza gia' aperta
            self.assertFalse(self.f.con_chromium("http://x/"))

    def test_nessun_chromium(self):
        with mock.patch.object(self.f, "trova_chromium", return_value=None):
            self.assertFalse(self.f.con_chromium("http://x/"))

    def test_ricerca_del_browser_su_windows(self):
        with tempfile.TemporaryDirectory() as d:
            edge = Path(d) / r"Microsoft\Edge\Application\msedge.exe"        # stesso modo con cui lo cerca il programma
            edge.parent.mkdir(parents=True, exist_ok=True)
            edge.write_text("")
            ambiente = {"ProgramFiles(x86)": d, "ProgramFiles": "", "LOCALAPPDATA": ""}
            with mock.patch.object(self.f.sys, "platform", "win32"), \
                 mock.patch.dict(self.f.os.environ, ambiente, clear=False), \
                 mock.patch.object(self.f.shutil, "which", return_value=None):
                self.assertEqual(Path(self.f.trova_chromium()), edge)

    def test_stato_dice_se_e_una_finestra(self):
        from messa.server import Servizio
        sv = Servizio(html_prova=str(QUI / "pagina_cei_esempio.html"))
        self.assertFalse(sv.stato()["finestra"])
        sv.modalita = "finestra"
        self.assertTrue(sv.stato()["finestra"])

    def test_file_di_installazione_e_icone(self):
        radice = QUI.parent
        self.assertIn("pywebview", (radice / "requirements-finestra.txt").read_text(encoding="utf-8"))
        self.assertNotIn("pywebview", (radice / "requirements.txt").read_text(encoding="utf-8"))   # facoltativo
        for nome in ("messa.png", "messa.ico", "messa.icns"):
            self.assertTrue((radice / nome).stat().st_size > 1000, nome)
        if (radice / "Installa.bat").exists():
            bat = (radice / "Installa.bat").read_bytes().decode("utf-8")
            self.assertIn("requirements-finestra.txt", bat)
            self.assertIn("\r\n", bat)
        if (radice / "Installa.command").exists():
            cmd = (radice / "Installa.command").read_text(encoding="utf-8")
            self.assertIn("requirements-finestra.txt", cmd)
            self.assertIn("if ! .venv/bin/python -m pip install -r requirements-finestra.txt", cmd)   # non bloccante


class TestAvvioMac(unittest.TestCase):
    """Il file di avvio dell'app Mac: diario, avvisi chiari, nessun lancio 'orfano' in secondo piano."""

    def setUp(self):
        self.avvia = QUI.parent / "Messa Parrocchia.app" / "Contents" / "MacOS" / "avvia"
        if not self.avvia.exists():
            self.skipTest("pacchetto Windows: l'app Mac non c'e'")
        if sys.platform.startswith("win") or not shutil_which("bash"):
            self.skipTest("serve bash")

    def _prova(self, python_finto, comandi=None):
        """Esegue davvero 'avvia' in una cartella finta; restituisce (codice, diario).
        comandi: {nome: script} di comandi finti (es. sysctl, arch) messi in testa al PATH."""
        import os
        import subprocess
        d = Path(tempfile.mkdtemp())
        app = d / "programma" / "Messa Parrocchia.app" / "Contents" / "MacOS"
        app.mkdir(parents=True)
        shutil_copy(self.avvia, app / "avvia")
        os.chmod(app / "avvia", 0o755)
        (d / "programma" / "app.py").write_text("# finto")
        if python_finto is not None:
            py = d / "programma" / ".venv" / "bin" / "python"
            py.parent.mkdir(parents=True)
            py.write_text(python_finto)
            os.chmod(py, 0o755)
        casa = d / "casa"
        casa.mkdir()
        percorso = "/usr/bin:/bin"
        if comandi:
            cartella_comandi = d / "bin"
            cartella_comandi.mkdir()
            for nome, testo in comandi.items():
                (cartella_comandi / nome).write_text(testo)
                os.chmod(cartella_comandi / nome, 0o755)
            percorso = f"{cartella_comandi}:{percorso}"
        self.diario_arch = d / "arch.log"
        # ambiente minimo, come quando macOS apre un'icona (niente osascript: gli avvisi vengono solo ignorati)
        r = subprocess.run([str(app / "avvia")], cwd="/", capture_output=True, timeout=60,
                           env={"HOME": str(casa), "PATH": percorso, "FAKE_ARCH_LOG": str(self.diario_arch)})
        log = casa / "Library" / "Logs" / "Messa Parrocchia" / "avvio.log"
        return r.returncode, log.read_text(encoding="utf-8") if log.exists() else ""

    def test_avvio_riuscito(self):
        codice, log = self._prova("#!/bin/bash\n[ \"$1\" = \"-c\" ] && exit 0\necho 'programma in funzione'\nsleep 1\nexit 0\n")
        self.assertEqual(codice, 0)
        self.assertIn("avvio dall'icona", log)
        self.assertIn("programma in funzione", log)                    # l'output del programma finisce nel diario
        self.assertIn("il programma è terminato: codice 0", log)

    def test_il_lanciatore_aspetta_il_programma(self):
        import time
        inizio = time.time()
        self._prova("#!/bin/bash\n[ \"$1\" = \"-c\" ] && exit 0\nsleep 2\nexit 0\n")
        self.assertGreaterEqual(time.time() - inizio, 2)               # resta in vita quanto il programma

    def test_installazione_mancante(self):
        codice, log = self._prova(None)
        self.assertEqual(codice, 1)
        self.assertIn("ERRORE: non trovo", log)
        self.assertIn(".venv/bin/python", log)

    def test_programma_che_si_chiude_subito(self):
        codice, log = self._prova("#!/bin/bash\n[ \"$1\" = \"-c\" ] && exit 0\necho 'Traceback: errore finto' >&2\nexit 3\n")
        self.assertEqual(codice, 3)
        self.assertIn("Traceback: errore finto", log)                  # il motivo e' nel diario
        self.assertIn("codice 3", log)

    def test_python_che_non_parte(self):
        codice, log = self._prova("#!/bin/bash\nexit 5\n")
        self.assertEqual(codice, 1)
        self.assertIn("ERRORE: Python non parte", log)

    # --- Mac con chip Apple: il programma deve partire in modo nativo (arm64), non in modalita' Intel ---
    PY_OK = "#!/bin/bash\n[ \"$1\" = \"-c\" ] && exit 0\necho 'programma in funzione'\nexit 0\n"
    ARCH_FINTO = "#!/bin/bash\necho \"arch $*\" >> \"$FAKE_ARCH_LOG\"\n[ \"$1\" = \"-arm64\" ] && shift\nexec \"$@\"\n"

    def test_mac_apple_silicon_avvio_nativo(self):
        codice, log = self._prova(self.PY_OK, {"sysctl": "#!/bin/bash\necho 1\n", "arch": self.ARCH_FINTO})
        self.assertEqual(codice, 0)
        self.assertIn("modalità del programma: arch -arm64", log)
        chiamate = self.diario_arch.read_text().splitlines()
        self.assertTrue(all(c.startswith("arch -arm64") for c in chiamate))          # sempre in modo nativo
        self.assertGreaterEqual(len(chiamate), 2)                                    # prova + avvio vero
        self.assertIn("programma in funzione", log)

    def test_mac_intel_nessuna_forzatura(self):
        codice, log = self._prova(self.PY_OK, {"sysctl": "#!/bin/bash\nexit 1\n", "arch": self.ARCH_FINTO})
        self.assertEqual(codice, 0)
        self.assertIn("modalità del programma: predefinita", log)
        self.assertFalse(self.diario_arch.exists())                                  # arch non e' stato usato

    def test_apple_silicon_ma_python_solo_intel_ripiega(self):
        arch_che_rifiuta = "#!/bin/bash\necho \"arch $*\" >> \"$FAKE_ARCH_LOG\"\n[ \"$1\" = \"-arm64\" ] && exit 1\nexec \"$@\"\n"
        codice, log = self._prova(self.PY_OK, {"sysctl": "#!/bin/bash\necho 1\n", "arch": arch_che_rifiuta})
        self.assertEqual(codice, 0)                                                  # il programma parte lo stesso
        self.assertIn("modalità del programma: predefinita", log)

    def test_errore_di_architettura_viene_spiegato(self):
        python = ("#!/bin/bash\n[ \"$1\" = \"-c\" ] && exit 0\n"
                  "echo \"ImportError: dlopen(x.so): mach-o file, but is an incompatible architecture "
                  "(have 'arm64', need 'x86_64')\" >&2\nexit 1\n")
        codice, log = self._prova(python)
        self.assertEqual(codice, 1)
        self.assertIn("CAUSA: componenti installati per un tipo di Mac diverso", log)

    def test_scheda_dell_app_chiede_arm64(self):
        import plistlib
        info = plistlib.loads((self.avvia.parents[1] / "Info.plist").read_bytes())
        self.assertEqual(info["LSArchitecturePriority"], ["arm64", "x86_64"])

    def test_il_programma_scrive_architettura_e_python_nel_diario(self):
        testo = (QUI.parent / "app.py").read_text(encoding="utf-8")
        self.assertIn("platform.machine()", testo)
        self.assertIn("platform.python_version()", testo)

    def test_forma_del_file(self):
        import os
        import plistlib
        testo = self.avvia.read_text(encoding="utf-8")
        righe = [r.strip() for r in testo.splitlines() if r.strip() and not r.strip().startswith("#")]
        self.assertFalse(any(r.startswith("nohup") or r.endswith(" &") for r in righe))    # niente lancio in secondo piano
        self.assertIn("Library/Logs/Messa Parrocchia", testo)           # diario in una cartella sempre accessibile
        self.assertIn("Applicazioni", testo)                            # suggerisce dove spostare la cartella
        self.assertTrue(os.access(self.avvia, os.X_OK))
        info = plistlib.loads((self.avvia.parents[1] / "Info.plist").read_bytes())
        self.assertEqual(info["CFBundleExecutable"], "avvia")
        self.assertTrue((self.avvia.parents[1] / "Resources" / "messa.icns").exists())

    def test_avvio_di_emergenza(self):
        import os
        emergenza = QUI.parent / "Avvia con Terminale.command"
        self.assertTrue(emergenza.exists())
        self.assertTrue(os.access(emergenza, os.X_OK))
        self.assertIn(".venv/bin/python app.py", emergenza.read_text(encoding="utf-8"))
        self.assertIn("Avvia con Terminale.command", (QUI.parent / "Installa.command").read_text(encoding="utf-8"))

    def test_diario_del_programma_ha_una_riserva(self):
        from messa import server
        with tempfile.TemporaryDirectory() as casa:
            with mock.patch.object(server, "LOG", Path("/proc/non/scrivibile/log.txt")), \
                 mock.patch.object(server.Path, "home", return_value=Path(casa)):
                server.log("prova")
            scritto = Path(casa) / "Library" / "Logs" / "Messa Parrocchia" / "programma.log"
            self.assertIn("prova", scritto.read_text(encoding="utf-8"))


def shutil_which(nome):
    import shutil
    return shutil.which(nome)


def shutil_copy(origine, destinazione):
    import shutil
    shutil.copy(origine, destinazione)


class TestVersioni(unittest.TestCase):
    """Numero di versione, registro delle modifiche e cosa finirebbe su GitHub."""

    RADICE = QUI.parent

    def test_versione_a_tre_cifre(self):
        import re as _re
        from messa import __version__
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")

    def test_changelog_allineato_alla_versione(self):
        import re as _re
        from messa import __version__
        testo = (self.RADICE / "CHANGELOG.md").read_text(encoding="utf-8")
        prima = _re.search(r"^## (\d+\.\d+\.\d+)", testo, _re.M).group(1)
        self.assertEqual(prima, __version__)

    def test_la_pagina_mostra_la_versione(self):
        from messa import __version__
        from messa.server import Servizio
        sv = Servizio(html_prova=str(QUI / "pagina_cei_esempio.html"))
        self.assertEqual(sv.stato()["versione"], __version__)
        self.assertIn('id="versione"', (self.RADICE / "web" / "index.html").read_text(encoding="utf-8"))

    def test_cosa_finirebbe_su_github(self):
        """Simula 'git add' su una copia: i dati personali e l'ambiente NON devono essere inclusi."""
        import shutil
        import subprocess
        if not shutil.which("git"):
            self.skipTest("git non installato")
        if not (self.RADICE / "strumenti").exists():
            self.skipTest("pacchetto di installazione: questa verifica vale per il repository")
        d = Path(tempfile.mkdtemp()) / "copia"
        shutil.copytree(self.RADICE, d, ignore=shutil.ignore_patterns(".git"))
        # file che sul computer di chi usa il programma esistono davvero:
        (d / "config.json").write_text("{}")
        (d / "log.txt").write_text("x")
        (d / "archivi").mkdir(exist_ok=True)
        (d / "archivi" / "canti.pdf").write_bytes(b"%PDF-finto")
        (d / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
        (d / ".venv" / "bin" / "python").write_text("x")
        (d / "cache").mkdir(exist_ok=True)
        (d / "cache" / "canti_x.json").write_text("{}")
        (d / "Messa_2026-11-08.pptx").write_bytes(b"PK")
        subprocess.run(["git", "init", "-q"], cwd=d, check=True)
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        file = subprocess.run(["git", "ls-files"], cwd=d, capture_output=True, text=True, check=True).stdout.splitlines()
        for vietato in ("config.json", "log.txt", "archivi/canti.pdf", ".venv/bin/python", "cache/canti_x.json",
                        "Messa_2026-11-08.pptx"):
            self.assertNotIn(vietato, file, vietato)
        for dovuto in ("app.py", "README.md", "LEGGIMI.md", "CHANGELOG.md", ".gitignore", "requirements.txt",
                       "archivi/LEGGIMI.txt", "messa/__init__.py", "testi/gloria.txt", "web/index.html"):
            self.assertIn(dovuto, file, dovuto)
        self.assertFalse([f for f in file if "__pycache__" in f or f.endswith(".pyc")])


class TestTestata(unittest.TestCase):
    """Logo e foto della chiesa in cima alla pagina."""

    RADICE = QUI.parent

    def setUp(self):
        import threading
        from messa.server import Servizio, avvia
        self.sv = Servizio(html_prova=str(QUI / "pagina_cei_esempio.html"))
        self.srv = avvia(self.sv, 0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.porta = self.srv.server_address[1]
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def _get(self, percorso):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=5)
        c.request("GET", percorso, headers={"Host": f"127.0.0.1:{self.porta}"})
        r = c.getresponse()
        corpo = r.read()
        c.close()
        return r.status, r.getheader("Content-Type"), r.getheader("Cache-Control"), corpo

    def test_immagini_presenti_leggere_e_nel_formato_giusto(self):
        from PIL import Image
        for nome, larghezza_min in (("logo-parrocchia.jpg", 250), ("chiesa.jpg", 250)):
            f = self.RADICE / "web" / "img" / nome
            self.assertTrue(f.exists(), nome)
            self.assertLess(f.stat().st_size, 120 * 1024, nome)                  # la pagina resta leggera
            with Image.open(f) as im:
                self.assertGreaterEqual(im.size[0], larghezza_min, nome)         # nitida anche su schermi Retina

    def test_la_pagina_mostra_le_due_immagini_accanto_al_titolo(self):
        html = (self.RADICE / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('src="/img/logo-parrocchia.jpg"', html)
        self.assertIn('src="/img/chiesa.jpg"', html)
        self.assertIn('alt="', html.split('class="logo"')[1][:120])               # testo alternativo per chi non vede le immagini
        self.assertLess(html.index("/img/logo-parrocchia.jpg"), html.index("Presentazione della Messa"))
        self.assertLess(html.index("Presentazione della Messa"), html.index("/img/chiesa.jpg"))

    def test_il_server_serve_le_immagini(self):
        for nome in ("logo-parrocchia.jpg", "chiesa.jpg"):
            stato, tipo, cache, corpo = self._get(f"/img/{nome}")
            self.assertEqual((stato, tipo), (200, "image/jpeg"), nome)
            self.assertIn("max-age", cache)                                       # non si riscarica a ogni apertura
            self.assertEqual(corpo, (self.RADICE / "web" / "img" / nome).read_bytes())

    def test_solo_le_immagini_della_cartella_si_possono_leggere(self):
        for sbagliato in ("/img/../app.py", "/img/..%2fapp.py", "/img/%2e%2e/app.py", "/img/", "/img/non_esiste.jpg",
                          "/img/chiesa.jpg/../../app.py", "/img/../../etc/passwd", "/img/LEGGIMI.md"):
            self.assertEqual(self._get(sbagliato)[0], 404, sbagliato)

    def test_le_immagini_gia_presenti_non_vengono_sovrascritte_dagli_aggiornamenti(self):
        from messa import aggiornamenti as ag
        self.assertTrue(ag.protetto("web/img/chiesa.jpg", True))                  # la parrocchia puo' averla cambiata
        self.assertFalse(ag.protetto("web/img/nuova.jpg", False))                 # una immagine nuova invece si aggiunge
        self.assertFalse(ag.protetto("web/index.html", True))                     # la pagina si aggiorna


if __name__ == "__main__":
    unittest.main()
