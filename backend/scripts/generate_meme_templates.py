"""
Generate simple CC0/public-domain-style meme template PNG files using Pillow.
All templates use flat colors and geometric shapes — no copyrighted imagery.

Run from the backend/ directory with the venv active:
    python scripts/generate_meme_templates.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).parent.parent / "app" / "assets" / "meme_templates"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _save(img: Image.Image, name: str) -> None:
    path = OUT_DIR / f"{name}.png"
    img.save(path)
    print(f"  saved {path}")


# ---------------------------------------------------------------------------
# Drake (two-panel: reject top, approve bottom)
# ---------------------------------------------------------------------------
def make_drake() -> None:
    w, h = 600, 600
    img = Image.new("RGB", (w, h), "#1a1a2e")
    draw = ImageDraw.Draw(img)
    mid = h // 2
    draw.rectangle([0, 0, w, mid], fill="#16213e")
    draw.rectangle([0, mid, w, h], fill="#0f3460")
    draw.line([(0, mid), (w, mid)], fill="#e94560", width=3)

    f_sm = _font(18)
    draw.text((10, mid // 2 - 10), "Top panel (reject/ignore)", fill="#888", font=f_sm)
    draw.text((10, mid + mid // 2 - 10), "Bottom panel (prefer/approve)", fill="#e2e8f0", font=f_sm)

    f_label = _font(14)
    draw.text((w - 80, 5), "DRAKE", fill="#e94560", font=f_label)
    _save(img, "drake")


# ---------------------------------------------------------------------------
# Two Buttons (person sweating over two buttons)
# ---------------------------------------------------------------------------
def make_two_buttons() -> None:
    w, h = 600, 400
    img = Image.new("RGB", (w, h), "#1a1a2e")
    draw = ImageDraw.Draw(img)
    bw, bh = 220, 120
    gap = 40
    total = bw * 2 + gap
    x1 = (w - total) // 2
    x2 = x1 + bw + gap
    by = (h - bh) // 2

    draw.rectangle([x1, by, x1 + bw, by + bh], fill="#16213e", outline="#e94560", width=3)
    draw.rectangle([x2, by, x2 + bw, by + bh], fill="#16213e", outline="#e94560", width=3)

    f = _font(16)
    draw.text((x1 + 10, by + 10), "Button A\n(option 1)", fill="#e2e8f0", font=f)
    draw.text((x2 + 10, by + 10), "Button B\n(option 2)", fill="#e2e8f0", font=f)

    f_label = _font(14)
    draw.text((w - 130, 5), "TWO BUTTONS", fill="#e94560", font=f_label)
    _save(img, "two_buttons")


# ---------------------------------------------------------------------------
# Expanding Brain (4 rows, increasing brightness)
# ---------------------------------------------------------------------------
def make_expanding_brain() -> None:
    w, h = 600, 800
    panel_h = h // 4
    shades = ["#0d0d1a", "#111128", "#151535", "#1a1a42"]
    labels = ["Tier 1 (simple)", "Tier 2 (medium)", "Tier 3 (complex)", "Tier 4 (galaxy brain)"]
    img = Image.new("RGB", (w, h), "#000")
    draw = ImageDraw.Draw(img)
    f = _font(18)
    for i, (shade, label) in enumerate(zip(shades, labels)):
        y = i * panel_h
        draw.rectangle([0, y, w, y + panel_h], fill=shade)
        draw.line([(0, y + panel_h), (w, y + panel_h)], fill="#333", width=1)
        draw.text((10, y + panel_h // 2 - 10), label, fill="#e2e8f0", font=f)

    f_label = _font(14)
    draw.text((w - 170, 5), "EXPANDING BRAIN", fill="#e94560", font=f_label)
    _save(img, "expanding_brain")


# ---------------------------------------------------------------------------
# Distracted Boyfriend (3-part: bf, gf, other)
# ---------------------------------------------------------------------------
def make_distracted_boyfriend() -> None:
    w, h = 800, 400
    img = Image.new("RGB", (w, h), "#1a1a2e")
    draw = ImageDraw.Draw(img)
    colors = ["#0f3460", "#16213e", "#e94560"]
    labels = ["Boyfriend\n(current focus)", "Girlfriend\n(old/stable)", "Distraction\n(new/shiny)"]
    section_w = w // 3
    f = _font(16)
    for i, (color, label) in enumerate(zip(colors, labels)):
        x = i * section_w
        draw.rectangle([x, 0, x + section_w, h], fill=color)
        draw.line([(x + section_w, 0), (x + section_w, h)], fill="#444", width=2)
        draw.text((x + 10, h // 2 - 20), label, fill="#e2e8f0", font=f)

    f_label = _font(14)
    draw.text((w - 215, 5), "DISTRACTED BOYFRIEND", fill="#eee", font=f_label)
    _save(img, "distracted_boyfriend")


# ---------------------------------------------------------------------------
# Change My Mind (person at table)
# ---------------------------------------------------------------------------
def make_change_my_mind() -> None:
    w, h = 600, 400
    img = Image.new("RGB", (w, h), "#1a1a2e")
    draw = ImageDraw.Draw(img)
    # Table
    draw.rectangle([50, h * 2 // 3, w - 50, h * 2 // 3 + 20], fill="#555")
    # Sign area
    sign_x, sign_y, sign_w, sign_h = 150, 100, 300, 160
    draw.rectangle([sign_x, sign_y, sign_x + sign_w, sign_y + sign_h], fill="#fff", outline="#e94560", width=3)
    f = _font(18)
    draw.text((sign_x + 10, sign_y + 10), "Your claim here.\n\nChange my mind.", fill="#1a1a2e", font=f)
    f_label = _font(14)
    draw.text((w - 155, 5), "CHANGE MY MIND", fill="#e94560", font=f_label)
    _save(img, "change_my_mind")


# ---------------------------------------------------------------------------
# Phase 5 — additional placeholder templates
#
# These are non-photographic, CC0-style geometric placeholders. They are
# designed to look distinct from each other so a user can preview meme
# layouts before swapping in real (licensed) imagery later.
# ---------------------------------------------------------------------------


def _placeholder_panel(
    name: str, w: int, h: int, palette: list[str], label_color: str = "#e94560"
) -> None:
    img = Image.new("RGB", (w, h), palette[0])
    draw = ImageDraw.Draw(img)
    band_h = max(40, h // 5)
    for i, color in enumerate(palette[1:], start=1):
        draw.rectangle([0, i * band_h, w, (i + 1) * band_h], fill=color)
    f_label = _font(14)
    draw.text((10, 5), name.upper(), fill=label_color, font=f_label)
    _save(img, name)


def make_galaxy_brain() -> None:
    _placeholder_panel(
        "galaxy_brain", 600, 800,
        palette=["#0a0a1a", "#181840", "#3050a0", "#80a0ff", "#fff5cc"],
    )


def make_this_is_fine() -> None:
    _placeholder_panel(
        "this_is_fine", 800, 600,
        palette=["#3a1a0a", "#7a2a10", "#c25018", "#e07020"],
    )


def make_surprised_pikachu() -> None:
    _placeholder_panel(
        "surprised_pikachu", 700, 700,
        palette=["#ffdc00", "#ffeb50", "#ffeb50", "#444"],
        label_color="#444",
    )


def make_roll_safe() -> None:
    _placeholder_panel(
        "roll_safe", 700, 500,
        palette=["#241a18", "#3a2820", "#5a3528"],
    )


def make_always_has_been() -> None:
    w, h = 800, 600
    img = Image.new("RGB", (w, h), "#0a0a1a")
    draw = ImageDraw.Draw(img)
    # Two "astronaut" silhouettes
    draw.ellipse([50, 80, 250, 280], fill="#fff")
    draw.ellipse([550, 280, 750, 480], fill="#fff")
    f = _font(14)
    draw.text((w - 200, 5), "ALWAYS HAS BEEN", fill="#e94560", font=f)
    _save(img, "always_has_been")


def make_woman_yelling_at_cat() -> None:
    w, h = 800, 400
    img = Image.new("RGB", (w, h), "#1a1a2e")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w // 2, h], fill="#7a2a3a")
    draw.rectangle([w // 2, 0, w, h], fill="#0f3460")
    f_label = _font(14)
    draw.text((10, 5), "WOMAN YELLING AT CAT", fill="#fff", font=f_label)
    _save(img, "woman_yelling_at_cat")


def make_hide_the_pain_harold() -> None:
    _placeholder_panel(
        "hide_the_pain_harold", 600, 600,
        palette=["#f0e8d8", "#d4c8a8", "#b09878", "#806848"],
        label_color="#333",
    )


def make_gru_plan() -> None:
    w, h = 800, 800
    img = Image.new("RGB", (w, h), "#1a1a2e")
    draw = ImageDraw.Draw(img)
    palettes = ["#0f3460", "#16213e", "#e94560", "#fff5cc"]
    for i, c in enumerate(palettes):
        r, col = divmod(i, 2)
        x = col * (w // 2)
        y = r * (h // 2)
        draw.rectangle([x + 5, y + 5, x + w // 2 - 5, y + h // 2 - 5], fill=c)
    f_label = _font(14)
    draw.text((w - 110, 5), "GRU PLAN", fill="#fff", font=f_label)
    _save(img, "gru_plan")


def make_mocking_spongebob() -> None:
    _placeholder_panel(
        "mocking_spongebob", 700, 500,
        palette=["#ffeb50", "#ffe000", "#e2c000", "#a48a00"],
        label_color="#222",
    )


def make_success_kid() -> None:
    _placeholder_panel(
        "success_kid", 700, 700,
        palette=["#4ca0c0", "#80c0d0", "#c0e0e8", "#fcdcb0"],
    )


if __name__ == "__main__":
    print(f"Generating meme templates into {OUT_DIR} ...")
    # Phase 4 originals
    make_drake()
    make_two_buttons()
    make_expanding_brain()
    make_distracted_boyfriend()
    make_change_my_mind()
    # Phase 5 additions
    make_galaxy_brain()
    make_this_is_fine()
    make_surprised_pikachu()
    make_roll_safe()
    make_always_has_been()
    make_woman_yelling_at_cat()
    make_hide_the_pain_harold()
    make_gru_plan()
    make_mocking_spongebob()
    make_success_kid()
    print("Done.")
