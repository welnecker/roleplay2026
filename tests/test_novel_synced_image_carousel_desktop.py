from __future__ import annotations

from services.novel_synced_image_carousel_desktop import desktop_accumulated_html


def _sample_html() -> str:
    return """
<style>
.sync-mobile{display:none;}
</style>
<div class="novel-frame-description">Cena</div>
<section class="sync-desktop">
  <div class="sync-desktop-image"><img src="active.webp"></div>
  <section class="novel-frame-track"><article>balões antigos</article></section>
</section>
<section class="sync-mobile">
  <div class="sync-mobile-track"><section class="sync-slide" data-slide="0"><div class="sync-image-wrap"><img src="a.webp"></div><div class="sync-card-wrap">A</div></section><section class="sync-slide" data-slide="1"><div class="sync-image-wrap"><img src="b.webp"></div><div class="sync-card-wrap">B</div></section></div>
  <div class="sync-controls">controles</div>
</section>
<script>mobile()</script>
"""


def test_desktop_uses_same_accumulated_image_balloon_slides_as_mobile() -> None:
    html = desktop_accumulated_html(_sample_html())

    desktop_start = html.index('<section class="sync-desktop">')
    mobile_start = html.index('<section class="sync-mobile">')
    desktop = html[desktop_start:mobile_start]

    assert 'class="sync-desktop-track"' in desktop
    assert desktop.count('class="sync-slide"') == 2
    assert 'src="a.webp"' in desktop
    assert 'src="b.webp"' in desktop
    assert ">A<" in desktop
    assert ">B<" in desktop
    assert "sync-desktop-image" not in desktop
    assert "novel-frame-track" not in desktop


def test_mobile_carousel_remains_present_and_unchanged() -> None:
    original = _sample_html()
    html = desktop_accumulated_html(original)

    original_mobile = original[original.index('<section class="sync-mobile">') :]
    transformed_mobile = html[html.index('<section class="sync-mobile">') :]

    assert transformed_mobile == original_mobile


def test_desktop_track_has_visible_horizontal_overflow_style() -> None:
    html = desktop_accumulated_html(_sample_html())

    assert ".sync-desktop-track{" in html
    assert "overflow-x:auto;" in html
    assert "scroll-snap-type:x proximity;" in html
    assert "scrollbar-gutter:stable;" in html


def test_transform_is_safe_when_synced_markup_is_absent() -> None:
    legacy = "<style></style><section>legacy</section>"

    assert desktop_accumulated_html(legacy) == legacy
