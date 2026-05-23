# Start the Next.js dev server.
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
Set-Location $root\frontend

Get-Content ..\.env | ForEach-Object {
    if ($_ -match "^\s*([^#=]+)=(.*)$") {
        Set-Item -Path "Env:$($matches[1].Trim())" -Value $matches[2].Trim()
    }
}

npm run dev
