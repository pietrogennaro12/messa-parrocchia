# -*- coding: utf-8 -*-
"""
Server locale (solo 127.0.0.1) che alimenta l'interfaccia grafica nel browser.
Tutta la logica sta nei moduli di 'messa': qui ci sono solo le chiamate dell'interfaccia.
"""
import dataclasses
import datetime as dt
import json
import secrets
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from . import aggiornamenti
from . import config as cfgmod
from . import dialoghi
from .canti import ArchivioCanti
from .config import BASE
from .errori import ErroreMessa
from .generatore import genera, nome_file_valido, prepara_piano, usa_frontespizio
from .liturgia import Liturgia, recupera_liturgia
from .preghiere import leggi_preghiere
from .sezioni import SEZIONI

LOG = BASE / "log.txt"


def log(testo):
    """Diario del programma: nella cartella del programma o, se non e' scrivibile, in ~/Library/Logs (o home)."""
    riga = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {testo}\n"
    alternativo = Path.home() / "Library" / "Logs" / "Messa Parrocchia" / "programma.log"
    for percorso in (LOG, alternativo, Path.home() / "messa_parrocchia_log.txt"):
        try:
            percorso.parent.mkdir(parents=True, exist_ok=True)
            with open(percorso, "a", encoding="utf-8") as f:
                f.write(riga)
            return
        except OSError:
            continue


def prossima_domenica(oggi=None):
    oggi = oggi or dt.date.today()
    return oggi + dt.timedelta(days=(6 - oggi.weekday()) % 7)


