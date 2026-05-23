"""Track D — image series storyboard format."""
from __future__ import annotations

import json
from pathlib import Path

from app.services.media import storyboard_renderer
from app.services.media.storyboard_renderer import Frame


def test_image_series_writes_frames_and_manifest(tmp_path):
    from PIL import Image

    src_img = tmp_path / "src.png"
    Image.new("RGB", (50, 50), (90, 90, 110)).save(src_img)

    frames = [
        Frame(index=1, narration="n1", visual="v1", audio_note="", duration=3.0),
        Frame(index=2, narration="n2", visual="v2", audio_note="", duration=4.0),
    ]
    visuals = [(src_img, "test"), (src_img, "test")]
    audio_paths = [None, None]

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = storyboard_renderer._render_image_series(
        out_dir, frames, visuals, audio_paths
    )

    assert result == out_dir
    assert (out_dir / "manifest.json").exists()
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert len(manifest) == 2
    assert manifest[0]["index"] == 1
    assert manifest[0]["image"] is not None
    # Both per-frame PNGs were copied
    assert (out_dir / "frame_01.png").exists()
    assert (out_dir / "frame_02.png").exists()
