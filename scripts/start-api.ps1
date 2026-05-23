# Start the FastAPI server.
#
# IMPORTANT: --reload is scoped to `app/` only. The project lives inside the
# user's OneDrive sync root, so a bare `--reload` watches .venv (2 GB+,
# ~30k files), data/, logs/, and any rendered reels. OneDrive constantly
# touches those, triggering reload storms that make every API call stall.
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
Set-Location $root\backend

Get-Content ..\.env | ForEach-Object {
    if ($_ -match "^\s*([^#=]+)=(.*)$") {
        Set-Item -Path "Env:$($matches[1].Trim())" -Value $matches[2].Trim()
    }
}

.\.venv\Scripts\uvicorn.exe app.main:app `
    --host 0.0.0.0 --port 8000 `
    --reload `
    --reload-dir app `
    --reload-exclude __pycache__
