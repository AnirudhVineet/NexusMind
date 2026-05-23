"""Track F — bundle_export zips files + extra text correctly."""
from __future__ import annotations

import uuid
import zipfile

from app.services import publish
from app.services.media import bundles_dir


def test_bundle_export_writes_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "bundles_dir", lambda: tmp_path)

    f1 = tmp_path / "video.mp4"
    f1.write_bytes(b"fake mp4 bytes")
    f2 = tmp_path / "subtitles.srt"
    f2.write_text("1\n00:00:00,000 --> 00:00:05,000\nHello\n")

    tid = uuid.uuid4()
    out = publish.bundle_export(
        target_type="media_job",
        target_id=tid,
        files=[("video.mp4", f1), ("subtitles.srt", f2)],
        extra_text={"caption.txt": "A caption."},
    )

    assert out.exists()
    assert out.suffix == ".zip"
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "video.mp4" in names
        assert "subtitles.srt" in names
        assert "caption.txt" in names
        assert zf.read("caption.txt").decode() == "A caption."


def test_bundle_export_skips_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "bundles_dir", lambda: tmp_path)

    missing = tmp_path / "no-such.mp4"
    real = tmp_path / "real.txt"
    real.write_text("hello")

    out = publish.bundle_export(
        target_type="content",
        target_id=uuid.uuid4(),
        files=[("missing.mp4", missing), ("real.txt", real)],
    )
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "missing.mp4" not in names
        assert "real.txt" in names
