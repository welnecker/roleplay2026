from __future__ import annotations

from services.novel_synced_visual_contract import apply_visual_contract


def test_visual_contract_preserves_full_image_without_crop() -> None:
    html = apply_visual_contract('<section class="sync-mobile"></section>')
    assert "object-fit:contain!important" in html
    assert "height:auto!important" in html
    assert "object-position:center top!important" in html
    assert "object-fit:cover!important" not in html
    assert "aspect-ratio:16 / 9" not in html


def test_visual_contract_standardizes_balloon_geometry() -> None:
    html = apply_visual_contract('<div class="sync-card-wrap"></div>')
    assert "min-height:9.25rem" in html
    assert "border-radius:22px!important" in html
    assert "padding:1rem 1.05rem!important" in html
    assert "transform:none!important" in html


def test_visual_contract_restores_mobile_speech_and_thought_tails() -> None:
    html = apply_visual_contract('<div class="sync-card-wrap"></div>')
    assert ".sync-card-wrap>.novel-frame-speech::before" in html
    assert ".sync-card-wrap>.novel-frame-thought::before" in html
    assert ".sync-card-wrap>.novel-frame-thought>.novel-thought-tail-dot" in html


def test_visual_contract_is_idempotent_and_preserves_content() -> None:
    original = '<section><p>Texto autoral intacto.</p></section>'
    once = apply_visual_contract(original)
    twice = apply_visual_contract(once)
    assert original in once
    assert twice == once
