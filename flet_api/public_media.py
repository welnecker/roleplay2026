from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote


def public_story_media_url(
    package_id: str,
    category: str,
    filename: str | Path | Mapping[str, Any],
) -> str:
    """Return an R2 URL when external story media has been enabled."""

    base_url = os.getenv("ENTRECENAS_MEDIA_URL", "").strip().rstrip("/")
    safe_category = str(category or "").strip().strip("/")
    source = filename.get("path", "") if isinstance(filename, Mapping) else filename
    safe_filename = Path(source).name if source else ""
    if not base_url or not package_id or not safe_category or not safe_filename:
        return ""
    return (
        f"{base_url}/stories/{quote(package_id, safe='')}/"
        f"{quote(safe_category, safe='')}/{quote(safe_filename, safe='')}"
    )
