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


def test_mobile_carousel_markup_remains_present() -> None:
    html = desktop_accumulated_html(_sample_html())

    assert '<section class="sync-mobile">' in html
    assert 'class="sync-mobile-track"' in html
    assert '<script>mobile()</script>' in html


def test_desktop_track_has_visible_horizontal_overflow_style() -> None:
    html = desktop_accumulated_html(_sample_html())

    assert ".sync-desktop-track{" in html
    assert "align-items:flex-start;" in html
    assert "overflow-x:auto;" in html
    assert "scroll-snap-type:x proximity;" in html
    assert "scrollbar-gutter:stable;" in html


def test_desktop_focuses_newest_slide_when_iframe_renders() -> None:
    html = desktop_accumulated_html(_sample_html())

    assert "track.scrollWidth - track.clientWidth" in html
    assert "track.scrollTo({left: latest, behavior: 'auto'})" in html
    assert "fitTrackToSlide(slides.length - 1);" in html


def test_active_slide_controls_desktop_track_height() -> None:
    html = desktop_accumulated_html(_sample_html())

    assert "const visibleSlideIndex = () =>" in html
    assert "const fitTrackToSlide = (index = visibleSlideIndex()) =>" in html
    assert "slide.getBoundingClientRect().height" in html
    assert "track.style.height = `${targetHeight}px`" in html
    assert "track.addEventListener('scroll'" in html
    assert "setTimeout(() => fitTrackToSlide(), 90)" in html


def test_new_reveal_scrolls_component_vertically_into_reading_position() -> None:
    html = desktop_accumulated_html(_sample_html())

    assert "const scrollPageToCarousel = () =>" in html
    assert "const frame = window.frameElement" in html
    assert "frame.scrollIntoView({behavior: 'smooth', block: 'start', inline: 'nearest'})" in html
    assert "scrollPageToCarousel();" in html


def test_manual_carousel_scroll_only_recalibrates_height() -> None:
    html = desktop_accumulated_html(_sample_html())

    scroll_block = html[html.index("track.addEventListener('scroll'") : html.index("track.querySelectorAll('img')")]
    assert "fitTrackToSlide" in scroll_block
    assert "scrollPageToCarousel" not in scroll_block
    assert "scrollLatest" not in scroll_block


def test_image_load_rechecks_width_and_active_height_without_vertical_jump() -> None:
    html = desktop_accumulated_html(_sample_html())

    image_load_block = html[html.index("track.querySelectorAll('img')") :]
    assert "image.addEventListener('load', () =>" in image_load_block
    assert "scrollLatest();" in image_load_block
    assert "fitTrackToSlide();" in image_load_block
    assert "scrollPageToCarousel" not in image_load_block


def test_resize_observer_keeps_height_in_sync_with_late_layout_changes() -> None:
    html = desktop_accumulated_html(_sample_html())

    assert "typeof ResizeObserver !== 'undefined'" in html
    assert "new ResizeObserver(() => fitTrackToSlide())" in html
    assert "slides.forEach((slide) => observer.observe(slide))" in html


def test_transform_is_idempotent() -> None:
    once = desktop_accumulated_html(_sample_html())
    twice = desktop_accumulated_html(once)

    assert twice.count("const scrollLatest = () =>") == 1
    assert twice.count("const scrollPageToCarousel = () =>") == 1
    assert twice.count("const fitTrackToSlide =") == 1


def test_transform_is_safe_when_synced_markup_is_absent() -> None:
    legacy = "<style></style><section>legacy</section>"

    assert desktop_accumulated_html(legacy) == legacy