class Servizio:
    """Stato dell'applicazione."""

    def __init__(self, html_prova=None):
        self.cfg = cfgmod.carica()
        self.html_prova = html_prova
        self.archivio_canti = None
        self.errore_canti = None
        self.liturgie = {}
        self.ultimo_ping = time.time()
        self.modalita = "browser"             # "finestra" quando il programma ha una finestra propria
        self.token = secrets.token_urlsafe(16)
        self.ricarica_canti()

    # --- archivi ------------------------------------------------------------
    def ricarica_canti(self):
        self.archivio_canti, self.errore_canti = None, None
        try:
            self.archivio_canti = ArchivioCanti(cfgmod.percorso(self.cfg["pdf_canti"]))
        except ErroreMessa as e:
            self.errore_canti = e
            log(f"{e}")

    def stato_preghiere(self):
        p = cfgmod.percorso(self.cfg["pdf_preghiere"])
        try:
            n = len(leggi_preghiere(p, self.cfg.get("pagine_preghiere", "")))
            return {"ok": True, "errore": None, "paragrafi": n}
        except ErroreMessa as e:
            return {"ok": False, "errore": e.come_dict()}

    def stato_archivi(self):
        return {
            "canti": {"percorso": str(cfgmod.percorso(self.cfg["pdf_canti"])),
                      "ok": self.archivio_canti is not None,
                      "errore": self.errore_canti.come_dict() if self.errore_canti else None,
                      "numero": len(self.archivio_canti.canti) if self.archivio_canti else 0},
            "preghiere": dict(self.stato_preghiere(),
                              percorso=str(cfgmod.percorso(self.cfg["pdf_preghiere"])),
                              pagine=self.cfg.get("pagine_preghiere", "")),
        }

    def stato(self):
        predefiniti = {}
        if self.archivio_canti:
            for slot, titolo in self.cfg.get("canti_predefiniti", {}).items():
                c = self.archivio_canti.per_titolo(titolo)
                if c:
                    predefiniti[slot] = c["id"]
        return {
            "parrocchia": self.cfg["parrocchia"],
            "sezioni": [{"id": s["id"], "nome": s["nome"], "fonte": s["fonte"], "slot": s.get("slot"),
                         "nota": s.get("nota"),
                         "varianti": [{"id": v["id"], "etichetta": v["etichetta"], "tipo": v["tipo"],
                                       "slot": v.get("slot")} for v in s.get("varianti", [])]}
                        for s in SEZIONI],
            "canti": self.archivio_canti.titoli() if self.archivio_canti else [],
            "archivi": self.stato_archivi(),
            "cartella_output": str(Path(self.cfg["cartella_output"]).expanduser()),
            "gestore_file": dialoghi.gestore_file(),
            "finestra": self.modalita == "finestra",
            "versione": __version__,
            "aggiornamenti": self.stato_aggiornamenti(),
            "data_predefinita": prossima_domenica().isoformat(),
            "canti_predefiniti": predefiniti,
        }

    def imposta_archivio(self, tipo, percorso=None, pagine=None):
        if tipo == "canti":
            if percorso:
                self.cfg["pdf_canti"] = percorso
            self.ricarica_canti()
        elif tipo == "preghiere":
            if percorso:
                self.cfg["pdf_preghiere"] = percorso
            if pagine is not None:
                self.cfg["pagine_preghiere"] = pagine.strip()
        cfgmod.salva(self.cfg)
        return self.stato_archivi()

    # --- aggiornamenti --------------------------------------------------------
    def _api(self):
        return self.cfg.get("api_aggiornamenti") or aggiornamenti.API_GITHUB      # (cambia solo nelle prove)

    def stato_aggiornamenti(self):
        meta = aggiornamenti.leggi_meta()
        return {"repository": self.cfg.get("repository_aggiornamenti", ""),
                "automatico": bool(self.cfg.get("controllo_automatico", True)),
                "ripristino": meta["versione_precedente"] if meta else None}

    def imposta_aggiornamenti(self, repository=None, automatico=None):
        if repository is not None:
            repository = repository.strip().replace("https://github.com/", "").strip("/")
            if repository.endswith(".git"):
                repository = repository[:-4]
            if not aggiornamenti.REPOSITORY.match(repository):
                raise ErroreMessa("E10", "Indirizzo non valido: scrivi utente/nome (per esempio parrocchia/messa-parrocchia).")
            self.cfg["repository_aggiornamenti"] = repository
        if automatico is not None:
            self.cfg["controllo_automatico"] = bool(automatico)
        cfgmod.salva(self.cfg)
        return self.stato_aggiornamenti()

    def controlla_aggiornamenti(self):
        return aggiornamenti.controlla(self.cfg.get("repository_aggiornamenti"), api_base=self._api())

    def installa_aggiornamento(self):
        r = aggiornamenti.installa(self.cfg.get("repository_aggiornamenti"), api_base=self._api())
        self.liturgie.clear()
        return r

    def ripristina_versione(self):
        return {"versione": aggiornamenti.ripristina_precedente()}

    # --- liturgia -----------------------------------------------------------
    @staticmethod
    def _data(testo):
        try:
            return dt.date.fromisoformat(testo)
        except (TypeError, ValueError):
            raise ErroreMessa("E03", "Data non valida.")

    def carica_liturgia(self, testo_data):
        data = self._data(testo_data)
        lit = recupera_liturgia(data, self.html_prova)
        self.liturgie[data.isoformat()] = lit
        n = max(1, len(lit.formulari))
        formulari = []
        for i in range(n):
            f = lit.con_formulario(i)
            formulari.append({"etichetta": (lit.formulari[i]["etichetta"] if len(lit.formulari) > 1 else None),
                              "disponibili": [s["id"] for s in SEZIONI
                                              if s["fonte"] == "cei" and f.trova(s["chiavi"])]})
        return {"nome": lit.nome, "colore": lit.colore_nome, "colore_hex": lit.colore_hex,
                "formulari": formulari, "disponibili": formulari[0]["disponibili"], "avvisi": lit.avvisi}

    # --- generazione --------------------------------------------------------
    def genera(self, r):
        data = self._data(r.get("data"))
        scelte = set(r.get("sezioni", []))
        if not scelte:
            raise ErroreMessa("E08", "Nessuna sezione selezionata.")
        serve_sito = (any(s["fonte"] == "cei" and s["id"] in scelte for s in SEZIONI)
                      or usa_frontespizio(scelte, r.get("varianti", {})))
        lit = self.liturgie.get(data.isoformat())
        if lit is None and serve_sito:
            lit = recupera_liturgia(data, self.html_prova)
            self.liturgie[data.isoformat()] = lit
        lit = (lit or Liturgia(data=data)).con_formulario(r.get("formulario") or 0)
        nome_celebrazione = (r.get("nome_celebrazione") or "").strip()
        if nome_celebrazione:                                  # nome scritto/corretto a mano nell'interfaccia
            lit = dataclasses.replace(lit, nome=nome_celebrazione)

        piano, avvisi = prepara_piano(data, scelte, r.get("canti", {}), lit,
                                      self.archivio_canti, self.errore_canti, self.cfg,
                                      r.get("varianti", {}), r.get("canti_extra", []))
        problemi = [a for a in avvisi if a["codice"] != "INFO"]
        if problemi and not r.get("conferma"):
            return {"richiede_conferma": True, "avvisi": avvisi}

        cartella = r.get("cartella") or self.cfg["cartella_output"]
        nome = nome_file_valido(r.get("nome_file"), data)
        n, destinazione = genera(piano, self.cfg, lit.colore_hex, Path(cartella), nome,
                                 bool(r.get("sovrascrivi")))
        if n is None:
            return {"esiste": True, "file": str(destinazione)}
        self.cfg["cartella_output"] = str(cartella)
        cfgmod.salva(self.cfg)
        return {"file": str(destinazione), "slide": n, "avvisi": avvisi}


