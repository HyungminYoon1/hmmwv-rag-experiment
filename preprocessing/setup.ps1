param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$projectPreprocessing = $PSScriptRoot
$projectPython = Join-Path $projectPreprocessing ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $projectPython)) {
    & $Python -m venv (Join-Path $projectPreprocessing ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create the isolated Python environment." }
}
& $projectPython -X utf8 -m pip install -r (Join-Path $projectPreprocessing "requirements.lock.txt")
if ($LASTEXITCODE -ne 0) { throw "Package installation failed." }
& $projectPython -X utf8 (Join-Path $projectPreprocessing "prepare_assets.py")
if ($LASTEXITCODE -ne 0) { throw "Asset preparation failed." }
Write-Output "Ready. Run preprocess.py with an empty output directory."
