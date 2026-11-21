# -*- coding: utf-8 -*-
"""
Aggiornamento del programma da GitHub ("Aggiorna versione").

Come funziona
  1. controlla  : chiede a GitHub l'ultima "release" del repository (pubblico, senza password);
  2. scarica    : il pacchetto .zip adatto a questo computer (Mac o Windows);
  3. verifica   : integrita' dello zip, percorsi sicuri, numero di versione coerente con la release;
  4. salva      : una copia di sicurezza di cio' che sta per essere sostituito;
  5. sostituisce: i file del programma. NON si toccano mai PDF, impostazioni, cartella .venv, diario e
                  testi gia' presenti (potresti averli modificati): dei testi si aggiungono solo i nuovi;
  6. riavvia.
In caso di errore si torna automaticamente alla versione precedente; "ripristina_precedente" permette di
tornarci anche dopo.
"""
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import __version__
from .config import BASE
from .errori import ErroreMessa

API_GITHUB = "https://api.github.com"
HOST_GITHUB = {"github.com", "api.github.com", "objects.githubusercontent.com",
               "release-assets.githubusercontent.com", "github-releases.githubusercontent.com"}
LIMITE_PACCHETTO = 100 * 1024 * 1024        # dimensione massima del file scaricato
LIMITE_DECOMPRESSO = 250 * 1024 * 1024      # dimensione massima dopo la decompressione
MAX_FILE = 3000
COPIE_DA_TENERE = 3
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


# ----------------------------------------------------------------------------
# versioni
# ----------------------------------------------------------------------------

def parse_versione(testo):
    """'v1.2.0' o '1.2.0' -> (1, 2, 0); altrimenti None."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (testo or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def _testo_versione(t):
    return ".".join(str(x) for x in t)


def sistema():
    """'Windows', 'Mac' o None: serve a scegliere il pacchetto giusto."""
    if sys.platform.startswith("win"):
        return "Windows"
    if sys.platform == "darwin":
        return "Mac"
    return None


def scegli_asset(assets):
    chiave = (sistema() or "").lower()
    for a in assets or []:
        nome = (a.get("name") or "")
        if chiave and nome.lower().endswith(".zip") and chiave in nome.lower():
            return {"nome": nome, "url": a.get("browser_download_url"), "dimensione": a.get("size"),
                    "digest": a.get("digest")}
    return None


# ----------------------------------------------------------------------------
# 1. controllo
# ----------------------------------------------------------------------------

def controlla(repository, versione_corrente=__version__, api_base=API_GITHUB, timeout=15):
    """Restituisce un dizionario con l'ultima versione pubblicata e se e' piu' nuova di quella in uso."""
    repository = (repository or "").strip()
    if not REPOSITORY.match(repository):
        raise ErroreMessa("E10", "Indirizzo del repository non valido: scrivi utente/nome.")
    url = f"{api_base}/repos/{repository}/releases/latest"
    try:
        r = requests.get(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "messa-parrocchia"},
                         timeout=timeout)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise ErroreMessa("E01")                                  # il dettaglio tecnico non serve a chi usa il programma
    except requests.exceptions.RequestException as e:
        raise ErroreMessa("E10", str(e)[:120])
    if r.status_code == 404:
        raise ErroreMessa("E10", "Nessuna versione trovata: il repository dev'essere pubblico e avere almeno una release.")
    if r.status_code in (403, 429):
        raise ErroreMessa("E10", "GitHub ha limitato le richieste: riprova tra qualche minuto.")
    if r.status_code >= 400:
        raise ErroreMessa("E10", f"Risposta di GitHub: {r.status_code}.")
    try:
        dati = r.json()
    except ValueError:
        raise ErroreMessa("E10", "Risposta di GitHub non leggibile.")

    nuova = parse_versione(dati.get("tag_name"))
    corrente = parse_versione(versione_corrente)
    if nuova is None:
        raise ErroreMessa("E10", f"La versione pubblicata («{dati.get('tag_name')}») non ha il formato 1.2.3.")
    info = {"versione_corrente": versione_corrente, "versione": _testo_versione(nuova),
            "disponibile": bool(corrente and nuova > corrente), "note": (dati.get("body") or "").strip(),
            "pagina": dati.get("html_url"), "asset": scegli_asset(dati.get("assets"))}
    if info["disponibile"] and not info["asset"]:
        raise ErroreMessa("E10", f"La versione {info['versione']} non ha il pacchetto per {sistema() or 'questo computer'}.")
    return info


