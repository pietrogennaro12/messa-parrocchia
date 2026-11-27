# -*- coding: utf-8 -*-
"""Preghiere dei fedeli (ligature, titolo, risposta in giallo) e nuovo frontespizio."""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))

from messa import impaginazione as imp                    # noqa: E402
from messa.pptx_builder import costruisci, formatta_nome  # noqa: E402
from messa.preghiere import analizza_preghiere, e_intenzione, ripara_riga  # noqa: E402

PDF_REALE = Path("/mnt/user-data/uploads/domenica_22_novembre_2026.pdf")     # solo dove esiste (non fa parte del repository)
ORO = RGBColor.from_string("F2C94C")
TITOLO = "XXXIV Domenica del Tempo Ordinario\u00a0– Anno A"      # il trattino e' legato alla parola prima: se va a capo, "Anno A" va a capo da solo


def riga_finta(testo, simboli):
    """
    Riga di pdfplumber con le sole misure che servono. simboli: lista di (carattere, larghezza/corpo) nell'ordine
    in cui compaiono nella riga. Le misure sono quelle del PDF reale: 0,856 = "tti"; 0,557 = "ti"; 0,634 = "tt"; 0,268 = ":".
    """
    corpo = 22.0
    return {"text": testo, "chars": [{"text": c, "x0": 10.0, "x1": 10.0 + r * corpo, "size": corpo} for c, r in simboli]}


class TestLigature(unittest.TestCase):
    def test_tti_ti_tt_ricostruite(self):
        riga = riga_finta("Per tu: noi < preghiamo: perme@e se:mana", [(":", .856), ("<", .557), (":", .268), ("@", .634), (":", .856)])
        testo, n = ripara_riga(riga)
        self.assertEqual(testo, "Per tutti noi ti preghiamo: permette settimana")
        self.assertEqual(n, 4)                                  # il due punti vero (largo 0,268) resta com'e'

    def test_il_due_punti_vero_non_si_tocca(self):
        testo, n = ripara_riga(riga_finta("Ascoltaci, Signore: ti preghiamo:", [(":", .268), (":", .268)]))
        self.assertEqual((testo, n), ("Ascoltaci, Signore: ti preghiamo:", 0))

    def test_la_chiocciola_vera_non_si_tocca(self):
        testo, n = ripara_riga(riga_finta("scrivi a parrocchia@esempio.it", [("@", .939)]))
        self.assertEqual((testo, n), ("scrivi a parrocchia@esempio.it", 0))

    def test_ligature_unicode_diventano_lettere(self):
        testo, n = ripara_riga({"text": "momenti diﬃcili, ﬁglio e ﬂusso, oﬀerta", "chars": []})
        self.assertEqual(testo, "momenti difficili, figlio e flusso, offerta")

    def test_parole_con_piu_simboli(self):
        riga = riga_finta("tu: i fa<che con<nuare auten<ca", [(":", .856), ("<", .557), ("<", .557), ("<", .557)])
        self.assertEqual(ripara_riga(riga)[0], "tutti i fatiche continuare autentica")


class TestIntenzioni(unittest.TestCase):
    def test_intenzioni_normali(self):
        for t in ("Per la Chiesa, perché sappia riconoscere Cristo, noi ti preghiamo:",
                  "Per chi soffre, ti preghiamo.", "Per la pace nel mondo, preghiamo il Signore.",
                  "Per i giovani, noi ti preghiamo"):
            self.assertTrue(e_intenzione([t]), t)

    def test_preghiera_conclusiva_senza_risposta(self):
        for t in ("O Dio, Padre buono, accogli le nostre preghiere. Per Cristo nostro Signore.",
                  "Accogli, Padre, queste suppliche. Per Cristo, nostro Signore. Amen.", "Ti lodiamo, o Dio. Amen"):
            self.assertFalse(e_intenzione([t]), t)

    def test_invito_iniziale_senza_risposta(self):
        for t in ("Fratelli e sorelle, rivolgiamo la nostra preghiera a Dio e diciamo insieme:",
                  "Con fiducia, rispondiamo insieme.", "Preghiamo insieme"):
            self.assertFalse(e_intenzione([t]), t)

    def test_se_la_risposta_c_e_gia_non_si_ripete(self):
        self.assertFalse(e_intenzione(["... e diciamo insieme: Ascoltaci, o Signore."]))
        self.assertFalse(e_intenzione(["Preghiamo, ascoltaci o signore"], "Ascoltaci, o Signore"))

    def test_paragrafo_su_piu_righe(self):
        self.assertTrue(e_intenzione(["Per i malati, perché trovino conforto.", "Noi ti preghiamo:"]))
        self.assertFalse(e_intenzione([]))


