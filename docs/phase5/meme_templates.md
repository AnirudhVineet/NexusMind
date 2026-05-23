# Phase 5 — Meme template library

NexusMind ships **15 placeholder meme templates** as CC0-style geometric
PNG files (no copyrighted imagery). They demonstrate every supported
layout type and let you preview meme generation end-to-end before you
swap in real artwork.

## Generating the bundled placeholders

```powershell
cd backend
.venv\Scripts\activate
python scripts/generate_meme_templates.py
```

This writes 15 PNG files into `backend/app/assets/meme_templates/`.

## Template inventory

| Key | Layout | Regions | Notes |
|---|---|---|---|
| drake | two_panel_vertical | 2 | Top "reject", bottom "approve" |
| two_buttons | two_button | 2 | Side-by-side choice |
| expanding_brain | four_panel_vertical | 4 | Escalating absurdity |
| distracted_boyfriend | three_label | 3 | bf / gf / other_woman |
| change_my_mind | single_centered | 1 | Sign panel |
| galaxy_brain | four_panel_vertical | 4 | Brighter ramp than expanding_brain |
| this_is_fine | top_bottom | 2 | Setup → outcome |
| surprised_pikachu | top_bottom | 2 | Predictable surprise |
| roll_safe | top_bottom | 2 | Smug logic |
| always_has_been | two_speech | 2 | Realization + reply |
| woman_yelling_at_cat | two_panel_horizontal | 2 | Argument |
| hide_the_pain_harold | top_bottom | 2 | Smiling pain |
| gru_plan | four_panel_grid | 4 | Step 4 highlighted |
| mocking_spongebob | top_bottom_caps | 2 | Bottom panel uses alternate caps |
| success_kid | top_bottom | 2 | Triumph |
| custom | ai_generated_background | 1 | AI image + single overlay |

## Swapping in real artwork

For each template you can replace the placeholder PNG with a real image
sized to the same dimensions (or any size — the renderer scales by
fractional coordinates). Keep the filename identical; sidecars live in
`backend/app/assets/meme_templates/sidecars.py`, not next to the PNGs.

When you swap real artwork in:

1. Confirm the source license. Some classic meme templates have unclear
   copyright; many are treated as fair-use within commentary and parody
   contexts but vary by jurisdiction. Document your decision in
   `docs/phase5/meme_templates.md` (this file).
2. Re-check the region descriptors in `sidecars.py`. If the new artwork's
   text-blank areas differ from the placeholder's, adjust the fractional
   `(x, y, w, h)` to match.
3. The renderer always uses fractional coordinates so resolution changes
   don't break the layout — only the aspect ratio matters.

## Region descriptor reference

Every region in `sidecars.py` supports:

```python
{
    "id": "reject",            # slot id the LLM fills
    "x": 0.55, "y": 0.05,      # top-left as fraction of (W, H)
    "w": 0.42, "h": 0.40,      # size as fraction
    "align": "left",           # left | center | right
    "font_size_pct": 0.06,     # fraction of H used as base font size (auto-shrinks)
    "color": "#FFFFFFFF",      # RGBA hex
    "outline": "#000000FF",    # outline color, "" for none
    "uppercase": False,        # SHOUTING
    "alternate_caps": False,   # mOcKiNg SpOnGeBoB style
}
```

The renderer shrinks the font when text won't fit and then performs greedy
word wrap. Lines that overflow the box vertically are dropped.

## Custom AI backgrounds

Setting `template_key = "custom"` skips the template library and
generates a background image via the same visual provider chain as
reels (Pollinations → HF SDXL → Pexels → solid). The meme JSON for
custom memes uses a single `main` region:

```json
{
  "template_key": "custom",
  "panel_texts": { "main": "Your text here" },
  "custom_background_prompt": "abstract digital brain neurons firing"
}
```

If all providers fail, the renderer falls back to a solid-color
background so the meme still produces output.
