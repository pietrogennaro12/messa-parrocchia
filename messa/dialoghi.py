# -*- coding: utf-8 -*-
"""
Finestre di scelta file/cartella e apertura della cartella del file creato.

  macOS    -> finestre native (osascript)
  Windows  -> finestre native (PowerShell + Windows Forms): non serve nessun componente in piu'
  altri    -> Tk, se disponibile

Tutto senza aprire il Terminale o finestre nere.
"""
import os
import subprocess
import sys
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000        # Windows: niente finestra nera durante l'esecuzione


def gestore_file() -> str:
    """Nome del programma che mostra i file (per il testo del pulsante)."""
    if sys.platform == "darwin":
        return "Finder"
    if sys.platform.startswith("win"):
        return "Esplora file"
    return "gestore file"


# ----------------------------------------------------------------------------
# macOS
# ----------------------------------------------------------------------------

def _osascript(corpo: str):
    script = f'tell application "System Events"\nactivate\n{corpo}\nend tell'
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:          # annullato dall'utente (errore -128) o altro
        return None
    return r.stdout.strip() or None


# ----------------------------------------------------------------------------
# Windows
# ----------------------------------------------------------------------------

_PS_INIZIO = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    "Add-Type -AssemblyName System.Windows.Forms;"
    "$o=New-Object System.Windows.Forms.Form;"           # finestra "madre" invisibile, sempre in primo piano
    "$o.TopMost=$true;$o.ShowInTaskbar=$false;$o.Opacity=0;$o.StartPosition='CenterScreen';$o.Show();"
)


def _powershell(corpo: str):
    """Esegue uno script PowerShell (finestre di dialogo) e restituisce il testo stampato, o None."""
    comando = ["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", _PS_INIZIO + corpo]
    r = subprocess.run(comando, capture_output=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise OSError("PowerShell non disponibile o in errore")
    return r.stdout.decode("utf-8", errors="replace").strip() or None


def _windows(tipo: str, messaggio: str):
    messaggio = messaggio.replace("'", "")               # nello script PowerShell si usano apici singoli
    if tipo == "file":
        corpo = ("$d=New-Object System.Windows.Forms.OpenFileDialog;"
                 f"$d.Title='{messaggio}';$d.Filter='File PDF (*.pdf)|*.pdf|Tutti i file (*.*)|*.*';"
                 "if($d.ShowDialog($o) -eq 'OK'){$d.FileName}")
    else:
        corpo = ("$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
                 f"$d.Description='{messaggio}';$d.ShowNewFolderButton=$true;"
                 "if($d.ShowDialog($o) -eq 'OK'){$d.SelectedPath}")
    try:
        return _powershell(corpo)
    except Exception:
        return _tk(tipo)


# ----------------------------------------------------------------------------
# Altri sistemi (e riserva)
# ----------------------------------------------------------------------------

def _python_con_console():
    """Con l'avvio 'senza finestre' l'eseguibile e' pythonw.exe, che non restituisce testo: uso python.exe."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return str(exe.with_name("python.exe"))
    return str(exe)


def _tk(tipo):
    codice = (
        "import tkinter as tk\nfrom tkinter import filedialog\n"
        "r=tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
        + ("print(filedialog.askopenfilename(filetypes=[('PDF','*.pdf')]))" if tipo == "file"
           else "print(filedialog.askdirectory())")
    )
    try:
        extra = {"creationflags": CREATE_NO_WINDOW} if sys.platform.startswith("win") else {}
        r = subprocess.run([_python_con_console(), "-c", codice], capture_output=True, text=True, **extra)
        return r.stdout.strip() or None
    except Exception:
        return None


# ----------------------------------------------------------------------------
# interfaccia usata dal programma
# ----------------------------------------------------------------------------

def scegli_pdf(messaggio="Scegli il file PDF"):
    if sys.platform == "darwin":
        return _osascript(f'POSIX path of (choose file with prompt "{messaggio}" of type {{"com.adobe.pdf"}})')
    if sys.platform.startswith("win"):
        return _windows("file", messaggio)
    return _tk("file")


def scegli_cartella(messaggio="Scegli la cartella"):
    if sys.platform == "darwin":
        return _osascript(f'POSIX path of (choose folder with prompt "{messaggio}")')
    if sys.platform.startswith("win"):
        return _windows("cartella", messaggio)
    return _tk("cartella")


def mostra_nel_finder(percorso: str):
    """Apre la cartella del file e lo seleziona (Finder su Mac, Esplora file su Windows)."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", percorso])
        elif sys.platform.startswith("win"):
            # Esplora file vuole "/select,<percorso>" in un solo argomento, con le barre rovesciate
            subprocess.run(["explorer", "/select," + os.path.normpath(percorso)])
        else:
            subprocess.run(["xdg-open", str(Path(percorso).parent)])
    except Exception:
        pass