class TestLetturaDelPdf(unittest.TestCase):
    def test_titolo_del_documento_scartato(self):
        blocchi, info = analizza_preghiere(QUI / "preghiere_esempio.pdf")
        self.assertIsNotNone(info["titolo_scartato"])
        self.assertIn("Preghiera dei fedeli", info["titolo_scartato"])
        self.assertFalse(any("Preghiera dei fedeli -" in " ".join(b) for b in blocchi))
        self.assertGreaterEqual(len(blocchi), 5)
        self.assertEqual(info["riparati"], 0)

    @unittest.skipUnless(PDF_REALE.exists(), "PDF reale non presente (non fa parte del repository)")
    def test_pdf_reale_con_ligature(self):
        blocchi, info = analizza_preghiere(PDF_REALE)
        testo = " ".join(r for b in blocchi for r in b)
        self.assertEqual(len(blocchi), 5)                                       # titolo scartato + 5 preghiere
        self.assertEqual(info["riparati"], 14)
        self.assertEqual(info["sospetti"], 0)
        for giusto in ("tutti i fratelli", "noi ti preghiamo:", "permette", "attesa viva", "settimana", "momenti difficili",
                       "fatiche", "continuare a camminare", "autentica", "difficoltà"):
            self.assertIn(giusto, testo)
        for sbagliato in ("<", "@", "tu: ", "se:mana"):
            self.assertNotIn(sbagliato, testo)
        self.assertEqual(sum(b[-1].rstrip().endswith("noi ti preghiamo:") for b in blocchi), 5)   # ogni preghiera e' un blocco


def visualizza(nome):
    import re
    return re.sub(r"\s+[-–]\s+", "\u00a0– ", formatta_nome(nome))


def crea(piano, colore="3FA34D"):
    d = tempfile.mkdtemp()
    percorso = Path(d) / "t.pptx"
    costruisci(piano, "Aptos", colore, percorso)
    return Presentation(str(percorso))


def runs(slide):
    return [(r.text, r) for sh in slide.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs for r in p.runs]


class TestSlidePreghiere(unittest.TestCase):
    BLOCCHI = [["Per la Chiesa, perché sia segno di unità, noi ti preghiamo:"],
               ["Per chi governa, perché cerchi il bene comune, noi ti preghiamo:"],
               ["Per i malati, perché trovino conforto, noi ti preghiamo:"]]

    def _deck(self, blocchi=None, risposta="Ascoltaci, o Signore"):
        return crea([{"tipo": "testo", "titolo": "Preghiere dei fedeli", "blocchi": blocchi or self.BLOCCHI,
                      "modo": "preghiere", "risposta": risposta}])

    def test_prima_slide_solo_il_titolo(self):
        p = self._deck()
        primo = [t for t, _ in runs(p.slides[0])]
        self.assertEqual(primo, ["PREGHIERE DEI FEDELI"])                       # il titolo e basta

    def test_una_preghiera_per_slide(self):
        p = self._deck()
        self.assertEqual(len(p.slides), 1 + len(self.BLOCCHI))
        for slide, b in zip(list(p.slides)[1:], self.BLOCCHI):
            testo = " ".join(t for t, _ in runs(slide))
            self.assertIn(b[0], testo)
            for altra in self.BLOCCHI:
                if altra is not b:
                    self.assertNotIn(altra[0], testo)

    def test_ascoltaci_in_giallo_e_grassetto_come_il_ritornello_del_salmo(self):
        for slide in list(self._deck().slides)[1:]:
            risposta = [r for t, r in runs(slide) if t == "Ascoltaci, o Signore"]
            self.assertEqual(len(risposta), 1)
            self.assertTrue(risposta[0].font.bold)
            self.assertEqual(risposta[0].font.color.rgb, ORO)
            preghiera = [r for t, r in runs(slide) if t.startswith("Per ")][0]
            self.assertNotEqual(preghiera.font.color.rgb, ORO)                   # la preghiera resta bianca
            self.assertFalse(preghiera.font.bold)

    def test_ascoltaci_sta_sotto_la_preghiera(self):
        for slide in list(self._deck().slides)[1:]:
            ordine = [t for t, _ in runs(slide)]
            self.assertEqual(ordine[-1], "Ascoltaci, o Signore")

    def test_il_marcatore_non_compare_nel_testo(self):
        for slide in self._deck().slides:
            for t, _ in runs(slide):
                self.assertNotIn(imp.MARCA_ORO, t)
                self.assertNotIn(imp.MARCA, t)

    def test_niente_risposta_su_invito_e_preghiera_conclusiva(self):
        blocchi = [["Fratelli, preghiamo il Padre e diciamo insieme:"]] + self.BLOCCHI + [
            ["O Dio, ascolta le nostre preghiere. Per Cristo nostro Signore. Amen."]]
        p = self._deck(blocchi)
        con = [any(t == "Ascoltaci, o Signore" for t, _ in runs(s)) for s in list(p.slides)[1:]]
        self.assertEqual(con, [False, True, True, True, False])

    def test_risposta_personalizzabile_o_assente(self):
        p = self._deck(risposta="Ti preghiamo, ascoltaci")
        self.assertTrue(any(t == "Ti preghiamo, ascoltaci" for t, _ in runs(p.slides[1])))
        senza = self._deck(risposta="")
        for slide in list(senza.slides)[1:]:
            gialli = [t for t, r in runs(slide) if r.font.color and r.font.color.type and r.font.color.rgb == ORO]
            self.assertEqual(gialli, ["PREGHIERE DEI FEDELI"])                   # solo il titolo in alto: nessuna risposta

    def test_preghiera_lunghissima_resta_leggibile_con_la_risposta(self):
        lunga = [["Per tutti coloro che, in ogni parte del mondo, soffrono a causa della guerra, della fame e dell'ingiustizia, "
                  "perché trovino accoglienza, giustizia e pace, e perché noi sappiamo essere strumenti del tuo amore, "
                  "noi ti preghiamo: " * 3]]
        p = self._deck(lunga)
        ultime = [t for t, _ in runs(list(p.slides)[-1])]
        self.assertEqual(ultime[-1], "Ascoltaci, o Signore")                      # la risposta segue il testo anche se si divide


