"""Phase 5 Track C — Centralized region descriptors for all meme templates.

Replaces the hardcoded `_resolve_panels` heuristic in content_engine.py with
a data-driven layout. Each template defines its panels as fractional
coordinates so they scale with the underlying PNG resolution.

Region fields:
  id          — slot identifier (the LLM is asked to fill this)
  x, y        — top-left corner as a fraction of (width, height) ∈ [0,1]
  w, h        — width/height as fractions
  align       — "left" | "center" | "right"
  font_size_pct — fraction of height used to size the font
  uppercase   — render text in uppercase (classic meme style)
  color       — RGBA hex (default "#FFFFFFFF")
  outline     — RGBA hex outline color, "" for none
"""
from __future__ import annotations

from typing import Any

# Common style presets ------------------------------------------------------

CLASSIC_OUTLINE = "#000000FF"
MEME_WHITE = "#FFFFFFFF"

# Each value is { name, layout, regions[], aliases?, license, source } ------

TEMPLATE_SIDECARS: dict[str, dict[str, Any]] = {
    "drake": {
        "name": "Drake",
        "layout": "two_panel_vertical",
        "regions": [
            {
                "id": "reject",
                "x": 0.55,
                "y": 0.05,
                "w": 0.42,
                "h": 0.40,
                "align": "left",
                "font_size_pct": 0.06,
                "color": MEME_WHITE,
                "outline": "",
            },
            {
                "id": "approve",
                "x": 0.55,
                "y": 0.55,
                "w": 0.42,
                "h": 0.40,
                "align": "left",
                "font_size_pct": 0.06,
                "color": MEME_WHITE,
                "outline": "",
            },
        ],
        "aliases": ["top", "bottom"],
        "license": "fair_use_meme_archive",
        "source": "internal placeholder PNG",
    },
    "two_buttons": {
        "name": "Two Buttons",
        "layout": "two_button",
        "regions": [
            {
                "id": "button_left",
                "x": 0.05,
                "y": 0.30,
                "w": 0.40,
                "h": 0.30,
                "align": "center",
                "font_size_pct": 0.06,
                "color": MEME_WHITE,
                "outline": CLASSIC_OUTLINE,
            },
            {
                "id": "button_right",
                "x": 0.55,
                "y": 0.30,
                "w": 0.40,
                "h": 0.30,
                "align": "center",
                "font_size_pct": 0.06,
                "color": MEME_WHITE,
                "outline": CLASSIC_OUTLINE,
            },
        ],
        "aliases": ["top", "bottom"],
        "license": "fair_use_meme_archive",
        "source": "internal placeholder PNG",
    },
    "expanding_brain": {
        "name": "Expanding Brain",
        "layout": "four_panel_vertical",
        "regions": [
            {"id": "level_1", "x": 0.55, "y": 0.02, "w": 0.42, "h": 0.20, "align": "left", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": ""},
            {"id": "level_2", "x": 0.55, "y": 0.27, "w": 0.42, "h": 0.20, "align": "left", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": ""},
            {"id": "level_3", "x": 0.55, "y": 0.52, "w": 0.42, "h": 0.20, "align": "left", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": ""},
            {"id": "level_4", "x": 0.55, "y": 0.77, "w": 0.42, "h": 0.20, "align": "left", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": ""},
        ],
        "aliases": ["top", "bottom"],
        "license": "fair_use_meme_archive",
        "source": "internal placeholder PNG",
    },
    "distracted_boyfriend": {
        "name": "Distracted Boyfriend",
        "layout": "three_label",
        "regions": [
            {"id": "boyfriend", "x": 0.55, "y": 0.55, "w": 0.20, "h": 0.10, "align": "center", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "girlfriend", "x": 0.80, "y": 0.55, "w": 0.18, "h": 0.10, "align": "center", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "other_woman", "x": 0.15, "y": 0.55, "w": 0.22, "h": 0.10, "align": "center", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
        ],
        "aliases": ["top", "bottom"],
        "license": "fair_use_meme_archive",
        "source": "internal placeholder PNG",
    },
    "change_my_mind": {
        "name": "Change My Mind",
        "layout": "single_centered",
        "regions": [
            {"id": "claim", "x": 0.10, "y": 0.45, "w": 0.50, "h": 0.30, "align": "center", "font_size_pct": 0.05, "color": "#000000FF", "outline": ""},
        ],
        "aliases": ["top", "bottom"],
        "license": "fair_use_meme_archive",
        "source": "internal placeholder PNG",
    },
    # ─── New Phase 5 templates ──────────────────────────────────────────────
    "galaxy_brain": {
        "name": "Galaxy Brain",
        "layout": "four_panel_vertical",
        "regions": [
            {"id": "level_1", "x": 0.55, "y": 0.02, "w": 0.42, "h": 0.20, "align": "left", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": ""},
            {"id": "level_2", "x": 0.55, "y": 0.27, "w": 0.42, "h": 0.20, "align": "left", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": ""},
            {"id": "level_3", "x": 0.55, "y": 0.52, "w": 0.42, "h": 0.20, "align": "left", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": ""},
            {"id": "level_4", "x": 0.55, "y": 0.77, "w": 0.42, "h": 0.20, "align": "left", "font_size_pct": 0.04, "color": "#FFFF00FF", "outline": ""},
        ],
        "aliases": ["top", "bottom"],
        "license": "cc0_placeholder",
        "source": "internal placeholder PNG",
    },
    "this_is_fine": {
        "name": "This Is Fine",
        "layout": "top_bottom",
        "regions": [
            {"id": "top", "x": 0.05, "y": 0.03, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "bottom", "x": 0.05, "y": 0.82, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
        ],
        "license": "cc0_placeholder",
        "source": "internal placeholder PNG",
    },
    "surprised_pikachu": {
        "name": "Surprised Pikachu",
        "layout": "top_bottom",
        "regions": [
            {"id": "top", "x": 0.05, "y": 0.03, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "bottom", "x": 0.05, "y": 0.82, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
        ],
        "license": "cc0_placeholder",
        "source": "internal placeholder PNG",
    },
    "roll_safe": {
        "name": "Roll Safe",
        "layout": "top_bottom",
        "regions": [
            {"id": "top", "x": 0.05, "y": 0.03, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "bottom", "x": 0.05, "y": 0.82, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
        ],
        "license": "cc0_placeholder",
        "source": "internal placeholder PNG",
    },
    "always_has_been": {
        "name": "Always Has Been",
        "layout": "two_speech",
        "regions": [
            {"id": "realization", "x": 0.05, "y": 0.05, "w": 0.50, "h": 0.20, "align": "left", "font_size_pct": 0.05, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "reply", "x": 0.45, "y": 0.65, "w": 0.50, "h": 0.20, "align": "right", "font_size_pct": 0.05, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
        ],
        "aliases": ["top", "bottom"],
        "license": "cc0_placeholder",
        "source": "internal placeholder PNG",
    },
    "woman_yelling_at_cat": {
        "name": "Woman Yelling at Cat",
        "layout": "two_panel_horizontal",
        "regions": [
            {"id": "woman", "x": 0.02, "y": 0.05, "w": 0.46, "h": 0.20, "align": "center", "font_size_pct": 0.05, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "cat", "x": 0.52, "y": 0.05, "w": 0.46, "h": 0.20, "align": "center", "font_size_pct": 0.05, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
        ],
        "aliases": ["top", "bottom"],
        "license": "cc0_placeholder",
        "source": "internal placeholder PNG",
    },
    "hide_the_pain_harold": {
        "name": "Hide the Pain Harold",
        "layout": "top_bottom",
        "regions": [
            {"id": "top", "x": 0.05, "y": 0.03, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "bottom", "x": 0.05, "y": 0.82, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
        ],
        "license": "cc0_placeholder",
        "source": "internal placeholder PNG",
    },
    "gru_plan": {
        "name": "Gru's Plan",
        "layout": "four_panel_grid",
        "regions": [
            {"id": "step_1", "x": 0.02, "y": 0.02, "w": 0.46, "h": 0.46, "align": "center", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "step_2", "x": 0.52, "y": 0.02, "w": 0.46, "h": 0.46, "align": "center", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "step_3", "x": 0.02, "y": 0.52, "w": 0.46, "h": 0.46, "align": "center", "font_size_pct": 0.04, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "step_4", "x": 0.52, "y": 0.52, "w": 0.46, "h": 0.46, "align": "center", "font_size_pct": 0.04, "color": "#FFFF00FF", "outline": CLASSIC_OUTLINE},
        ],
        "aliases": ["top", "bottom"],
        "license": "cc0_placeholder",
        "source": "internal placeholder PNG",
    },
    "mocking_spongebob": {
        "name": "Mocking SpongeBob",
        "layout": "top_bottom_caps",
        "regions": [
            {"id": "top", "x": 0.05, "y": 0.03, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE, "uppercase": True},
            {"id": "bottom", "x": 0.05, "y": 0.82, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE, "alternate_caps": True},
        ],
        "license": "cc0_placeholder",
        "source": "internal placeholder PNG",
    },
    "success_kid": {
        "name": "Success Kid",
        "layout": "top_bottom",
        "regions": [
            {"id": "top", "x": 0.05, "y": 0.03, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
            {"id": "bottom", "x": 0.05, "y": 0.82, "w": 0.90, "h": 0.15, "align": "center", "font_size_pct": 0.07, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
        ],
        "license": "cc0_placeholder",
        "source": "internal placeholder PNG",
    },
    "custom": {
        "name": "Custom",
        "layout": "ai_generated_background",
        "regions": [
            {"id": "main", "x": 0.05, "y": 0.70, "w": 0.90, "h": 0.25, "align": "center", "font_size_pct": 0.08, "color": MEME_WHITE, "outline": CLASSIC_OUTLINE},
        ],
        "license": "user_owned",
        "source": "ai_generated",
    },
}


def get_sidecar(template_filename: str) -> dict[str, Any] | None:
    """Return the sidecar for a given template filename (with or without .png)."""
    key = template_filename.lower().replace(".png", "").replace(" ", "_")
    return TEMPLATE_SIDECARS.get(key)


def list_templates() -> list[dict[str, Any]]:
    """Return all known templates with their public metadata."""
    out: list[dict[str, Any]] = []
    for key, side in TEMPLATE_SIDECARS.items():
        out.append(
            {
                "key": key,
                "name": side["name"],
                "layout": side["layout"],
                "regions": side["regions"],
                "license": side.get("license", "unknown"),
            }
        )
    return out
