# Registro delle versioni

Il numero di versione ha tre cifre: **maggiore.minore.correzione** (es. 1.2.0).
Ogni versione pubblicata su GitHub ha il suo "tag" `v1.2.0`.

## 1.3.0 — frontespizio rinnovato, preghiere dei fedeli migliorate

- **Frontespizio**: la ricorrenza (es. "XXXIII Domenica del Tempo Ordinario") è il titolo principale, in grassetto e nel
  **colore liturgico** del giorno; la data è il sottotitolo.
- **Frontespizio ripetuto in 15 punti**: dopo canto iniziale, atto penitenziale, Gloria, colletta, Vangelo, professione di
  fede, preghiere dei fedeli, preghiera sulle offerte, Santo, canto della pace, Agnello di Dio, comunione spirituale,
  canto di comunione, preghiera dopo la comunione e canto finale. Ognuno si può togliere dalla lista.
- **Preghiere dei fedeli**: prima slide con il solo titolo; poi **una preghiera per slide**, con "Ascoltaci, o Signore" in
  giallo e grassetto (come il ritornello del salmo) alla fine di ogni intenzione. Non viene aggiunto all'invito iniziale né
  alla preghiera conclusiva. Il testo si cambia con `risposta_preghiere` in `config.json`.
- **Preghiere dei fedeli, PDF con simboli strani**: sistemato il difetto per cui «ti», «tt», «tti» comparivano come `<`, `@`,
  `:` ("noi < preghiamo", "perme@e", "tu: i fratelli"). Il programma riconosce quei simboli e rimette le lettere giuste,
  e lo segnala. Anche le ligature vere (ﬁ, ﬃ…) diventano lettere normali. Il titolo del documento non è più una slide.
- Piccole correzioni alle maiuscole del titolo ("Tutti i Fedeli Defunti").

## 1.2.1 — icona Mac copiabile

- L'icona "Messa Parrocchia" copiata fuori dalla cartella del programma (per esempio sulla Scrivania) ora funziona:
  il programma ricorda dove sta. Prima compariva "Non riesco ad avviare il programma".
  Dopo l'aggiornamento basta aprire una volta l'icona che sta dentro la cartella, poi rifare la copia
  (le copie fatte in precedenza hanno il vecchio file di avvio).

## 1.2.0 — testata con logo e chiesa

- In cima alla pagina compaiono il logo della parrocchia e una foto della chiesa, accanto al titolo (la foto si nasconde
  da sola sugli schermi stretti). Le immagini sono in `web/img/`: per cambiarle basta sostituire i due file,
  tenendo gli stessi nomi (`logo-parrocchia.jpg`, `chiesa.jpg`). Gli aggiornamenti non le sovrascrivono.

## 1.1.1 — correzione dei pacchetti per Mac

- I pacchetti `.zip` ora scrivono i permessi di esecuzione nel formato che macOS riconosce: `Installa.command` e l'app
  si aprono con il doppio clic (nella 1.1.0 comparivano "non hai i privilegi di accesso adeguati").
- Guida: cosa fare se un file `.command` non si apre.

## 1.1.0 — aggiornamento dal programma

- Pulsante **Aggiorna versione**: controlla su GitHub se c'è una versione più nuova, la scarica, la verifica, ne conserva
  una copia di sicurezza e si riavvia. Non tocca PDF, impostazioni e testi già presenti.
- Avviso automatico all'avvio quando è disponibile una versione nuova (si può disattivare).
- **Torna alla versione precedente**, se un aggiornamento non convince.
- Strumento per preparare i pacchetti di ogni versione (`strumenti/crea_pacchetti.py`).

## 1.0.0 — prima versione stabile

- Presentazione della Messa creata dal sito della CEI: colletta, letture (con slide di annuncio), salmo con ritornello,
  Vangelo, preghiera sulle offerte, dopo la comunione; alternative ("Oppure:") e forma breve su slide separate.
- Canti scelti da un PDF locale; canti aggiuntivi inseribili dopo qualsiasi parte.
- Testi fissi modificabili (Gloria, Credo, Confesso, Pietà di noi, promesse battesimali, comunione spirituale).
- Scelte: Gloria (canto o preghiera), Atto penitenziale, Professione di fede; più messe nello stesso giorno (formulari).
- Frontespizio ripetuto in sei punti della Messa; nome della celebrazione modificabile.
- Finestra propria (senza browser), con riserva su Edge/Chrome e sul browser.
- Versioni per Mac (anche chip Apple) e Windows.
