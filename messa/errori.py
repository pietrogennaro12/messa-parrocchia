# -*- coding: utf-8 -*-
"""Codici di errore (vedi capitolo 7 dell'analisi funzionale)."""

MESSAGGI = {
    "E01": "Connessione Internet assente. Controlla la rete e riprova.",
    "E02": "Il sito della CEI (chiesacattolica.it) non è raggiungibile in questo momento.",
    "E03": "Liturgia non trovata per la data selezionata. Verifica la data.",
    "E04": "L'archivio PDF dei canti non è disponibile.",
    "E05": "L'archivio PDF delle preghiere dei fedeli non è disponibile.",
    "E06": "Il file PDF non è leggibile.",
    "E07": "Canto non selezionato.",
    "E08": "Errore durante la creazione del file PowerPoint.",
    "E09": "Il file con il testo fisso non è stato trovato o è vuoto (cartella testi).",
    "E10": "Non riesco a controllare gli aggiornamenti.",
    "E11": "L'aggiornamento non è andato a buon fine: il programma è rimasto com'era.",
    "E99": "Errore imprevisto.",
}


class ErroreMessa(Exception):
    """Errore gestito: viene mostrato all'utente senza chiudere il programma."""

    def __init__(self, codice: str, dettaglio: str = ""):
        self.codice = codice
        self.dettaglio = dettaglio
        self.messaggio = MESSAGGI.get(codice, MESSAGGI["E99"])
        super().__init__(f"{codice}: {self.messaggio} {dettaglio}".strip())

    def come_dict(self):
        return {"codice": self.codice, "messaggio": self.messaggio, "dettaglio": self.dettaglio}
