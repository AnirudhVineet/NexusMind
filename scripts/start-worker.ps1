param(
    # -Lite starts only the 3 workers most dev sessions need (NM-fast,
    # NM-content, NM-media) and skips the heavy ML workers — saves ~3-5 GB
    # of resident RAM when you're not ingesting documents.
    [switch]$Lite
)

# Start Celery workers — one process per queue group so fast tasks never wait
# behind slow Ollama/NLI tasks from another stage.
#
# Queue groups:
#   fast        : default              — parse, chunk, embed   (file I/O + Gemini API, <5s each)
#   ner         : ner                  — spaCy + GLiNER per chunk (~10-20s per doc)
#   llm         : relations,intelligence — Ollama JSON calls (20-60s per doc)
#   credibility : credibility          — credibility scoring (~5-15s per doc)
#   misc        : ocr,transcription,cards,maintenance — infrequent tasks
#   research    : research             — Phase 4 research brief generation
#   media       : reel                 — Phase 5 reel/narration/storyboard/bundle render jobs
#   content     : content              — Phase 4 Track H content repurposing
#
# Workers run as hidden background processes. Logs go to logs\workers\<name>.log
# To stop all workers: Get-Content logs\workers\pids.txt | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

$ErrorActionPreference = "Stop"
$root  = Resolve-Path "$PSScriptRoot\.."
$back  = "$root\backend"

# Force unbuffered output so log files capture celery output in real time.
[System.Environment]::SetEnvironmentVariable("PYTHONUNBUFFERED", "1", "Process")

# Load .env into this process so workers inherit environment variables.
$envFile = "$root\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#=]+)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

$celery  = "$back\.venv\Scripts\celery.exe"
$logDir  = "$root\logs\workers"
$pidFile = "$logDir\pids.txt"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# ── Stop any previously-launched workers before starting fresh ones ─────────
# Running this script twice without first killing old workers leaves stale
# duplicates fighting for queue messages — often running OUTDATED code from
# before the last reload. We do this in two passes:
#
#   1. PIDs we recorded in pids.txt from a previous run of this script.
#   2. Belt-and-braces: any other celery.exe whose command line points at
#      THIS project's venv (catches workers started outside pids.txt and
#      avoids killing unrelated Celery installs elsewhere on the box).
$stopped = 0
if (Test-Path $pidFile) {
    foreach ($line in (Get-Content $pidFile)) {
        $oldId = ($line -as [int])
        if (-not $oldId) { continue }
        try {
            Stop-Process -Id $oldId -Force -ErrorAction Stop
            $stopped++
        } catch {
            # Process already gone — no-op.
        }
    }
}

$ourVenv = ([regex]::Escape("$back\.venv"))
try {
    Get-CimInstance Win32_Process -Filter "Name='celery.exe'" -ErrorAction Stop |
        Where-Object { $_.CommandLine -match $ourVenv } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
                $stopped++
            } catch {}
        }
} catch {
    # CIM may not be available on every host; silently fall through.
}

if ($stopped -gt 0) {
    Write-Host "Stopped $stopped stale worker process(es) before relaunch." -ForegroundColor Yellow
}

if (Test-Path $pidFile) { Clear-Content $pidFile }

if ($Lite) {
    $workers = @(
        @{ Name = "NM-fast";     Queues = "default" },
        @{ Name = "NM-media";    Queues = "reel" },
        @{ Name = "NM-content";  Queues = "content" },
        @{ Name = "NM-research"; Queues = "research" }
    )
} else {
    $workers = @(
        @{ Name = "NM-fast";        Queues = "default" },
        @{ Name = "NM-ner";         Queues = "ner" },
        @{ Name = "NM-llm";         Queues = "relations,intelligence" },
        @{ Name = "NM-credibility"; Queues = "credibility" },
        @{ Name = "NM-misc";        Queues = "ocr,transcription,cards,maintenance" },
        @{ Name = "NM-research";    Queues = "research" },
        @{ Name = "NM-media";       Queues = "reel" },
        @{ Name = "NM-content";     Queues = "content" }
    )
}

$mode = if ($Lite) { " (LITE mode)" } else { "" }
Write-Host "Starting $($workers.Count) Celery workers$mode (hidden, logging to logs\workers\)..." -ForegroundColor Cyan

foreach ($w in $workers) {
    $log = "$logDir\$($w.Name).log"

    $proc = Start-Process -FilePath $celery `
        -ArgumentList "-A", "app.workers.celery_app", "worker",
                      "-Q", $w.Queues,
                      "-n", "$($w.Name)@%h",
                      "--pool=solo", "--loglevel=info" `
        -WorkingDirectory $back `
        -WindowStyle Hidden `
        -RedirectStandardOutput $log `
        -RedirectStandardError  "$logDir\$($w.Name).err.log" `
        -PassThru

    Add-Content $pidFile $proc.Id
    Write-Host "  $($w.Name) [$($w.Queues)]  PID $($proc.Id)  -> logs\workers\$($w.Name).log" -ForegroundColor Green
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "All workers running in background." -ForegroundColor Cyan
Write-Host "Logs : $logDir" -ForegroundColor DarkGray
Write-Host "Stop : Get-Content '$pidFile' | ForEach-Object { Stop-Process -Id `$_ -Force -EA SilentlyContinue }" -ForegroundColor DarkGray
