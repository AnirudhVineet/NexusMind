# NexusMind Observability (Phase 3.7)

Prometheus + Grafana OSS dashboards over the metrics the backend already
exposes at `/metrics`. No paid services.

## 1. Prometheus

Install Prometheus (Windows binary from prometheus.io) and run it against the
provided scrape config:

```powershell
prometheus.exe --config.file=ops\prometheus\prometheus.yml
```

It scrapes the NexusMind API at `localhost:8000/metrics`. If `METRICS_TOKEN`
is set in `backend/.env`, uncomment the `authorization` block in
`ops/prometheus/prometheus.yml` and supply the same token.

## 2. Grafana OSS

Install Grafana OSS (`winget install Grafana.Grafana`). Wire up provisioning
by copying these folders into Grafana's config directory
(`<grafana>\conf\provisioning\`):

- `ops/grafana/provisioning/datasources/prometheus.yml`
- `ops/grafana/provisioning/dashboards/provider.yml`

Before starting Grafana, edit `provider.yml` so `options.path` points at the
absolute path of `ops/grafana/dashboards` in your checkout.

Start Grafana and open <http://localhost:3000> (default login `admin`/`admin`).
The four dashboards appear under the **NexusMind** folder.

## 3. Dashboards

| Dashboard | File | Covers |
|---|---|---|
| Ingestion | `dashboards/ingestion.json` | Celery queue depth, task failures, ingestion events, NER latency, claims/contradictions |
| Retrieval | `dashboards/retrieval.json` | Query latency p50/p95/p99, per-stage timings, cache hit rate, LLM latency |
| AI Usage | `dashboards/ai_usage.json` | LLM tokens & requests by provider, Ollama throughput |
| System | `dashboards/system.json` | CPU / memory / disk, knowledge-graph size |

## 4. System dashboard (optional)

The CPU/memory/disk panels need
[windows_exporter](https://github.com/prometheus-community/windows_exporter)
(MIT licensed, free). Install it, then it is scraped via the `windows` job
already present in `prometheus.yml` (`localhost:9182`). The
"Knowledge Graph Size" panel works without it — it reads NexusMind's own
metrics.
