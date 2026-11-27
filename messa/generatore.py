# -*- coding: utf-8 -*-
"""Mette insieme liturgia, canti e preghiere nel piano delle slide (ordine fisso) e genera il .pptx."""
import datetime as dt
import re
from pathlib import Path

from . import config as cfgmod
from .errori import ErroreMessa, MESSAGGI
from .pptx_builder import costruisci
from .preghiere import analizza_preghiere
from .sezioni import SEZIONI
from .testi import carica_testo


def _avviso(codice, sezione, dettaglio=""):
    return {"codice": codice, "sezione": sezione, "messaggio": MESSAGGI[codice], "dettaglio": dettaglio}


def variante_scelta(sez, varianti):
    """La variante scelta per la sezione (o la prima della lista, se non indicata)."""
    elenco = sez["varianti"]
    scelta = (varianti or {}).get(sez["id"])
    return next((v for v in elenco if v["id"] == scelta), elenco[0])


def _canto(piano, avvisi, nome, id_canto, archivio_canti, errore_canti):
    if archivio_canti is None:
        avvisi.append(_avviso(errore_canti.codice if errore_canti else "E04", nome))
        piano.append({"tipo": "segnaposto", "titolo": nome})
        return
    if not id_canto:
        avvisi.append(_avviso("E07", nome))
        piano.append({"tipo": "segnaposto", "titolo": nome})
        return
    canto = archivio_canti.per_id(int(id_canto))
    if canto is None:
        avvisi.append(_avviso("E07", nome, "Il canto scelto non è più nell'archivio."))
        piano.append({"tipo": "segnaposto", "titolo": nome})
        return
    piano.append({"tipo": "canto", "titolo": nome, "titolo_canto": canto["titolo"],
                  "blocchi": canto["blocchi"]})


def _testo_fisso(piano, avvisi, nome, titolo_slide, file, modo):
    try:
        piano.append({"tipo": "testo", "titolo": titolo_slide, "blocchi": carica_testo(file), "modo": modo})
    except ErroreMessa as e:
        avvisi.append(_avviso(e.codice, nome, e.dettaglio))
        piano.append({"tipo": "segnaposto", "titolo": nome})


def usa_frontespizio(scelte, varianti):
    """True se qualche sezione scelta mostra il frontespizio (serve il nome della celebrazione)."""
    for sez in SEZIONI:
        if sez["id"] in scelte:
            if sez["fonte"] == "sistema":
                return True
            if sez["fonte"] == "scelta" and variante_scelta(sez, varianti)["tipo"] == "frontespizio":
                return True
    return False


def prepara_piano(data, scelte, canti_scelti, liturgia, archivio_canti, errore_canti, cfg, varianti=None,
                  canti_extra=None):
    """
    scelte: insieme degli id di sezione selezionati.
    canti_scelti: {slot: id_canto}.   varianti: {id_sezione: id_variante}.
    canti_extra: [{"id": id_canto, "dopo": id_sezione, "etichetta": str}] canti aggiuntivi, inseriti
    subito dopo la sezione indicata (anche se quella sezione non e' selezionata).
    Restituisce (piano, avvisi). Gli avvisi non bloccano: l'utente decide se procedere.
    """
    piano, avvisi = [], []
    frontespizio = {"tipo": "frontespizio", "data": data, "celebrazione": liturgia.nome,
                    "parrocchia": cfg["parrocchia"], "sottotitolo": liturgia.etichetta_formulario}
    extra = list(canti_extra or [])
    ids_sezioni = {sez["id"] for sez in SEZIONI}
    for sez in SEZIONI:                       # ordine FISSO, indipendente dall'ordine di selezione
        _sezione(piano, avvisi, sez, scelte, canti_scelti, varianti, liturgia, archivio_canti,
                 errore_canti, cfg, frontespizio)
        for e in extra:
            if e.get("dopo") == sez["id"]:
                _extra(piano, avvisi, e, archivio_canti, errore_canti)
    for e in extra:                           # posizione sconosciuta: in fondo
        if e.get("dopo") not in ids_sezioni:
            _extra(piano, avvisi, e, archivio_canti, errore_canti)
    return piano, avvisi


