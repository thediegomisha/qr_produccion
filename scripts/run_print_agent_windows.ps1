$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

function Import-EnvFile($path) {
    if (-not (Test-Path $path)) { return }
    Get-Content $path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $parts = $line -split "=", 2
        if ($parts.Count -ne 2) { return }
        $key = $parts[0].Trim()
        $val = $parts[1].Trim().Trim('"')
        if ($key) { $env:$key = $val }
    }
}

Import-EnvFile (Join-Path $root ".env")
Import-EnvFile (Join-Path $root "backend/.env")

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$env:PYTHONPATH = (Join-Path $root "backend")

$agentToken = $env:AGENT_TOKEN
if (-not $agentToken) { $agentToken = $env:PRINT_AGENT_TOKEN }
if (-not $agentToken) { $agentToken = "change-me" }

$agentId = $env:AGENT_ID
if (-not $agentId) { $agentId = "agent-001" }

$agentHost = $env:AGENT_HOST
if (-not $agentHost) { $agentHost = "0.0.0.0" }

$agentPort = $env:AGENT_PORT
if (-not $agentPort) { $agentPort = "5000" }

$env:AGENT_TOKEN = $agentToken
$env:AGENT_ID = $agentId

Write-Host "Print Agent -> http://$agentHost`:$agentPort"
Write-Host "AGENT_ID=$agentId"
Write-Host "Health check: curl http://127.0.0.1:$agentPort/health"

& $python -m uvicorn app.print_agent.agent_app:app --host $agentHost --port $agentPort
