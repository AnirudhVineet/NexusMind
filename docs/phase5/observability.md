# Phase 5 — Media observability

## Prometheus metrics (added in Track H)

| Metric | Type | Labels | Notes |
|---|---|---|---|
| `nexusmind_media_jobs_total` | Counter | `job_type`, `status` | Increment in renderer at terminal status |
| `nexusmind_media_job_duration_seconds` | Histogram | `job_type` | Observe on completion |
| `nexusmind_media_cost_usd_total` | Counter | `provider` | Inc by `cost_estimate_usd` from each metric row |
| `nexusmind_visual_provider_calls_total` | Counter | `provider`, `status` | `ok`, `timeout`, `error` |
| `nexusmind_tts_provider_calls_total` | Counter | `provider`, `status` | Same status set |
| `nexusmind_media_disk_used_bytes` | Gauge | `user_id` | Recomputed by cleanup beat task |

All metrics share the `nexusmind_` prefix used by Phases 2–4.

## Grafana dashboard

Provisioned at `ops/grafana/dashboards/media.json`. Import it via the
Grafana UI or drop it into the Grafana provisioning directory next to the
Phase 4 dashboards (`ingestion.json`, `retrieval.json`, `ai_usage.json`,
`system.json`).

## Cost rate cards

`backend/app/services/media/cost_rates.py` holds rough per-provider USD
rates per 1M units. They are estimates — update when a provider changes
pricing. Free providers report 0.0.

## Quota strip

The Studio header renders `QuotaStrip` (frontend), which calls
`GET /api/media/quota-status` every 30 s and surfaces:

- Daily counter per job type (`reel`, `narration`, `storyboard`, `meme_image`)
- Per-user disk usage vs cap (`MEDIA_USER_QUOTA_BYTES`, default 2 GB)
- Today's estimated USD spend (sums `generation_metrics.cost_estimate_usd`
  across all providers for the last 24 hours)

When a counter crosses 70 % it goes amber; at 90 % it goes red. Render
endpoints return 429 with `Retry-After: 86400` (midnight UTC) when over cap.

## Cleanup beat tasks (registered in celery_app.py)

| Task | Schedule | Effect |
|---|---|---|
| `cleanup_expired_media` | every hour | Deletes media_jobs files + DB rows past `expires_at` |
| `cleanup_orphan_scratch_dirs` | every hour | Removes scratch subdirs older than 6 hours |

Both run on the existing `maintenance` queue.

## Importing the Grafana dashboard

```bash
# From a Linux/macOS shell with curl + a Grafana API key
curl -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${GRAFANA_API_TOKEN}" \
  -d @ops/grafana/dashboards/media.json \
  http://localhost:3001/api/dashboards/db
```

On Windows / PowerShell:

```powershell
$payload = Get-Content ops/grafana/dashboards/media.json -Raw
Invoke-RestMethod -Uri http://localhost:3001/api/dashboards/db `
  -Method Post -ContentType "application/json" `
  -Headers @{ Authorization = "Bearer $env:GRAFANA_API_TOKEN" } `
  -Body $payload
```
