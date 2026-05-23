"""Track D — HTML slides format."""
from __future__ import annotations

from app.services.media import storyboard_renderer
from app.services.media.storyboard_renderer import Frame


def test_html_slides_self_contained(tmp_path):
    from PIL import Image

    src = tmp_path / "src.png"
    Image.new("RGB", (40, 40), (180, 90, 90)).save(src)

    frames = [
        Frame(index=1, narration="n1", visual="v1", audio_note="", duration=3.0),
    ]
    visuals = [(src, "test")]
    audio_paths = [None]

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = storyboard_renderer._render_html_slides(
        out_dir, frames, visuals, audio_paths
    )
    assert result == out_dir / "index.html"
    assert result.exists()
    html = result.read_text(encoding="utf-8")
    assert "<html" in html.lower()
    assert "Frame 1" in html
    assert "frame_01.png" in html
    assert (out_dir / "frame_01.png").exists()


def test_html_escape_neutralizes_tags():
    assert "<script>" not in storyboard_renderer._html_escape("<script>")
    assert "&lt;script&gt;" == storyboard_renderer._html_escape("<script>")
