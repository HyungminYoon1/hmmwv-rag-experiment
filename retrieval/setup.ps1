$ErrorActionPreference = 'Stop'
$searchProject = Split-Path -Parent $PSScriptRoot
$searchBasePython = Join-Path $searchProject 'preprocessing\.venv\Scripts\python.exe'
$searchPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $searchBasePython)) { throw 'Python 3.11 from the preprocessing environment is required.' }
if (-not (Test-Path -LiteralPath $searchPython)) {
    & $searchBasePython -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
& $searchPython -m pip install --disable-pip-version-check 'torch==2.8.0+cpu' --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed.' }
& $searchPython -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $searchPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency compatibility check failed.' }