class TestNuovoFrontespizio(unittest.TestCase):
    DATA = dt.date(2026, 11, 22)

    def _slide(self, nome="XXXIV DOMENICA DEL TEMPO ORDINARIO - ANNO A", colore="3FA34D", sottotitolo=None):
        piano = [{"tipo": "frontespizio", "data": self.DATA, "celebrazione": nome, "parrocchia": "Parrocchia di Terranegra",
                  "sottotitolo": sottotitolo}]
        return crea(piano, colore).slides[0]

    def test_la_ricorrenza_e_il_titolo_principale_nel_colore_liturgico_e_in_grassetto(self):
        for colore in ("3FA34D", "F5F5F5", "D64545", "9B6BC4", "E58FB0"):
            r = {t: x for t, x in runs(self._slide(colore=colore))}
            titolo = r[TITOLO]
            self.assertTrue(titolo.font.bold)
            self.assertEqual(titolo.font.color.rgb, RGBColor.from_string(colore), colore)

    def test_la_data_e_il_sottotitolo(self):
        r = dict(runs(self._slide()))
        data, titolo = r["Domenica 22 novembre 2026"], r[TITOLO]
        self.assertFalse(data.font.bold)
        self.assertLess(data.font.size, titolo.font.size)                         # piu' piccola del titolo
        self.assertEqual(data.font.color.rgb, RGBColor.from_string("FFFFFF"))      # bianca, non del colore liturgico

    def test_ordine_parrocchia_titolo_data(self):
        ordine = [t for t, _ in runs(self._slide())]
        self.assertEqual(ordine, ["PARROCCHIA DI TERRANEGRA", TITOLO,
                                  "Domenica 22 novembre 2026"])

    def test_nome_della_messa_dopo_la_data(self):
        ordine = [t for t, _ in runs(self._slide(sottotitolo="Messa della notte"))]
        self.assertEqual(ordine[-2:], ["Domenica 22 novembre 2026", "Messa della notte"])

    def test_il_trattino_non_resta_solo_all_inizio_della_riga_dopo(self):
        for nome in ("XXXII DOMENICA DEL TEMPO ORDINARIO - ANNO A", "DEDICAZIONE DELLA BASILICA LATERANENSE – FESTA"):
            titolo = visualizza(nome)
            self.assertIn("\u00a0– ", titolo)                                       # spazio non divisibile prima del trattino
            self.assertNotIn(" - ", titolo)
            self.assertNotIn(" – ", titolo)                                         # (con spazio normale)

    def test_nome_lungo_rimpicciolisce_per_stare_in_slide(self):
        lungo = "SOLENNITÀ DEL NOSTRO SIGNORE GESÙ CRISTO RE DELL'UNIVERSO - ANNO A"
        r = dict(runs(self._slide(nome=lungo)))
        breve = dict(runs(self._slide()))
        self.assertLess(r[visualizza(lungo)].font.size, breve[TITOLO].font.size)

    def test_senza_nome_la_data_fa_da_titolo(self):
        r = dict(runs(self._slide(nome="")))
        data = r["Domenica 22 novembre 2026"]
        self.assertTrue(data.font.bold)
        self.assertEqual(data.font.size.pt, 54)


if __name__ == "__main__":
    unittest.main()
