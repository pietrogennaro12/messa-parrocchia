# Messa Parrocchia – generatore di presentazioni liturgiche

Crea il PowerPoint della Messa: sceglie la data, scarica i testi dal sito della CEI,
inserisce i canti presi dal vostro PDF e salva il file `.pptx` pronto per la TV.

## Installazione (una volta sola)

Il pacchetto esiste in due versioni: **Mac** e **Windows**. Il programma è lo stesso.

### Su Mac

1. Installa **Python 3** da <https://www.python.org/downloads/macos/> (se non l'hai già).
2. Scompatta la cartella dove vuoi (es. Applicazioni o Documenti).
3. Fai doppio clic su **Installa.command**.
   La prima volta macOS potrebbe rifiutarsi: fai *tasto destro → Apri → Apri*.
   Serve Internet; ci vogliono pochi minuti.
4. Da ora in poi apri **Messa Parrocchia** (l'icona nella cartella; puoi trascinarla nel Dock). Finché il programma è aperto,
   l'icona resta nel Dock; chiudendo la finestra si chiude anche il programma.
   Se macOS avvisa che l'app non è verificata: *tasto destro → Apri* (solo la prima volta).

**Se compare "Impossibile eseguire il file … non hai i privilegi di accesso adeguati"**: il file è arrivato senza il permesso
di esecuzione. Apri **Terminale**, scrivi `bash ` (con uno spazio dopo), trascina nella finestra il file `Installa.command`
e premi Invio. L'installazione parte e rende eseguibili anche gli altri file. (Se sei già dentro una shell `bash`,
scrivi comunque `bash` davanti al percorso: senza, il Terminale dà di nuovo "Permission denied".)

### Su Windows (10 e 11)

1. Installa **Python 3** da <https://www.python.org/downloads/windows/> (se non l'hai già).
   Nella **prima schermata** dell'installazione spunta **"Add python.exe to PATH"**.
2. **Prima di scompattare**: tasto destro sul file `.zip` → *Proprietà* → spunta **Annulla blocco** (o *Sblocca*) → OK.
   Poi tasto destro → *Estrai tutto…* e scegli una cartella (es. Documenti). Non usare la cartella Download.
3. Fai doppio clic su **Installa.bat**. Se compare *"Windows ha protetto il PC"*:
   *Ulteriori informazioni → Esegui comunque*. Serve Internet; ci vogliono pochi minuti.
4. Alla fine trovi sul Desktop l'icona **Messa Parrocchia** (croce dorata su fondo blu).
   In alternativa: doppio clic su `Messa Parrocchia.vbs` nella cartella del programma.

Non serve mai il Terminale (né la "finestra nera") dopo l'installazione.

## Su Mac: se l'icona "Messa Parrocchia" non si apre

1. **Prova l'avvio di emergenza**: doppio clic su **Avvia con Terminale.command**. Si apre una finestra di Terminale:
   lasciala aperta (puoi ridurla a icona), perché chiuderla chiude il programma.
