# -*- coding: utf-8 -*-
"""Test dell'aggiornamento da GitHub, con un 'finto GitHub' locale (nessun accesso a Internet)."""
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import requests

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))

from messa import aggiornamenti as ag                     # noqa: E402
from messa.errori import ErroreMessa                      # noqa: E402


# ----------------------------------------------------------------------------
# strumenti di prova
# ----------------------------------------------------------------------------

class GitHubFinto:
    """Server locale che imita le due chiamate usate: 'ultima release' e 'scarica il pacchetto'."""

    def __init__(self):
        self.release = None            # None -> 404
        self.stato = 200
        self.pacchetti = {}
        outer = self

        class Gestore(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.endswith("/releases/latest"):
                    if outer.stato != 200 or outer.release is None:
                        self.send_response(outer.stato if outer.stato != 200 else 404)
                        self.end_headers()
                        return
                    corpo = json.dumps(outer.release).encode()
                    self.send_response(200)
                elif self.path.startswith("/download/"):
                    corpo = outer.pacchetti.get(self.path.split("/")[-1])
                    if corpo is None:
                        self.send_response(404)
                        self.end_headers()
                        return
                    self.send_response(200)
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Gestore)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def chiudi(self):
        self.server.shutdown()
        self.server.server_close()

    def pubblica(self, versione, pacchetti, note="Novità di prova", digest=True, tag=None):
        assets = []
        for nome, dati in pacchetti.items():
            self.pacchetti[nome] = dati
            a = {"name": nome, "size": len(dati), "browser_download_url": f"{self.base}/download/{nome}"}
            if digest:
                a["digest"] = "sha256:" + hashlib.sha256(dati).hexdigest()
            assets.append(a)
        self.release = {"tag_name": tag or f"v{versione}", "body": note, "html_url": "https://github.com/x/y/releases/1",
                        "assets": assets}


def contenuto_pacchetto(versione):
    return {
        "app.py": "# app nuova\n",
        "messa/__init__.py": f'__version__ = "{versione}"\n',
        "messa/nuovo.py": "x = 1\n",
        "testi/gloria.txt": "GLORIA CAMBIATO DALLA NUOVA VERSIONE\n",
        "testi/novita.txt": "testo nuovo\n",
        "archivi/LEGGIMI.txt": "promemoria nuovo\n",
        "archivi/canti.pdf": "PDF-ARRIVATO-NEL-PACCHETTO",
        "config.json": '{"nel_pacchetto": true}',
        "Installa.command": "#!/bin/bash\necho ok\n",
        "requirements.txt": "requests\n",
    }


