$ErrorActionPreference = 'Stop'
$experimentDir = $PSScriptRoot
$ollamaExe = (Get-Command ollama -ErrorAction Stop).Source
$settings = @{
    OLLAMA_HOST = '127.0.0.1:11435'
    OLLAMA_MODELS = (Join-Path $experimentDir 'models/ollama')
    OLLAMA_NUM_PARALLEL = '1'
    OLLAMA_MAX_LOADED_MODELS = '1'
    OLLAMA_NO_CLOUD = '1'
    OLLAMA_CONTEXT_LENGTH = '4096'
}
$saved = @{}
New-Item -ItemType Directory -Force -Path (Join-Path $experimentDir 'reports') | Out-Null
try {
    foreach ($name in $settings.Keys) {
        $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $settings[$name], 'Process')
    }
    $server = Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $experimentDir 'reports/ollama-stdout.log') -RedirectStandardError (Join-Path $experimentDir 'reports/ollama-stderr.log')
    [IO.File]::WriteAllText((Join-Path $experimentDir 'reports/ollama-pid.txt'), [string]$server.Id, [Text.UTF8Encoding]::new($false))
    Write-Output "Experiment Ollama server PID: $($server.Id), address: 127.0.0.1:11435"
} finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
}
