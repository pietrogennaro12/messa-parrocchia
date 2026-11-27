# -*- coding: utf-8 -*-
"""
Le sezioni della presentazione, NELL'ORDINE FISSO previsto dall'analisi funzionale.

fonte:
  sistema   = frontespizio
  scelta    = l'utente sceglie una variante (canto, testo fisso o frontespizio)
  cei       = testo preso dal sito della CEI (chiavi = nomi possibili del titolo sul sito)
  canto     = canto scelto dall'archivio PDF (slot = nome della select)
  preghiere = archivio PDF delle preghiere dei fedeli
  fisso     = testo fisso preso da testi/<nome>.txt

varianti (fonte "scelta"): tipo "canto" (slot = nome della select), "testo" (file in testi/)
o "frontespizio". La prima della lista e' quella proposta all'avvio, salvo "predefinita".
"""

_BASE = [
    {"id": "frontespizio",        "nome": "Frontespizio",            "fonte": "sistema"},
    {"id": "canto_iniziale",      "nome": "Canto iniziale",          "fonte": "canto", "slot": "iniziale"},
    {"id": "atto_penitenziale",   "nome": "Atto penitenziale",       "fonte": "scelta", "varianti": [
        {"id": "confesso", "etichetta": "Confesso", "tipo": "testo", "file": "confesso", "titolo": "Confesso"},
        {"id": "pieta", "etichetta": "Pietà di noi", "tipo": "testo", "file": "pieta_di_noi", "titolo": "Pietà di noi"},
        {"id": "frontespizio", "etichetta": "Solo frontespizio", "tipo": "frontespizio"},
    ]},
    {"id": "gloria",              "nome": "Gloria",                  "fonte": "scelta", "varianti": [
        {"id": "canto", "etichetta": "Canto", "tipo": "canto", "slot": "gloria"},
        {"id": "preghiera", "etichetta": "Preghiera (testo fisso)", "tipo": "testo", "file": "gloria"},
    ]},
    # La Colletta e' prevista dal punto RF-02 ma mancava nell'elenco RF-03: inserita qui.
    {"id": "colletta",            "nome": "Colletta",                "fonte": "cei",
     "chiavi": ["colletta"], "modo": "unica"},
    {"id": "prima_lettura",       "nome": "Prima lettura",           "fonte": "cei",
     "chiavi": ["prima lettura", "lettura"], "modo": "lettura"},
    {"id": "salmo",               "nome": "Salmo",                   "fonte": "cei",
     "chiavi": ["salmo responsoriale", "salmo"], "modo": "salmo"},
    {"id": "seconda_lettura",     "nome": "Seconda lettura",         "fonte": "cei",
     "chiavi": ["seconda lettura"], "modo": "lettura"},
    {"id": "alleluia",            "nome": "Alleluia",                "fonte": "canto", "slot": "alleluia"},
    {"id": "vangelo",             "nome": "Vangelo",                 "fonte": "cei",
     "chiavi": ["vangelo"], "modo": "lettura"},
    {"id": "professione_fede",    "nome": "Professione di fede",     "fonte": "scelta", "varianti": [
        {"id": "credo", "etichetta": "Credo", "tipo": "testo", "file": "credo", "titolo": "Credo"},
        {"id": "promesse", "etichetta": "Rinnovo delle promesse battesimali", "tipo": "testo",
         "file": "promesse_battesimali", "titolo": "Promesse battesimali"},
        {"id": "frontespizio", "etichetta": "Solo frontespizio", "tipo": "frontespizio"},
    ]},
    {"id": "preghiere_fedeli",    "nome": "Preghiere dei fedeli",    "fonte": "preghiere"},
    {"id": "canto_offertorio",    "nome": "Canto offertorio",        "fonte": "canto", "slot": "offertorio"},
    {"id": "sulle_offerte",       "nome": "Preghiera sulle offerte", "fonte": "cei",
     "chiavi": ["sulle offerte", "preghiera sulle offerte"], "modo": "unica"},
    {"id": "santo",               "nome": "Santo",                   "fonte": "canto", "slot": "santo"},
    {"id": "canto_pace",          "nome": "Canto della pace",        "fonte": "canto", "slot": "pace"},
    {"id": "agnello_di_dio",      "nome": "Agnello di Dio",          "fonte": "canto", "slot": "agnello"},
    {"id": "comunione_spirituale", "nome": "Comunione spirituale",   "fonte": "fisso",
     "file": "comunione_spirituale", "modo": "unica"},
    {"id": "canto_comunione",     "nome": "Canto di comunione",      "fonte": "canto", "slot": "comunione"},
    {"id": "dopo_comunione",      "nome": "Preghiera dopo la comunione", "fonte": "cei",
     "chiavi": ["dopo la comunione", "preghiera dopo la comunione"], "modo": "unica"},
    {"id": "canto_finale",        "nome": "Canto finale",            "fonte": "canto", "slot": "finale"},
]

# Il frontespizio viene ripetuto DOPO queste sezioni: (id della sezione, testo del nome).
# Ogni ripetizione e' una sezione come le altre: si puo' togliere dalla lista nell'interfaccia.
RIPETI_FRONTESPIZIO = [
    ("canto_iniziale", "dopo il canto iniziale"),
    ("atto_penitenziale", "dopo l’atto penitenziale"),
    ("gloria", "dopo il Gloria"),
    ("colletta", "dopo la colletta"),
    ("vangelo", "dopo il Vangelo"),
    ("professione_fede", "dopo la professione di fede"),
    ("preghiere_fedeli", "dopo le preghiere dei fedeli"),
    ("sulle_offerte", "dopo la preghiera sulle offerte"),
    ("santo", "dopo il Santo"),
    ("canto_pace", "dopo il canto della pace"),
    ("agnello_di_dio", "dopo l’Agnello di Dio"),
    ("comunione_spirituale", "dopo la comunione spirituale"),
    ("canto_comunione", "dopo il canto di comunione"),
    ("dopo_comunione", "dopo la preghiera dopo la comunione"),
    ("canto_finale", "dopo il canto finale"),
]


def _con_ripetizioni(base):
    dopo = {id_sez: nome for id_sez, nome in RIPETI_FRONTESPIZIO}
    risultato = []
    for sez in base:
        risultato.append(sez)
        if sez["id"] in dopo:
            risultato.append({"id": f"frontespizio_dopo_{sez['id']}",
                              "nome": f"Frontespizio ({dopo[sez['id']]})",
                              "fonte": "sistema", "nota": "frontespizio ripetuto"})
    return risultato


SEZIONI = _con_ripetizioni(_BASE)
PER_ID = {s["id"]: s for s in SEZIONI}
def _slot(sez):
    if sez["fonte"] == "canto":
        yield sez["slot"]
    for v in sez.get("varianti", []):
        if v["tipo"] == "canto":
            yield v["slot"]


SLOT_CANTI = [slot for sez in SEZIONI for slot in _slot(sez)]