def crea_zip(versione, contenuto=None, radice="messa_parrocchia", con_manifest=True, extra_voci=()):
    contenuto = contenuto if contenuto is not None else contenuto_pacchetto(versione)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, testo in contenuto.items():
            info = zipfile.ZipInfo(f"{radice}/{rel}" if radice else rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = (0o755 if rel.endswith(".command") else 0o644) << 16
            z.writestr(info, testo)
        if con_manifest:
            manifest = {"versione": versione, "file": {rel: "x" for rel in contenuto}}
            z.writestr(f"{radice}/manifest.json", json.dumps(manifest))
        for info, dati in extra_voci:
            z.writestr(info, dati)
    return buf.getvalue()


def cartella_installata(versione="1.1.0"):
    """Un 'programma installato' con i dati della parrocchia."""
    d = Path(tempfile.mkdtemp()) / "programma"
    for rel, testo in {
        "app.py": "# app vecchia\n",
        "messa/__init__.py": f'__version__ = "{versione}"\n',
        "messa/vecchio.py": "# non serve piu'\n",
        "testi/gloria.txt": "GLORIA MODIFICATO DALLA PARROCCHIA\n",
        "archivi/canti.pdf": "PDF-DELLA-PARROCCHIA",
        "config.json": '{"parrocchia": "Mia parrocchia"}',
        "log.txt": "diario",
        ".venv/bin/python": "python",
        "cache/canti.json": "{}",
        "requirements.txt": "requests\n",
        "Installa.command": "#!/bin/bash\n",
    }.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(testo)
    manifest = {"versione": versione, "file": {"app.py": "x", "messa/__init__.py": "x", "messa/vecchio.py": "x",
                                               "testi/gloria.txt": "x", "Installa.command": "x"}}
    (d / "manifest.json").write_text(json.dumps(manifest))
    return d


def leggi(d, rel):
    return (Path(d) / rel).read_text()


# ----------------------------------------------------------------------------

class TestVersioni(unittest.TestCase):
    def test_lettura_e_confronto(self):
        self.assertEqual(ag.parse_versione("v1.2.0"), (1, 2, 0))
        self.assertEqual(ag.parse_versione(" 1.10.3 "), (1, 10, 3))
        for sbagliata in ("1.2", "x", "", None, "v1.2.0-beta", "1.2.0.1"):
            self.assertIsNone(ag.parse_versione(sbagliata), sbagliata)
        self.assertGreater(ag.parse_versione("1.10.0"), ag.parse_versione("1.9.9"))      # numeri, non testo

    def test_pacchetto_giusto_per_il_sistema(self):
        assets = [{"name": "Messa_Parrocchia_1.2.0_Mac.zip", "browser_download_url": "u1", "size": 1},
                  {"name": "Messa_Parrocchia_1.2.0_Windows.zip", "browser_download_url": "u2", "size": 2},
                  {"name": "Source code.tar.gz", "browser_download_url": "u3"}]
        for piattaforma, atteso in (("darwin", "u1"), ("win32", "u2")):
            with mock.patch.object(ag.sys, "platform", piattaforma):
                self.assertEqual(ag.scegli_asset(assets)["url"], atteso)
        with mock.patch.object(ag.sys, "platform", "linux"):
            self.assertIsNone(ag.scegli_asset(assets))


class TestControllo(unittest.TestCase):
    def setUp(self):
        self.gh = GitHubFinto()
        self.addCleanup(self.gh.chiudi)
        self.mac = mock.patch.object(ag.sys, "platform", "darwin")
        self.mac.start()
        self.addCleanup(self.mac.stop)

    def _controlla(self, repo="parrocchia/messa", corrente="1.1.0"):
        return ag.controlla(repo, corrente, self.gh.base)

    def test_versione_nuova_disponibile(self):
        self.gh.pubblica("1.2.0", {"Messa_Parrocchia_1.2.0_Mac.zip": b"x"}, note="Cosa c'è di nuovo")
        r = self._controlla()
        self.assertTrue(r["disponibile"])
        self.assertEqual((r["versione"], r["versione_corrente"], r["note"]), ("1.2.0", "1.1.0", "Cosa c'è di nuovo"))
        self.assertEqual(r["asset"]["nome"], "Messa_Parrocchia_1.2.0_Mac.zip")

    def test_gia_aggiornato(self):
        self.gh.pubblica("1.1.0", {"Messa_Parrocchia_1.1.0_Mac.zip": b"x"})
        self.assertFalse(self._controlla()["disponibile"])
        self.gh.pubblica("1.0.5", {"Messa_Parrocchia_1.0.5_Mac.zip": b"x"})              # release piu' vecchia
        self.assertFalse(self._controlla()["disponibile"])

    def test_repository_non_valido(self):
        for sbagliato in ("", "solo-nome", "a/b/c", "../etc/passwd", "x y/z", None):
            with self.assertRaises(ErroreMessa) as c:
                ag.controlla(sbagliato, "1.0.0", self.gh.base)
            self.assertEqual(c.exception.codice, "E10", sbagliato)

    def test_nessuna_release_o_repository_privato(self):
        with self.assertRaises(ErroreMessa) as c:
            self._controlla()
        self.assertEqual(c.exception.codice, "E10")
        self.assertIn("pubblico", c.exception.dettaglio)

    def test_limite_di_richieste_di_github(self):
        self.gh.stato = 403
        with self.assertRaises(ErroreMessa) as c:
            self._controlla()
        self.assertEqual(c.exception.codice, "E10")

    def test_tag_senza_formato_di_versione(self):
        self.gh.pubblica("x", {"Messa_Parrocchia_x_Mac.zip": b"x"}, tag="bozza")
        with self.assertRaises(ErroreMessa) as c:
            self._controlla()
        self.assertEqual(c.exception.codice, "E10")

    def test_manca_il_pacchetto_per_questo_computer(self):
        self.gh.pubblica("1.2.0", {"Messa_Parrocchia_1.2.0_Windows.zip": b"x"})
        with self.assertRaises(ErroreMessa) as c:
            self._controlla()
        self.assertIn("pacchetto", c.exception.dettaglio)

    def test_senza_internet(self):
        with mock.patch("requests.get", side_effect=requests.exceptions.ConnectionError("HTTPSConnectionPool(host=...)")):
            with self.assertRaises(ErroreMessa) as c:
                self._controlla()
        self.assertEqual(c.exception.codice, "E01")
        self.assertEqual(c.exception.dettaglio, "")                       # nessun dettaglio tecnico mostrato all'utente

    def test_connessione_persa_durante_il_download(self):
        asset = {"nome": "p.zip", "url": self.gh.base + "/download/p.zip", "digest": None}
        with mock.patch("requests.get", side_effect=requests.exceptions.ConnectionError("x")):
            with self.assertRaises(ErroreMessa) as c:
                ag.scarica(asset, Path(tempfile.mkdtemp()) / "p.zip", self.gh.base)
        self.assertEqual(c.exception.codice, "E01")


class TestScaricamentoEVerifica(unittest.TestCase):
    def setUp(self):
        self.gh = GitHubFinto()
        self.addCleanup(self.gh.chiudi)
        self.tmp = Path(tempfile.mkdtemp())

    def _asset(self, dati, digest=True):
        self.gh.pubblica("1.2.0", {"p.zip": dati}, digest=digest)
        a = self.gh.release["assets"][0]                                     # nel formato interno del programma
        return {"nome": a["name"], "url": a["browser_download_url"], "dimensione": a["size"], "digest": a.get("digest")}

    def test_scarica_e_controlla_sha256(self):
        dati = crea_zip("1.2.0")
        sha = ag.scarica(self._asset(dati), self.tmp / "p.zip", self.gh.base)
        self.assertEqual(sha, hashlib.sha256(dati).hexdigest())
        self.assertEqual((self.tmp / "p.zip").read_bytes(), dati)

    def test_file_diverso_da_quello_pubblicato(self):
        asset = self._asset(crea_zip("1.2.0"))
        self.gh.pacchetti["p.zip"] = b"contenuto manomesso"
        with self.assertRaises(ErroreMessa) as c:
            ag.scarica(asset, self.tmp / "p.zip", self.gh.base)
        self.assertEqual(c.exception.codice, "E11")
        self.assertIn("SHA-256", c.exception.dettaglio)

    def test_solo_da_github(self):
        for url in ("https://example.com/p.zip", "http://github.com/p.zip", "https://github.com.evil.it/p.zip",
                    "file:///etc/passwd", "ftp://github.com/p.zip"):
            with self.assertRaises(ErroreMessa, msg=url) as c:
                ag.scarica({"url": url}, self.tmp / "p.zip")                  # indirizzo GitHub reale: nessuna eccezione al controllo
            self.assertEqual(c.exception.codice, "E11")

    def test_pacchetto_troppo_grande(self):
        asset = self._asset(crea_zip("1.2.0"))
        with mock.patch.object(ag, "LIMITE_PACCHETTO", 50):
            with self.assertRaises(ErroreMessa) as c:
                ag.scarica(asset, self.tmp / "p.zip", self.gh.base)
        self.assertIn("grande", c.exception.dettaglio)

    def test_verifica_pacchetto_valido(self):
        z = self.tmp / "ok.zip"
        z.write_bytes(crea_zip("1.2.0"))
        self.assertEqual(ag.verifica_pacchetto(z, "1.2.0"), "messa_parrocchia")

    def _rifiutato(self, dati, versione="1.2.0"):
        z = self.tmp / "x.zip"
        z.write_bytes(dati)
        with self.assertRaises(ErroreMessa) as c:
            ag.verifica_pacchetto(z, versione)
        self.assertEqual(c.exception.codice, "E11")
        return c.exception.dettaglio

    def test_pacchetti_pericolosi_o_sbagliati(self):
        self._rifiutato(b"non sono uno zip")
        # percorso che esce dalla cartella ("zip slip")
        self._rifiutato(crea_zip("1.2.0", extra_voci=[("messa_parrocchia/../../fuori.txt", "x")]))
        self._rifiutato(crea_zip("1.2.0", extra_voci=[("/assoluto.txt", "x")]))
        self._rifiutato(crea_zip("1.2.0", extra_voci=[("C:/Windows/x.txt", "x")]))
        # collegamento simbolico
        link = zipfile.ZipInfo("messa_parrocchia/link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self._rifiutato(crea_zip("1.2.0", extra_voci=[(link, "/etc/passwd")]))
        # due cartelle principali
        self._rifiutato(crea_zip("1.2.0", extra_voci=[("altra/file.txt", "x")]))
        # mancano i file del programma
        self._rifiutato(crea_zip("1.2.0", contenuto={"leggimi.txt": "x"}))

    def test_versione_diversa_da_quella_della_release(self):
        self.assertIn("non corrisponde", self._rifiutato(crea_zip("1.3.0"), versione="1.2.0"))


class TestSostituzione(unittest.TestCase):
    def setUp(self):
        self.d = cartella_installata()
        self.zip = Path(tempfile.mkdtemp()) / "p.zip"
        self.zip.write_bytes(crea_zip("1.2.0"))

    def _applica(self):
        return ag.applica(self.zip, "messa_parrocchia", self.d, "1.1.0")

    def test_file_del_programma_aggiornati(self):
        r = self._applica()
        self.assertEqual(leggi(self.d, "app.py"), "# app nuova\n")
        self.assertIn("1.2.0", leggi(self.d, "messa/__init__.py"))
        self.assertTrue((self.d / "messa/nuovo.py").exists())
        self.assertGreaterEqual(r["sostituiti"], 4)

    def test_dati_della_parrocchia_mai_toccati(self):
        self._applica()
        self.assertEqual(leggi(self.d, "archivi/canti.pdf"), "PDF-DELLA-PARROCCHIA")          # il pacchetto ne aveva uno
        self.assertEqual(leggi(self.d, "config.json"), '{"parrocchia": "Mia parrocchia"}')
        self.assertEqual(leggi(self.d, "log.txt"), "diario")
        self.assertEqual(leggi(self.d, ".venv/bin/python"), "python")
        self.assertEqual(leggi(self.d, "cache/canti.json"), "{}")

    def test_testi_modificati_restano_e_i_nuovi_si_aggiungono(self):
        self._applica()
        self.assertEqual(leggi(self.d, "testi/gloria.txt"), "GLORIA MODIFICATO DALLA PARROCCHIA\n")
        self.assertEqual(leggi(self.d, "testi/novita.txt"), "testo nuovo\n")

    def test_promemoria_degli_archivi_si_aggiorna_ma_non_i_pdf(self):
        self._applica()
        self.assertEqual(leggi(self.d, "archivi/LEGGIMI.txt"), "promemoria nuovo\n")

    def test_permessi_di_esecuzione_conservati(self):
        self._applica()
        self.assertTrue(os.access(self.d / "Installa.command", os.X_OK))
        self.assertFalse(os.access(self.d / "app.py", os.X_OK))

    def test_file_non_piu_presenti_vengono_eliminati(self):
        r = self._applica()
        self.assertFalse((self.d / "messa/vecchio.py").exists())
        self.assertEqual(r["eliminati"], 1)

    def test_senza_manifest_vecchio_non_si_elimina_nulla(self):
        (self.d / "manifest.json").unlink()                               # installazione della 1.0.0
        r = self._applica()
        self.assertTrue((self.d / "messa/vecchio.py").exists())
        self.assertEqual(r["eliminati"], 0)

    def test_nessun_file_temporaneo_lasciato(self):
        self._applica()
        self.assertEqual(list(self.d.rglob("*.nuovo")), [])

    def test_ripristino_dopo_l_aggiornamento(self):
        self._applica()
        self.assertEqual(ag.leggi_meta(self.d)["versione_precedente"], "1.1.0")
        self.assertEqual(ag.ripristina_precedente(self.d), "1.1.0")
        self.assertEqual(leggi(self.d, "app.py"), "# app vecchia\n")
        self.assertTrue((self.d / "messa/vecchio.py").exists())            # file eliminato: tornato
        self.assertFalse((self.d / "messa/nuovo.py").exists())             # file aggiunto: tolto
        self.assertFalse((self.d / "testi/novita.txt").exists())
        self.assertEqual(leggi(self.d, "archivi/canti.pdf"), "PDF-DELLA-PARROCCHIA")
        self.assertIsNone(ag.leggi_meta(self.d))
        with self.assertRaises(ErroreMessa):
            ag.ripristina_precedente(self.d)                              # nulla da ripristinare due volte

    def test_errore_a_meta_riporta_tutto_com_era(self):
        vero = os.replace
        chiamate = []

        def guasto(a, b):
            chiamate.append(b)
            if len(chiamate) == 3:
                raise PermissionError("file in uso")
            return vero(a, b)
        with mock.patch.object(ag.os, "replace", side_effect=guasto):
            with self.assertRaises(ErroreMessa) as c:
                self._applica()
        self.assertEqual(c.exception.codice, "E11")
        self.assertEqual(leggi(self.d, "app.py"), "# app vecchia\n")
        self.assertIn("1.1.0", leggi(self.d, "messa/__init__.py"))
        self.assertTrue((self.d / "messa/vecchio.py").exists())
        self.assertFalse((self.d / "messa/nuovo.py").exists())

    def test_copie_di_sicurezza_limitate(self):
        for n in range(5):
            ag.applica(self.zip, "messa_parrocchia", self.d, f"1.1.{n}")
            time = __import__("time")
            time.sleep(1.1)                                              # nomi con data diversa
        self.assertLessEqual(len(list((self.d / "backup").glob("prima_di_*.zip"))), ag.COPIE_DA_TENERE)

    def test_cambio_dei_requisiti_viene_segnalato(self):
        self.assertFalse(self._applica()["dipendenze_cambiate"])
        z = Path(tempfile.mkdtemp()) / "q.zip"
        contenuto = contenuto_pacchetto("1.3.0")
        contenuto["requirements.txt"] = "requests\npdfplumber\n"
        z.write_bytes(crea_zip("1.3.0", contenuto))
        self.assertTrue(ag.applica(z, "messa_parrocchia", self.d, "1.2.0")["dipendenze_cambiate"])


class TestInstallazioneCompleta(unittest.TestCase):
    def setUp(self):
        self.gh = GitHubFinto()
        self.addCleanup(self.gh.chiudi)
        self.d = cartella_installata()
        self.mac = mock.patch.object(ag.sys, "platform", "darwin")
        self.mac.start()
        self.addCleanup(self.mac.stop)

    def _installa(self):
        return ag.installa("parrocchia/messa", self.d, self.gh.base, "1.1.0")

    def test_dal_controllo_all_installazione(self):
        self.gh.pubblica("1.2.0", {"Messa_Parrocchia_1.2.0_Mac.zip": crea_zip("1.2.0"),
                                   "Messa_Parrocchia_1.2.0_Windows.zip": b"non scelto"})
        r = self._installa()
        self.assertTrue(r["aggiornato"])
        self.assertEqual(r["versione"], "1.2.0")
        self.assertIn("1.2.0", leggi(self.d, "messa/__init__.py"))
        self.assertEqual(leggi(self.d, "archivi/canti.pdf"), "PDF-DELLA-PARROCCHIA")

    def test_gia_aggiornato_non_cambia_nulla(self):
        self.gh.pubblica("1.1.0", {"Messa_Parrocchia_1.1.0_Mac.zip": crea_zip("1.1.0")})
        r = self._installa()
        self.assertFalse(r["aggiornato"])
        self.assertEqual(leggi(self.d, "app.py"), "# app vecchia\n")
        self.assertFalse((self.d / "backup").exists())

    def test_pacchetto_manomesso_non_viene_installato(self):
        self.gh.pubblica("1.2.0", {"Messa_Parrocchia_1.2.0_Mac.zip": crea_zip("1.2.0")})
        self.gh.pacchetti["Messa_Parrocchia_1.2.0_Mac.zip"] = crea_zip("1.2.0", {"app.py": "malevolo"})
        with self.assertRaises(ErroreMessa) as c:
            self._installa()
        self.assertEqual(c.exception.codice, "E11")
        self.assertEqual(leggi(self.d, "app.py"), "# app vecchia\n")

    def test_pacchetto_con_versione_sbagliata_non_viene_installato(self):
        self.gh.pubblica("1.2.0", {"Messa_Parrocchia_1.2.0_Mac.zip": crea_zip("1.9.9")})
        with self.assertRaises(ErroreMessa):
            self._installa()
        self.assertEqual(leggi(self.d, "app.py"), "# app vecchia\n")

    def test_componenti_aggiornati_solo_se_cambiano_i_requisiti(self):
        contenuto = contenuto_pacchetto("1.2.0")
        contenuto["requirements.txt"] = "requests\npdfplumber\n"
        self.gh.pubblica("1.2.0", {"Messa_Parrocchia_1.2.0_Mac.zip": crea_zip("1.2.0", contenuto)})
        with mock.patch.object(ag, "_aggiorna_componenti", return_value="avviso di prova") as comp:
            r = self._installa()
        comp.assert_called_once()
        self.assertEqual(r["avvisi"], ["avviso di prova"])

    def test_riavvio(self):
        with mock.patch.object(ag.threading, "Thread", side_effect=lambda target, daemon: mock.Mock(start=target)), \
             mock.patch.object(ag.time, "sleep"), mock.patch.object(ag.os, "_exit") as uscita, \
             mock.patch.object(ag.subprocess, "Popen") as popen:
            ag.riavvia(self.d)
        argomenti, opzioni = popen.call_args
        self.assertEqual(argomenti[0], [ag.sys.executable, str(self.d / "app.py")])
        self.assertTrue(opzioni["start_new_session"])                        # sopravvive alla chiusura di questo processo
        uscita.assert_called_once_with(0)


class TestServizio(unittest.TestCase):
    def setUp(self):
        from messa.server import Servizio
        self.gh = GitHubFinto()
        self.addCleanup(self.gh.chiudi)
        self.sv = Servizio(html_prova=str(QUI / "pagina_cei_esempio.html"))
        self.sv.cfg["api_aggiornamenti"] = self.gh.base
        salva = mock.patch("messa.server.cfgmod.salva")
        salva.start()
        self.addCleanup(salva.stop)
        mac = mock.patch.object(ag.sys, "platform", "darwin")
        mac.start()
        self.addCleanup(mac.stop)

    def test_indirizzo_del_repository_normalizzato(self):
        for scritto in ("parrocchia/messa", "https://github.com/parrocchia/messa", "https://github.com/parrocchia/messa/",
                        "https://github.com/parrocchia/messa.git", " parrocchia/messa "):
            self.assertEqual(self.sv.imposta_aggiornamenti(scritto)["repository"], "parrocchia/messa", scritto)
        with self.assertRaises(ErroreMessa):
            self.sv.imposta_aggiornamenti("non valido")

    def test_controllo_automatico_si_puo_disattivare(self):
        self.assertTrue(self.sv.stato()["aggiornamenti"]["automatico"])
        self.assertFalse(self.sv.imposta_aggiornamenti(automatico=False)["automatico"])

    def test_controllo_dal_servizio(self):
        self.sv.imposta_aggiornamenti("parrocchia/messa")
        self.gh.pubblica("9.0.0", {"Messa_Parrocchia_9.0.0_Mac.zip": b"x"})
        r = self.sv.controlla_aggiornamenti()
        self.assertTrue(r["disponibile"])
        self.assertEqual(r["versione_corrente"], self.sv.stato()["versione"])

    def test_senza_repository_configurato(self):
        with self.assertRaises(ErroreMessa) as c:
            self.sv.controlla_aggiornamenti()
        self.assertEqual(c.exception.codice, "E10")


class TestCreaPacchetti(unittest.TestCase):
    def setUp(self):
        if not (QUI.parent / "strumenti" / "crea_pacchetti.py").exists():
            self.skipTest("pacchetto di installazione: lo strumento sta solo nel repository")
        sys.path.insert(0, str(QUI.parent / "strumenti"))
        import importlib
        import crea_pacchetti
        self.cp = importlib.reload(crea_pacchetti)
        self.uscita = Path(tempfile.mkdtemp())

    def test_contenuto_dei_pacchetti_pubblici(self):
        from messa import __version__
        mac = self.cp.raccogli("Mac")
        win = self.cp.raccogli("Windows")
        for elenco in (mac, win):
            self.assertNotIn("archivi/canti.pdf", elenco)
            self.assertNotIn("config.json", elenco)
            self.assertFalse([f for f in elenco if ".venv" in f or "__pycache__" in f or f.startswith(("dist/", "strumenti/"))])
            self.assertIn("app.py", elenco)
            self.assertIn("testi/gloria.txt", elenco)
        self.assertIn("Installa.command", mac)
        self.assertNotIn("Installa.bat", mac)
        self.assertIn("Installa.bat", win)
        self.assertNotIn("Installa.command", win)
        self.assertTrue(any(f.startswith("Messa Parrocchia.app/") for f in mac))
        self.assertFalse(any(f.startswith("Messa Parrocchia.app/") for f in win))
        self.assertEqual(self.cp.versione(), __version__)

    def test_pacchetto_valido_con_manifest_e_permessi(self):
        z = self.uscita / "m.zip"
        self.cp.crea("Mac", z)
        self.assertEqual(ag.verifica_pacchetto(z, self.cp.versione()), "messa_parrocchia")
        with zipfile.ZipFile(z) as arc:
            manifest = json.loads(arc.read("messa_parrocchia/manifest.json"))
            self.assertEqual(manifest["versione"], self.cp.versione())
            self.assertIn("app.py", manifest["file"])
            self.assertEqual(manifest["file"]["app.py"], self.cp.impronta(QUI.parent / "app.py"))
            for nome in ("Installa.command", "Messa Parrocchia.app/Contents/MacOS/avvia"):
                self.assertTrue((arc.getinfo(f"messa_parrocchia/{nome}").external_attr >> 16) & 0o111, nome)
            self.assertFalse((arc.getinfo("messa_parrocchia/app.py").external_attr >> 16) & 0o111)
            self.assertFalse([n for n in arc.namelist() if n.startswith("messa_parrocchia/archivi/") and n.endswith(".pdf")])

    def test_permessi_scritti_nel_formato_completo_che_macos_capisce(self):
        """Senza il tipo 'file normale' (S_IFREG) macOS non rende eseguibili i file: 'Installa.command' non parte."""
        for sistema in ("Mac", "Windows"):
            z = self.uscita / f"{sistema}.zip"
            self.cp.crea(sistema, z)
            with zipfile.ZipFile(z) as arc:
                for info in arc.infolist():
                    modo = info.external_attr >> 16
                    self.assertEqual(info.create_system, 3, info.filename)             # creato come "Unix"
                    self.assertTrue(stat.S_ISREG(modo), f"{info.filename}: manca il tipo di file ({oct(modo)})")
                    self.assertEqual(stat.S_IMODE(modo) & 0o600, 0o600, info.filename)  # leggibile e scrivibile da chi lo usa
        z = self.uscita / "Mac.zip"
        self.cp.crea("Mac", z)
        with zipfile.ZipFile(z) as arc:
            for nome in ("Installa.command", "Avvia con Terminale.command", "Messa Parrocchia.app/Contents/MacOS/avvia"):
                modo = arc.getinfo(f"messa_parrocchia/{nome}").external_attr >> 16
                self.assertEqual(oct(modo), "0o100755", nome)                          # esattamente come fa il comando 'zip'
            self.assertEqual(oct(arc.getinfo("messa_parrocchia/app.py").external_attr >> 16), "0o100644")

    def test_il_pacchetto_pubblico_si_installa_sopra_una_cartella_con_i_dati(self):
        """Prova completa: costruisco davvero il pacchetto e lo applico a un programma con PDF e impostazioni."""
        z = self.uscita / "m.zip"
        self.cp.crea("Mac", z)
        d = cartella_installata("1.0.0")
        (d / "manifest.json").unlink()
        ag.applica(z, ag.verifica_pacchetto(z, self.cp.versione()), d, "1.0.0")
        self.assertEqual(leggi(d, "archivi/canti.pdf"), "PDF-DELLA-PARROCCHIA")
        self.assertEqual(leggi(d, "config.json"), '{"parrocchia": "Mia parrocchia"}')
        self.assertEqual(leggi(d, "testi/gloria.txt"), "GLORIA MODIFICATO DALLA PARROCCHIA\n")
        self.assertTrue((d / "web" / "index.html").exists())
        self.assertIn(self.cp.versione(), leggi(d, "messa/__init__.py"))
        self.assertTrue(os.access(d / "Installa.command", os.X_OK))

    def test_pacchetti_con_canti_solo_su_richiesta(self):
        self.assertNotIn("archivi/canti.pdf", self.cp.raccogli("Mac"))
        pdf = QUI.parent / "archivi" / "canti.pdf"
        creato = not pdf.exists()                                         # nel repository il PDF non c'e': ne metto uno finto
        if creato:
            pdf.write_bytes(b"%PDF-finto")
        try:
            self.assertIn("archivi/canti.pdf", self.cp.raccogli("Mac", con_canti=True))
            self.assertNotIn("archivi/canti.pdf", self.cp.raccogli("Mac"))
        finally:
            if creato:
                pdf.unlink()


if __name__ == "__main__":
    unittest.main()
