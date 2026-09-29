param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$searchRoot = Split-Path -Parent $PSScriptRoot
$searchPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$searchLogs = Join-Path $PSScriptRoot 'reports'
$searchUrl = 'http://127.0.0.1:8766'
if (-not (Test-Path -LiteralPath $searchPython)) { throw 'Run retrieval/setup.ps1 first.' }
$searchConfig = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config.json') -Encoding UTF8 -Raw | ConvertFrom-Json
$searchIndex = Join-Path $searchRoot $searchConfig.index
if (-not (Test-Path -LiteralPath (Join-Path $searchIndex 'manifest.json'))) { throw 'Build the retrieval index first. See retrieval/README.md.' }
[System.IO.Directory]::CreateDirectory($searchLogs) | Out-Null
$searchRunning = $false
$searchHealth = $null
try {
    $searchHealth = Invoke-RestMethod -Uri "$searchUrl/api/health" -TimeoutSec 2
} catch { }
if ($null -ne $searchHealth) {
    if ($searchHealth.application -ne 'kidet-retrieval') { throw 'Port 8766 is used by another service.' }
    $searchRunning = $true
}
if (-not $searchRunning) {
    $searchStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $searchProcess = Start-Process -FilePath $searchPython -ArgumentList @('-X','utf8','-m','retrieval.app') -WorkingDirectory $searchRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $searchLogs "server-$searchStamp.log") -RedirectStandardError (Join-Path $searchLogs "server-$searchStamp.err.log")
    for ($searchAttempt = 0; $searchAttempt -lt 120; $searchAttempt++) {
        Start-Sleep -Milliseconds 250
        if ($searchProcess.HasExited) { throw 'Search app could not start. Check retrieval/reports/server-*.err.log.' }
        try {
            $searchHealth = Invoke-RestMethod -Uri "$searchUrl/api/health" -TimeoutSec 1
            if ($searchHealth.application -eq 'kidet-retrieval') { $searchRunning = $true; break }
        } catch { }
    }
    if (-not $searchRunning) { throw 'Search app did not respond.' }
}
if (-not $NoBrowser) { Start-Process -FilePath "$searchUrl/" }
Write-Output "Search app: $searchUrl/"
