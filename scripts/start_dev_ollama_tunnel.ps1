param(
    [string]$TunnelToken = $env:CLOUDFLARE_TUNNEL_TOKEN
)

$ErrorActionPreference = "Stop"

if (-not $TunnelToken) {
    throw "Set CLOUDFLARE_TUNNEL_TOKEN or pass -TunnelToken before starting the tunnel."
}

$cloudflaredCommand = Get-Command cloudflared -ErrorAction SilentlyContinue
$cloudflaredPath = if ($cloudflaredCommand) {
    $cloudflaredCommand.Source
}
else {
    "C:\Program Files (x86)\cloudflared\cloudflared.exe"
}

if (-not (Test-Path $cloudflaredPath)) {
    throw "cloudflared was not found. Install Cloudflare.cloudflared first."
}

try {
    Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/tags |
        Out-Null
}
catch {
    throw "Ollama is not reachable at http://localhost:11434. Start Ollama first."
}

Write-Host "Starting the authenticated development tunnel to local Ollama..."
& $cloudflaredPath tunnel --no-autoupdate run --token $TunnelToken