# ----------------------------------------------------------------------------
# 2. scaricamento
# ----------------------------------------------------------------------------

def _host_ammessi(api_base):
    ammessi = set(HOST_GITHUB)
    if api_base.rstrip("/") != API_GITHUB:                 # solo per prove: un server locale scelto a mano
        ammessi.add(urlparse(api_base).hostname)
    return ammessi


def _controlla_indirizzo(url, ammessi, api_base):
    p = urlparse(url or "")
    https_obbligatorio = api_base.rstrip("/") == API_GITHUB
    if p.hostname not in ammessi or (https_obbligatorio and p.scheme != "https") or p.scheme not in ("http", "https"):
        raise ErroreMessa("E11", f"Indirizzo di download non ammesso: {p.hostname}")


def scarica(asset, destinazione, api_base=API_GITHUB, timeout=60):
    """Scarica il pacchetto; restituisce lo SHA-256. Solo da GitHub, solo https, con limite di dimensione."""
    ammessi = _host_ammessi(api_base)
    _controlla_indirizzo(asset.get("url"), ammessi, api_base)
    try:
        with requests.get(asset["url"], stream=True, timeout=timeout, headers={"User-Agent": "messa-parrocchia"}) as r:
            for passo in list(r.history) + [r]:                # anche i reindirizzamenti devono restare su GitHub
                _controlla_indirizzo(passo.url, ammessi, api_base)
            if r.status_code != 200:
                raise ErroreMessa("E11", f"Download non riuscito (risposta {r.status_code}).")
            lunghezza = int(r.headers.get("Content-Length") or 0)
            if lunghezza > LIMITE_PACCHETTO:
                raise ErroreMessa("E11", "Il pacchetto è troppo grande.")
            sha, totale = hashlib.sha256(), 0
            with open(destinazione, "wb") as f:
                for pezzo in r.iter_content(64 * 1024):
                    totale += len(pezzo)
                    if totale > LIMITE_PACCHETTO:
                        raise ErroreMessa("E11", "Il pacchetto è troppo grande.")
                    sha.update(pezzo)
                    f.write(pezzo)
    except ErroreMessa:
        raise
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise ErroreMessa("E01")
    except requests.exceptions.RequestException as e:
        raise ErroreMessa("E11", f"Download interrotto: {str(e)[:100]}")
    calcolato = sha.hexdigest()
    atteso = (asset.get("digest") or "")
    if atteso.startswith("sha256:") and atteso[7:].lower() != calcolato:
        raise ErroreMessa("E11", "Il file scaricato non corrisponde a quello pubblicato (controllo SHA-256).")
    return calcolato


# ----------------------------------------------------------------------------
# 3. verifica del pacchetto
# ----------------------------------------------------------------------------

def verifica_pacchetto(percorso_zip, versione_attesa):
    """Controlla lo zip prima di usarlo. Restituisce il nome della cartella principale."""
    try:
        z = zipfile.ZipFile(percorso_zip)
    except zipfile.BadZipFile:
        raise ErroreMessa("E11", "Il file scaricato non è uno zip valido.")
    with z:
        if z.testzip() is not None:
            raise ErroreMessa("E11", "Il pacchetto è danneggiato.")
        infos = z.infolist()
        if len(infos) > MAX_FILE or sum(i.file_size for i in infos) > LIMITE_DECOMPRESSO:
            raise ErroreMessa("E11", "Il pacchetto ha dimensioni anomale.")
        radici = set()
        for i in infos:
            nome = i.filename
            parti = Path(nome.replace("\\", "/")).parts
            if (nome.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", nome) or ".." in parti
                    or "\\" in nome or stat.S_ISLNK(i.external_attr >> 16)):
                raise ErroreMessa("E11", f"Percorso non ammesso nel pacchetto: {nome[:60]}")
            radici.add(nome.split("/")[0])
        if len(radici) != 1:
            raise ErroreMessa("E11", "Il pacchetto non ha la struttura attesa.")
        radice = radici.pop()
        nomi = {i.filename for i in infos}
        if f"{radice}/app.py" not in nomi or f"{radice}/messa/__init__.py" not in nomi:
            raise ErroreMessa("E11", "Nel pacchetto mancano i file del programma.")
        m = re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"', z.read(f"{radice}/messa/__init__.py").decode("utf-8", "replace"))
        if not m or m.group(1) != versione_attesa:
            raise ErroreMessa("E11", f"La versione nel pacchetto ({m.group(1) if m else '?'}) non corrisponde alla release ({versione_attesa}).")
    return radice


