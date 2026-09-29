param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$corpusBase = $PSScriptRoot
$corpusPython = Join-Path $corpusBase '.venv\Scripts\python.exe'
$corpusApp = Join-Path $corpusBase 'corpus\app.py'
$corpusLogs = Join-Path $corpusBase 'corpus\reports'
if (-not (Test-Path -LiteralPath $corpusPython)) { throw 'Run preprocessing setup.ps1 first.' }
[System.IO.Directory]::CreateDirectory($corpusLogs) | Out-Null
$corpusPort = 8765
$corpusUrl = "http://127.0.0.1:$corpusPort"
$corpusRunning = $false
try {
    $corpusHealth = Invoke-RestMethod -Uri "$corpusUrl/api/health" -TimeoutSec 2
    $corpusRunning = $corpusHealth.application -eq 'kidet-corpus'
} catch { }
if (-not $corpusRunning) {
    $corpusStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $corpusArgs = @('-X', 'utf8', ('"' + $corpusApp + '"'), '--port', "$corpusPort")
    $corpusProcess = Start-Process -FilePath $corpusPython -ArgumentList $corpusArgs -WorkingDirectory $corpusBase -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $corpusLogs "server-$corpusStamp.log") -RedirectStandardError (Join-Path $corpusLogs "server-$corpusStamp.err.log")
    for ($corpusAttempt = 0; $corpusAttempt -lt 30; $corpusAttempt++) {
        Start-Sleep -Milliseconds 200
        if ($corpusProcess.HasExited) { throw 'The corpus app could not start. Check corpus/reports/server-*.err.log.' }
        try {
            $corpusHealth = Invoke-RestMethod -Uri "$corpusUrl/api/health" -TimeoutSec 1
            if ($corpusHealth.application -eq 'kidet-corpus') { $corpusRunning = $true; break }
        } catch { }
    }
    if (-not $corpusRunning) { throw 'The corpus app did not respond.' }
}
if (-not $NoBrowser) { Start-Process -FilePath "$corpusUrl/" }
Write-Output "Corpus app: $corpusUrl/"
