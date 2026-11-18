#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prepara i pacchetti da pubblicare in una release di GitHub.

    python3 strumenti/crea_pacchetti.py              ->  dist/Messa_Parrocchia_<versione>_Mac.zip
                                                         dist/Messa_Parrocchia_<versione>_Windows.zip
    python3 strumenti/crea_pacchetti.py --con-canti  ->  in piu': versioni "_con_canti" per l'installazione
                                                         PRIVATA (contengono il PDF dei canti: NON pubblicarle!)

I pacchetti pubblici non contengono il PDF dei canti, le impostazioni, il diario e l'ambiente di installazione.
Ognuno contiene un "manifest.json" (elenco dei file con impronta SHA-256) che permette agli aggiornamenti
successivi di eliminare i file diventati inutili.
Scrive anche dist/SHA256SUMS.txt.
"""
import argparse
import fnmatch
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CARTELLA_NEL_ZIP = "messa_parrocchia"

ESCLUSI = [".git/*", ".venv/*", "__pycache__/*", "*/__pycache__/*", "*.pyc", "cache/*", "backup/*", "dist/*",
           "strumenti/*", "config.json", "log.txt", "*.pptx", ".DS_Store", "*/.DS_Store", "Messe/*", "manifest.json",
           "Thumbs.db", ".gitignore"]
SOLO_MAC = ["Installa.command", "Avvia con Terminale.command", "Messa Parrocchia.app/*"]
SOLO_WINDOWS = ["Installa.bat", "crea_collegamento.ps1", "Messa Parrocchia.vbs"]


def versione():
    testo = (RADICE / "messa" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"', testo).group(1)


def _corrisponde(rel, modelli):
    return any(fnmatch.fnmatch(rel, m) for m in modelli)


def raccogli(sistema, con_canti=False):
    """Elenco ordinato dei file (percorsi relativi, con '/') del pacchetto per 'Mac' o 'Windows'."""
    esclusi = list(ESCLUSI) + (SOLO_WINDOWS if sistema == "Mac" else SOLO_MAC)
    file = []
    for p in sorted(RADICE.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(RADICE).as_posix()
        if rel == "archivi/canti.pdf" and con_canti:
            file.append(rel)
            continue
        if rel.startswith("archivi/") and rel.lower().endswith(".pdf"):
            continue                                            # i PDF della parrocchia non sono mai pubblici
        if not _corrisponde(rel, esclusi):
            file.append(rel)
    return file


def _eseguibile(rel):
    return rel.endswith(".command") or rel.endswith("/MacOS/avvia")


def impronta(percorso):
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for pezzo in iter(lambda: f.read(65536), b""):
            h.update(pezzo)
    return h.hexdigest()


def crea(sistema, destinazione, con_canti=False):
    file = raccogli(sistema, con_canti)
    manifest = {"versione": versione(), "sistema": sistema,
                "file": {rel: impronta(RADICE / rel) for rel in file if rel != "archivi/canti.pdf"}}
    with zipfile.ZipFile(destinazione, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in file + ["manifest.json"]:
            info = zipfile.ZipInfo(f"{CARTELLA_NEL_ZIP}/{rel}", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3                          # "Unix": senza questo macOS ignora i permessi
            # i permessi vanno scritti COMPLETI, con il tipo "file normale" (S_IFREG): senza, macOS non rende
            # eseguibili i file (errore "non hai i privilegi di accesso adeguati")
            info.external_attr = (stat.S_IFREG | (0o755 if _eseguibile(rel) else 0o644)) << 16
            dati = (json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8") if rel == "manifest.json"
                    else (RADICE / rel).read_bytes())
            z.writestr(info, dati)
    return len(file)


def main():
    ap = argparse.ArgumentParser(description="Prepara i pacchetti di una release.")
    ap.add_argument("--con-canti", action="store_true", help="prepara anche i pacchetti PRIVATI con il PDF dei canti")
    ap.add_argument("--uscita", default=str(RADICE / "dist"), help="cartella di destinazione")
    a = ap.parse_args()
    uscita = Path(a.uscita)
    uscita.mkdir(parents=True, exist_ok=True)
    v = versione()
    somme = []
    for sistema in ("Mac", "Windows"):
        nomi = [(f"Messa_Parrocchia_{v}_{sistema}.zip", False)]
        if a.con_canti:
            nomi.append((f"Messa_Parrocchia_{v}_{sistema}_con_canti.zip", True))
        for nome, con in nomi:
            n = crea(sistema, uscita / nome, con)
            somme.append(f"{impronta(uscita / nome)}  {nome}")
            privato = "   <-- PRIVATO: contiene il PDF dei canti, NON pubblicare" if con else ""
            print(f"{nome}: {n} file{privato}")
    (uscita / "SHA256SUMS.txt").write_text("\n".join(somme) + "\n", encoding="utf-8")
    print(f"Fatto: {uscita}")
    print(f"Per la release su GitHub: tag v{v}; allega i due zip SENZA '_con_canti'.")


if __name__ == "__main__":
    main()
