from __future__ import annotations

from flet_client.frame_state import VisualEntry, VisualFrame
from flet_client.story_end_screen import story_end_message


def test_story_end_message_uses_authored_terminal_speech() -> None:
    frame = VisualFrame(
        frame_id="capitulo1_fim_historia",
        description="",
        entries=(
            VisualEntry(
                kind="fala",
                actor="mary",
                visible_name="Mary",
                body="Gostou dessa aventura, Janio? Aposto que sim. Te espero na próxima. Tchauzinho...",
            ),
        ),
    )

    assert story_end_message(frame) == (
        "Gostou dessa aventura, Janio? Aposto que sim. Te espero na próxima. Tchauzinho..."
    )
