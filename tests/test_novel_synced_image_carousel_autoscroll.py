from services.novel_synced_image_carousel_autoscroll import enable_latest_slide_autoscroll


def test_autoscroll_moves_track_to_active_slide() -> None:
    html = """
<script>
const track = document.querySelector('.sync-mobile-track');
const slides = [];
let active = 2;
slides[active]?.scrollIntoView({behavior, inline:'start', block:'nearest'});
</script>
"""

    updated = enable_latest_slide_autoscroll(html)

    assert "scrollIntoView" not in updated
    assert "track.scrollTo({left: active * Math.max(track.clientWidth, 1), behavior});" in updated


def test_autoscroll_keeps_unrelated_html_unchanged() -> None:
    html = "<section>sem carrossel</section>"

    assert enable_latest_slide_autoscroll(html) == html