2. **Guarda il diario**: apri la cartella `Libreria/Logs/Messa Parrocchia` della tua cartella Home e leggi `avvio.log`
   (da Finder: menu *Vai → Vai alla cartella…* e scrivi `~/Library/Logs/Messa Parrocchia`).
   - Se **non esiste** (o non c'è una riga nuova dopo il doppio clic), l'icona non è nemmeno partita: di solito è un
     blocco di sicurezza di macOS. Prova *tasto destro sull'icona → Apri*, oppure in *Impostazioni di Sistema → Privacy e
     sicurezza* cerca il messaggio su "Messa Parrocchia" e premi *Apri comunque*.
   - Se **esiste**, l'ultima riga dice cosa non va (e comparirà anche un avviso a schermo).
3. Rifai doppio clic su `Installa.command`. Se non basta, prova a spostare la cartella in **Applicazioni** e ripeti.

Nota per i Mac con chip Apple (M1, M2…): l'icona avvia il programma in modo nativo. Se nel diario compare
*"incompatible architecture"*, i componenti sono stati installati per un tipo di Mac diverso da quello in uso:
rifai `Installa.command`.

## La finestra del programma

Il programma si apre in una **finestra propria** (con la sua icona), senza barra degli indirizzi e senza schede.
Si chiude chiudendo la finestra (oppure con "Chiudi il programma" in fondo).

Per aprirla il programma prova tre strade, in ordine, e usa la prima che funziona:
1. **finestra nativa** (componente *pywebview*, installato da `Installa`): su Mac usa il motore di Safari, su Windows quello di Edge;
2. una **finestra "senza barra" di Edge, Chrome o Brave**, se sono installati;
3. il **browser** di sempre (in questo caso il programma si chiude da solo quando chiudi la scheda).

Se la finestra nativa non c'era e vuoi averla (per esempio hai installato una versione precedente), basta rifare
doppio clic su `Installa.command` (Mac) o `Installa.bat` (Windows): non cancella nulla di tuo.
Per forzare il browser: `python app.py --browser`.

## Aggiornare il programma

In fondo alla pagina c'è il pulsante **Aggiorna versione**. Il programma controlla su GitHub se esiste una versione più
nuova; se sì, mostra le novità e, con "Aggiorna ora", scarica l'aggiornamento, ne verifica l'integrità, conserva una
copia di sicurezza, sostituisce i file e si riavvia da solo.

- **Non vengono mai toccati**: i PDF in `archivi/`, le impostazioni (`config.json`), la cartella `.venv`, il diario e i
  **testi già presenti** in `testi/` (potresti averli modificati; gli aggiornamenti aggiungono solo testi nuovi).
- **Avviso automatico**: all'avvio, se c'è una versione nuova, compare un avviso in alto (senza Internet non dice nulla).
  Si può disattivare con `"controllo_automatico": false` in `config.json`.
- **Torna alla versione precedente**: dopo un aggiornamento compare questo pulsante; riporta il programma com'era.
- **Prima volta**: se l'indirizzo del repository non è ancora impostato, il programma lo chiede (forma `utente/nome`)
  e lo ricorda. Per darlo già pronto a tutti, scrivilo in `messa/config.py`, alla voce `repository_aggiornamenti`.

## Per chi pubblica le versioni

1. Cambia il numero in `messa/__init__.py` (es. `1.2.0`) e scrivi le novità in `CHANGELOG.md`.
2. Esegui `python3 strumenti/crea_pacchetti.py`: crea in `dist/` i pacchetti `Messa_Parrocchia_<versione>_Mac.zip` e
   `..._Windows.zip` (senza il PDF dei canti) e `SHA256SUMS.txt`. Con `--con-canti` prepara anche i pacchetti
   **privati** per l'installazione iniziale (`..._con_canti.zip`): non vanno mai pubblicati.
3. Su GitHub: carica il codice (GitHub Desktop: *Commit* e *Push*), poi *Releases → Create a new release*, tag `v1.2.0`,
   nelle note scrivi le novità (le vedranno gli utenti) e allega i **due zip pubblici**. Il nome deve contenere
   `Mac` o `Windows`. Il repository deve essere pubblico.
4. Gli utenti vedranno l'avviso al successivo avvio, o premendo **Aggiorna versione**.

Nota: chi ha ancora la 1.0.0 deve installare a mano la 1.1.0 una volta; da lì in poi basta il pulsante.

## Uso

1. Scegli la **data** (all'apertura propone la prossima domenica): la liturgia viene caricata da sola.
2. Spunta le **parti** da inserire e scegli i **canti** dai menu a tendina.
   Le parti non previste in quel giorno (es. Seconda lettura nei feriali) sono disattivate.
3. Controlla la **cartella** e il **nome del file**, poi premi **Crea il PowerPoint**.

L'ordine delle slide è sempre quello della lista, qualunque sia l'ordine con cui spunti le voci.
Se manca un canto, il programma avvisa e, se confermi, inserisce una slide con il solo titolo.

**Nome della celebrazione**: viene letto dal sito (es. "Natale del Signore") e compare sotto la data. Se è sbagliato
o vuoto, basta cliccarci sopra e scriverlo a mano: quello che scrivi finisce sul frontespizio così com'è.

**Alternative nelle letture** ("Oppure:"): ogni alternativa ha la sua slide di annuncio e le sue slide di testo
(titolo "PRIMA LETTURA · OPPURE"); lo stesso vale per la forma breve.

**Più messe nello stesso giorno** (es. Natale: vigilia, notte, aurora, giorno): sotto la data compare un menu
per scegliere quale usare; le parti disponibili si aggiornano e il frontespizio riporta il nome della messa.
Se il sito non indica un nome chiaro, i formulari si chiamano "Formulario 1", "Formulario 2"…

**Canti aggiuntivi**: sotto la lista, "＋ Aggiungi un canto". Si sceglie il canto, un nome facoltativo
(es. "Canto alla Madonna") e **dopo quale parte** inserirlo. Se ne possono aggiungere quanti si vuole, anche nello stesso
punto (restano nell'ordine in cui sono scritti); con la ✕ si tolgono.

## Archivi PDF

- `archivi/canti.pdf` – il PDF dei canti: una pagina per canto, titolo in prima riga.
  La prima lettura dura qualche secondo, poi viene ricordata. Per cambiare PDF basta sostituire il file.
- `archivi/preghiere_fedeli.pdf` – le preghiere dei fedeli (da aggiungere). Se il PDF contiene più
  celebrazioni, indica le pagine da usare (es. `3-4`) nella sezione "Archivi PDF".

## Cosa produce la presentazione

- Formato 16:9, sfondo nero, testo bianco, barra in alto del **colore liturgico** del giorno.
- **Letture e Vangelo**: prima una slide di **annuncio** ("PRIMA LETTURA – Dal libro della Sapienza – Sap 6,12-16"),
  poi il testo diviso **per paragrafi** in slide di peso simile (50 punti). Se c'è la *forma breve*,
  ha il suo annuncio e le sue slide.
- **Salmo**: slide di annuncio con il ritornello, poi **una strofa per slide** con il ritornello (R.) dopo ogni strofa.
- **Preghiere** (colletta, offerte, dopo la comunione, comunione spirituale): **una slide** ciascuna, con il carattere
  più grande che ci sta. Se ci sono alternative ("Oppure:"), ognuna ha la **sua slide** (titolo "COLLETTA · OPPURE").
- **Canti**: una strofa per slide, ogni slide con il carattere più grande possibile; ritornelli in grassetto, testo centrato.
- **Frontespizio ripetuto**: oltre che all'inizio, ricompare dopo il canto iniziale, dopo il Vangelo, dopo la preghiera
  sulle offerte, dopo il Santo, dopo l'Agnello di Dio e dopo il canto di comunione. Sono voci della lista come le altre:
  per non averne una basta togliere la spunta.
- **Parti con scelta** (menu a tendina accanto alla voce):
  - **Atto penitenziale**: *Confesso*, *Pietà di noi* oppure solo il frontespizio.
  - **Gloria**: *Canto* (scelto dal PDF) oppure *Preghiera* (testo fisso).
  - **Professione di fede**: *Credo*, *Rinnovo delle promesse battesimali* oppure solo il frontespizio.
- **Testi fissi** (Gloria, Credo, Confesso, Pietà di noi, promesse battesimali, comunione spirituale):
  strofe sempre intere, più strofe sulla stessa slide quando il carattere resta grande;
  le risposte dell'assemblea sono in grassetto.

## Modificare i testi fissi

Sono semplici file di testo nella cartella `testi/` (si aprono con TextEdit, formato "solo testo"):
`gloria.txt`, `credo.txt`, `promesse_battesimali.txt`, `confesso.txt`, `pieta_di_noi.txt`, `comunione_spirituale.txt`.
Una riga vuota separa due strofe (una strofa non viene mai divisa tra due slide), una riga tra `**doppi asterischi**`
compare in grassetto, le righe che iniziano con `#` sono commenti. Se un file manca compare l'errore E09.

## Personalizzazione (`config.json`, si crea al primo salvataggio)

| Voce | Significato |
|---|---|
| `parrocchia` | scritta sul frontespizio |
| `font` | carattere (`Aptos`; se non c'è sul Mac usa `Calibri` o `Arial`) |
| `canti_predefiniti` | canti proposti all'avvio, es. `{"agnello": "AGNELLO DI DIO"}` |
| `cartella_output` | cartella di salvataggio (predefinita: Documenti\\Messe) |

Le grandezze del carattere e i colori sono in `messa/pptx_builder.py` (in cima al file): per esempio
`DIM_LETTURE = 50` (letture e Vangelo; abbassalo a 46 per avere meno slide) e `DIM_MASSIMA`/`DIM_MINIMA` per preghiere e canti.

## In caso di problemi

I messaggi del programma hanno un codice (E01…E09, vedi analisi funzionale).
Se il file PowerPoint è aperto in PowerPoint, chiudilo prima di crearlo di nuovo con lo stesso nome (Windows lo blocca).
I dettagli tecnici sono nel file `log.txt` nella cartella del programma.

## Per chi sviluppa

```
app.py                 avvio (server locale + browser)
messa/liturgia.py      sito CEI: scarico, controllo data, lettura pagina
messa/canti.py         archivio canti (PDF)         messa/preghiere.py   preghiere dei fedeli (PDF)
messa/testi.py         testi fissi (cartella testi/)
messa/impaginazione.py quanto testo entra in una slide
messa/pptx_builder.py  costruzione del .pptx        messa/generatore.py  ordine fisso e controlli
messa/server.py        interfaccia (API locale)     web/index.html       interfaccia grafica
messa/finestra.py      apertura della finestra (pywebview → Edge/Chrome → browser)
tests/                 python -m unittest discover -s tests -v
```
Il codice è lo stesso su Mac e Windows; cambiano solo l'installatore/avvio (`Installa.command` e `Messa Parrocchia.app`
oppure `Installa.bat`, `crea_collegamento.ps1` e `Messa Parrocchia.vbs`) e le finestre "Scegli…" (`messa/dialoghi.py`).
