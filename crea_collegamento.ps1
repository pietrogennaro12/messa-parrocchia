# Crea il collegamento "Messa Parrocchia" sul Desktop e nella cartella del programma.
# (solo caratteri ASCII: PowerShell 5 legge i file senza BOM come ANSI)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw = Join-Path $dir '.venv\Scripts\pythonw.exe'
$ws  = New-Object -ComObject WScript.Shell

$cartelle = @($dir)
try { $cartelle += [Environment]::GetFolderPath('Desktop') } catch { }

foreach ($c in $cartelle) {
    try {
        $lnk = $ws.CreateShortcut((Join-Path $c 'Messa Parrocchia.lnk'))
        $lnk.TargetPath       = $pyw
        $lnk.Arguments        = '"' + (Join-Path $dir 'app.py') + '"'
        $lnk.WorkingDirectory = $dir
        $lnk.IconLocation     = (Join-Path $dir 'messa.ico')
        $lnk.Description      = 'Presentazione della Messa'
        $lnk.Save()
    } catch {
        Write-Host ('Non sono riuscito a creare il collegamento in ' + $c)
    }
}
