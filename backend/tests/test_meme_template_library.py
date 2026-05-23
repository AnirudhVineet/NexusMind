"""Track C — sidecar library has consistent shape across all templates."""
from __future__ import annotations

from app.assets.meme_templates.sidecars import TEMPLATE_SIDECARS, get_sidecar


def test_every_sidecar_has_required_keys():
    for key, side in TEMPLATE_SIDECARS.items():
        assert "name" in side, f"{key} missing name"
        assert "layout" in side, f"{key} missing layout"
        assert "regions" in side, f"{key} missing regions"
        assert isinstance(side["regions"], list)
        assert len(side["regions"]) >= 1
        for r in side["regions"]:
            assert {"id", "x", "y", "w", "h"} <= set(r.keys())
            assert 0.0 <= r["x"] <= 1.0
            assert 0.0 <= r["y"] <= 1.0
            assert 0.0 <= r["w"] <= 1.0
            assert 0.0 <= r["h"] <= 1.0


def test_at_least_fifteen_templates_present():
    assert len(TEMPLATE_SIDECARS) >= 15


def test_get_sidecar_handles_filename_variants():
    a = get_sidecar("drake")
    b = get_sidecar("Drake.png")
    c = get_sidecar("drake.PNG")
    assert a is not None
    assert a == b == c


def test_unknown_template_returns_none():
    assert get_sidecar("definitely_not_a_template") is None


def test_phase5_new_templates_are_present():
    new_ones = [
        "galaxy_brain",
        "this_is_fine",
        "surprised_pikachu",
        "roll_safe",
        "always_has_been",
        "woman_yelling_at_cat",
        "hide_the_pain_harold",
        "gru_plan",
        "mocking_spongebob",
        "success_kid",
        "custom",
    ]
    for key in new_ones:
        assert key in TEMPLATE_SIDECARS