def _extra(piano, avvisi, e, archivio_canti, errore_canti):
    nome = (e.get("etichetta") or "").strip() or "Canto aggiuntivo"
    _canto(piano, avvisi, nome, e.get("id"), archivio_canti, errore_canti)


def _sezione(piano, avvisi, sez, scelte, canti_scelti, varianti, liturgia, archivio_canti,
             errore_canti, cfg, frontespizio):
    """Aggiunge al piano le slide di UNA sezione (se e' stata scelta)."""
    if sez["id"] not in scelte:
        return
    fonte, nome = sez["fonte"], sez["nome"]

    if fonte == "sistema":
        piano.append(dict(frontespizio))
    elif fonte == "scelta":
        v = variante_scelta(sez, varianti)
        if v["tipo"] == "frontespizio":
            piano.append(dict(frontespizio))
        elif v["tipo"] == "canto":
            _canto(piano, avvisi, nome, canti_scelti.get(v["slot"]), archivio_canti, errore_canti)
        else:
            titolo = f"{nome} · {v['titolo']}" if v.get("titolo") else nome
            _testo_fisso(piano, avvisi, nome, titolo, v["file"], "fisso")
    elif fonte == "cei":
        blocchi = liturgia.trova(sez["chiavi"])
        if not blocchi:
            avvisi.append({"codice": "INFO", "sezione": nome,
                           "messaggio": f"«{nome}» non è prevista in questa celebrazione: saltata.",
                           "dettaglio": ""})
            return
        piano.append({"tipo": "testo", "titolo": nome, "blocchi": blocchi, "modo": sez["modo"]})
    elif fonte == "fisso":
        _testo_fisso(piano, avvisi, nome, nome, sez["file"], sez["modo"])
    elif fonte == "preghiere":
        try:
            blocchi, info = analizza_preghiere(cfgmod.percorso(cfg["pdf_preghiere"]), cfg.get("pagine_preghiere", ""))
            piano.append({"tipo": "testo", "titolo": nome, "blocchi": blocchi, "modo": "preghiere",
                          "risposta": cfg.get("risposta_preghiere", "Ascoltaci, o Signore")})
            if info["riparati"]:
                avvisi.append({"codice": "INFO", "sezione": nome, "dettaglio": "",
                               "messaggio": f"Preghiere dei fedeli: nel PDF {info['riparati']} gruppi di lettere («ti», «tt», «tti») "
                                            "erano scritti con simboli strani (<, @, :): li ho corretti. Dai comunque un'occhiata al testo."})
            if info["sospetti"]:
                avvisi.append({"codice": "INFO", "sezione": nome, "dettaglio": "",
                               "messaggio": f"Preghiere dei fedeli: nel PDF ci sono {info['sospetti']} caratteri insoliti "
                                            "che non so correggere: controlla il testo."})
        except ErroreMessa as e:
            avvisi.append(_avviso(e.codice, nome, e.dettaglio))
            piano.append({"tipo": "segnaposto", "titolo": nome})
    elif fonte == "canto":
        _canto(piano, avvisi, nome, canti_scelti.get(sez["slot"]), archivio_canti, errore_canti)


def nome_file_valido(nome: str, data: dt.date) -> str:
    nome = (nome or "").strip() or f"Messa_{data.isoformat()}"
    nome = re.sub(r'[\\/:*?"<>|]+', "_", nome)
    return nome if nome.lower().endswith(".pptx") else nome + ".pptx"


def genera(piano, cfg, colore_hex, cartella: Path, nome_file: str, sovrascrivi=False):
    cartella = Path(cartella).expanduser()
    try:
        cartella.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ErroreMessa("E08", f"Non riesco a usare la cartella {cartella}: {e}")
    destinazione = cartella / nome_file
    if destinazione.exists() and not sovrascrivi:
        return None, destinazione              # il chiamante chiede conferma
    n = costruisci(piano, cfg["font"], colore_hex, destinazione)
    return n, destinazione