# ----------------------------------------------------------------------------

def crea_handler(servizio: Servizio):
    pagina = (BASE / "web" / "index.html").read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        server_version = "MessaParrocchia/1.0"

        def log_message(self, formato, *a):      # niente rumore nel terminale
            pass

        def _host_ok(self):
            return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

        def _invia(self, codice, contenuto: bytes, tipo):
            self.send_response(codice)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(contenuto)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(contenuto)

        def do_GET(self):
            if not self._host_ok():
                return self._invia(403, b"", "text/plain")
            if self.path.split("?")[0] in ("/", "/index.html"):
                html = pagina.replace("{{TOKEN}}", servizio.token)
                return self._invia(200, html.encode("utf-8"), "text/html; charset=utf-8")
            self._invia(404, b"Non trovato", "text/plain")

        def do_POST(self):
            if not self._host_ok() or self.headers.get("X-Token") != servizio.token:
                return self._invia(403, b"", "text/plain")
            try:
                lung = int(self.headers.get("Content-Length", 0))
                dati = json.loads(self.rfile.read(lung) or b"{}")
            except ValueError:
                dati = {}
            try:
                risposta = {"ok": True, **self._rotta(self.path, dati)}
            except ErroreMessa as e:
                log(str(e))
                risposta = {"ok": False, "errore": e.come_dict()}
            except Exception as e:               # nessun errore deve chiudere il programma
                log(traceback.format_exc())
                risposta = {"ok": False, "errore": {"codice": "E99", "messaggio":
                            "Errore imprevisto. Il dettaglio è nel file log.txt.", "dettaglio": str(e)[:150]}}
            self._invia(200, json.dumps(risposta, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")

        def _rotta(self, path, d):
            s = servizio
            if path == "/api/ping":
                s.ultimo_ping = time.time()
                return {}
            if path == "/api/stato":
                return s.stato()
            if path == "/api/liturgia":
                return s.carica_liturgia(d.get("data"))
            if path == "/api/archivio":
                return {"archivi": s.imposta_archivio(d.get("tipo"), d.get("percorso"), d.get("pagine"))}
            if path == "/api/sfoglia":
                scelta = (dialoghi.scegli_cartella("Scegli la cartella di destinazione")
                          if d.get("tipo") == "cartella" else dialoghi.scegli_pdf("Scegli il file PDF"))
                return {"percorso": scelta}
            if path == "/api/genera":
                return s.genera(d)
            if path == "/api/rivela":
                dialoghi.mostra_nel_finder(d.get("file", ""))
                return {}
            if path == "/api/aggiornamenti/controlla":
                return s.controlla_aggiornamenti()
            if path == "/api/aggiornamenti/installa":
                return s.installa_aggiornamento()
            if path == "/api/aggiornamenti/ripristina":
                return s.ripristina_versione()
            if path == "/api/aggiornamenti/impostazioni":
                return s.imposta_aggiornamenti(d.get("repository"), d.get("automatico"))
            if path == "/api/riavvia":
                aggiornamenti.riavvia()
                return {}
            if path == "/api/esci":
                import threading
                threading.Thread(target=lambda: (time.sleep(0.5), __import__("os")._exit(0)), daemon=True).start()
                return {}
            raise ErroreMessa("E99", f"Richiesta sconosciuta: {path}")

    return Handler


def avvia(servizio: Servizio, porta=0):
    server = ThreadingHTTPServer(("127.0.0.1", porta), crea_handler(servizio))
    return server
