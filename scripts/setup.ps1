param([ValidateSet('view', 'full')][string]$Mode = 'view')
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Program (exit $LASTEXITCODE)" }
}

$pythonVersion = & py -3.11 -c 'import platform; print(platform.python_version())'
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 (64-bit) first.' }
if ($Mode -eq 'full' -and $pythonVersion.Trim() -ne '3.11.9') {
    throw 'The frozen index records Python 3.11.9. Use that version for this reference workflow.'
}

Push-Location -LiteralPath $packageRoot
try {
    if ($Mode -eq 'view') {
        $viewPython = Join-Path $packageRoot '.venv-view/Scripts/python.exe'
        if (-not (Test-Path -LiteralPath $viewPython)) {
            Invoke-Checked 'py' @('-3.11', '-m', 'venv', '.venv-view')
        }
        Invoke-Checked $viewPython @('-m', 'pip', 'install', '-r', 'scripts/requirements-view.txt')
        Invoke-Checked $viewPython @('-m', 'pip', 'check')
        Write-Output 'Ready: .\.venv-view\Scripts\python.exe -X utf8 scripts\serve_results.py'
        return
    }
    foreach ($directory in @('preprocessing/.venv', 'retrieval/.venv', 'experiment/evaluation/.venv')) {
        $python = Join-Path $packageRoot ($directory + '/Scripts/python.exe')
        if (-not (Test-Path -LiteralPath $python)) {
            Invoke-Checked 'py' @('-3.11', '-m', 'venv', $directory)
        }
    }
    Invoke-Checked '.\preprocessing\.venv\Scripts\python.exe' @('-m', 'pip', 'install', '-r', 'preprocessing/requirements.lock.txt')
    Invoke-Checked '.\retrieval\.venv\Scripts\python.exe' @('-m', 'pip', 'install', 'torch==2.8.0+cpu', '--index-url', 'https://download.pytorch.org/whl/cpu')
    Invoke-Checked '.\retrieval\.venv\Scripts\python.exe' @('-m', 'pip', 'install', '-r', 'retrieval/requirements.lock.txt')
    Invoke-Checked '.\experiment\evaluation\.venv\Scripts\python.exe' @('-m', 'pip', 'install', '-r', 'experiment/evaluation/requirements.lock.txt')
    foreach ($directory in @('preprocessing/.venv', 'retrieval/.venv', 'experiment/evaluation/.venv')) {
        Invoke-Checked (Join-Path $packageRoot ($directory + '/Scripts/python.exe')) @('-m', 'pip', 'check')
    }
    Write-Output 'Environments ready. Restore artifacts and download locked models next.'
} finally {
    Pop-Location
}
