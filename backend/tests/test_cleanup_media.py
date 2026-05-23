"""Track H — cleanup helpers don't crash on empty/missing state."""
from __future__ import annotations

import time
from pathlib import Path

from app.workers import media_cleanup


def test_cleanup_orphan_scratch_dirs_no_op_on_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(media_cleanup, "scratch_dir", lambda: tmp_path)
    result = media_cleanup.cleanup_orphan_scratch_dirs()
    assert result["removed"] == 0


def test_cleanup_orphan_scratch_dirs_removes_old(tmp_path, monkeypatch):
    monkeypatch.setattr(media_cleanup, "scratch_dir", lambda: tmp_path)

    old = tmp_path / "old_job"
    old.mkdir()
    (old / "x.txt").write_text("hi")
    # Backdate the mtime 7 hours
    cutoff = time.time() - 7 * 60 * 60
    import os

    os.utime(old, (cutoff, cutoff))

    new = tmp_path / "fresh_job"
    new.mkdir()

    result = media_cleanup.cleanup_orphan_scratch_dirs()
    assert result["removed"] == 1
    assert not old.exists()
    assert new.exists()


def test_cleanup_scratch_handles_missing_root(tmp_path, monkeypatch):
    missing = tmp_path / "doesnt_exist"
    monkeypatch.setattr(media_cleanup, "scratch_dir", lambda: missing)
    result = media_cleanup.cleanup_orphan_scratch_dirs()
    assert result == {"removed": 0}