# ----------------------------------------------------------------------------
# 4-5. sostituzione dei file (con copia di sicurezza)
# ----------------------------------------------------------------------------

def protetto(rel: str, esiste: bool) -> bool:
    """File che l'aggiornamento NON deve toccare."""
    p = rel.replace("\\", "/")
    if p.startswith((".venv/", "cache/", "backup/", ".git/")) or p in ("config.json", "log.txt"):
        return True
    if p.startswith("archivi/") and p.lower().endswith(".pdf"):
        return True                                          # i PDF della parrocchia
    if p.startswith(("testi/", "web/img/")) and esiste:
        return True                                          # testi e immagini forse personalizzati: si aggiungono solo i nuovi
    return False


def _sha(percorso: Path) -> str:
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for pezzo in iter(lambda: f.read(65536), b""):
            h.update(pezzo)
    return h.hexdigest()


def _manifest(cartella: Path):
    try:
        return json.loads((cartella / "manifest.json").read_text(encoding="utf-8")).get("file", {})
    except (OSError, ValueError):
        return None


def _requisiti(cartella: Path):
    return tuple(_sha(cartella / n) if (cartella / n).exists() else "" for n in ("requirements.txt", "requirements-finestra.txt"))


def _pulisci_copie(cartella_backup: Path):
    zips = sorted(cartella_backup.glob("prima_di_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for vecchio in zips[COPIE_DA_TENERE:]:
        vecchio.unlink(missing_ok=True)


def applica(percorso_zip, radice, cartella=BASE, versione_precedente=__version__):
    """Sostituisce i file del programma con quelli del pacchetto. Restituisce un riepilogo."""
    cartella = Path(cartella)
    backup = cartella / "backup"
    backup.mkdir(exist_ok=True)
    requisiti_prima = _requisiti(cartella)
    manifest_vecchio = _manifest(cartella)

    with zipfile.ZipFile(percorso_zip) as z:
        voci, tutti = [], set()
        for i in z.infolist():
            if i.is_dir():
                continue
            rel = i.filename[len(radice) + 1:]
            if not rel:
                continue
            tutti.add(rel)
            if not protetto(rel, (cartella / rel).exists()):
                voci.append((i, rel))

        obsoleti = []
        if manifest_vecchio is not None:                    # file che la versione nuova non ha piu'
            obsoleti = [p for p in manifest_vecchio if p not in tutti and not protetto(p, True) and (cartella / p).is_file()]

        # copia di sicurezza: tutto cio' che sta per essere sostituito o eliminato
        nuovi = [rel for _, rel in voci if not (cartella / rel).exists()]
        nome_backup = f"prima_di_{versione_precedente}_{datetime.now():%Y%m%d-%H%M%S}.zip"
        with zipfile.ZipFile(backup / nome_backup, "w", zipfile.ZIP_DEFLATED) as b:
            for rel in [r for _, r in voci if (cartella / r).exists()] + obsoleti:
                b.write(cartella / rel, rel)
        meta = {"versione_precedente": versione_precedente, "file": nome_backup, "nuovi": nuovi}
        (backup / "ultimo.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        _pulisci_copie(backup)

        try:
            for info, rel in voci:
                destinazione = cartella / rel
                destinazione.parent.mkdir(parents=True, exist_ok=True)
                temporaneo = destinazione.with_name(destinazione.name + ".nuovo")
                with z.open(info) as origine, open(temporaneo, "wb") as scritto:
                    shutil.copyfileobj(origine, scritto)
                eseguibile = (info.external_attr >> 16) & 0o111
                os.chmod(temporaneo, 0o755 if eseguibile else 0o644)
                os.replace(temporaneo, destinazione)
            for rel in obsoleti:
                (cartella / rel).unlink(missing_ok=True)
        except Exception as e:
            _ripristina_da(cartella, meta)
            raise ErroreMessa("E11", f"{type(e).__name__}: {str(e)[:100]}")

    return {"sostituiti": len(voci), "nuovi": len(nuovi), "eliminati": len(obsoleti),
            "mantenuti": len(tutti) - len(voci), "dipendenze_cambiate": requisiti_prima != _requisiti(cartella)}


def _ripristina_da(cartella: Path, meta: dict):
    backup = cartella / "backup"
    with zipfile.ZipFile(backup / meta["file"]) as b:
        for info in b.infolist():
            destinazione = cartella / info.filename
            destinazione.parent.mkdir(parents=True, exist_ok=True)
            with b.open(info) as o, open(destinazione, "wb") as w:
                shutil.copyfileobj(o, w)
            eseguibile = (info.external_attr >> 16) & 0o111
            os.chmod(destinazione, 0o755 if eseguibile else 0o644)
    for rel in meta.get("nuovi", []):
        (cartella / rel).unlink(missing_ok=True)


def leggi_meta(cartella=BASE):
    try:
        return json.loads((Path(cartella) / "backup" / "ultimo.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ripristina_precedente(cartella=BASE):
    """Torna alla versione salvata prima dell'ultimo aggiornamento. Restituisce il numero di versione."""
    cartella = Path(cartella)
    meta = leggi_meta(cartella)
    if not meta or not (cartella / "backup" / meta["file"]).exists():
        raise ErroreMessa("E11", "Non c'è una versione precedente da ripristinare.")
    try:
        _ripristina_da(cartella, meta)
    except Exception as e:
        raise ErroreMessa("E11", f"{type(e).__name__}: {str(e)[:100]}")
    (cartella / "backup" / "ultimo.json").unlink(missing_ok=True)
    return meta["versione_precedente"]


# ----------------------------------------------------------------------------
# orchestrazione e riavvio
# ----------------------------------------------------------------------------

def _aggiorna_componenti(cartella: Path):
    """Se i requisiti sono cambiati installa i componenti nuovi; restituisce un avviso se non riesce."""
    from .dialoghi import _python_con_console
    for nome in ("requirements.txt", "requirements-finestra.txt"):
        if not (cartella / nome).exists():
            continue
        try:
            r = subprocess.run([_python_con_console(), "-m", "pip", "install", "-r", str(cartella / nome), "-q"],
                               capture_output=True, text=True, timeout=900,
                               **({"creationflags": 0x08000000} if sys.platform.startswith("win") else {}))
            if r.returncode != 0 and nome == "requirements.txt":
                return "Alcuni componenti non si sono aggiornati: rifai l'installazione (Installa) se qualcosa non funziona."
        except Exception:
            if nome == "requirements.txt":
                return "Alcuni componenti non si sono aggiornati: rifai l'installazione (Installa) se qualcosa non funziona."
    return None


def installa(repository, cartella=BASE, api_base=API_GITHUB, versione_corrente=__version__):
    """Controlla, scarica, verifica e applica. Restituisce un riepilogo (o 'disponibile': False)."""
    info = controlla(repository, versione_corrente, api_base)
    if not info["disponibile"]:
        return {"aggiornato": False, **info}
    with tempfile.TemporaryDirectory() as t:
        pacchetto = Path(t) / "aggiornamento.zip"
        scarica(info["asset"], pacchetto, api_base)
        radice = verifica_pacchetto(pacchetto, info["versione"])
        riepilogo = applica(pacchetto, radice, cartella, versione_corrente)
    avvisi = []
    if riepilogo["dipendenze_cambiate"]:
        avviso = _aggiorna_componenti(Path(cartella))
        if avviso:
            avvisi.append(avviso)
    return {"aggiornato": True, "versione": info["versione"], "avvisi": avvisi, **riepilogo}


def riavvia(cartella=BASE, ritardo=0.8):
    """Avvia una nuova copia del programma e chiude questa."""
    def lavoro():
        time.sleep(ritardo)
        argomenti = [sys.executable, str(Path(cartella) / "app.py")]
        opzioni = {"cwd": str(cartella), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                   "stderr": subprocess.DEVNULL, "close_fds": True}
        if sys.platform.startswith("win"):
            opzioni["creationflags"] = 0x00000008 | 0x00000200      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        else:
            opzioni["start_new_session"] = True
        subprocess.Popen(argomenti, **opzioni)
        os._exit(0)
    threading.Thread(target=lavoro, daemon=True).start()
