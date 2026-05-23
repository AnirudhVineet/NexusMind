# Phase 5 — Migration sequence

Apply these in order **after** Phase 4 head (`0025_generated_content`).

```
0026_media_jobs              Track A
0027_media_assets            Track A
0028_voices                  Track B
0029  (intentionally skipped — kept open for a future meme_assets migration)
0030_share_links             Track F
0031_brandkit                Track G
0032_generation_metrics      Track H
```

## Running them

```powershell
cd backend
.venv\Scripts\activate
alembic upgrade head
```

You can also run incrementally:

```powershell
alembic upgrade 0026   # after Track A code lands
alembic upgrade 0027
alembic upgrade 0028
# … and so on
```

## Why the 0029 gap?

The Phase 5 plan originally reserved migration 0029 for a `meme_assets`
table. We ended up storing template metadata in JSON sidecars colocated with
the PNG files instead, which avoids the migration entirely. The numbering
gap is preserved so a future "uploaded user meme templates" feature can
slot in without renumbering downstream migrations.
