# Registro delle versioni

Il numero di versione ha tre cifre: **maggiore.minore.correzione** (es. 1.2.0).
Ogni versione pubblicata su GitHub ha il suo "tag" `v1.2.0`.

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
