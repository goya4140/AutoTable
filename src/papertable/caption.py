from __future__ import annotations

from typing import Any


def build_caption(spec: dict[str, Any]) -> str:
    """Return one identifying sentence; experimental detail belongs in the paper body."""
    caption = str(spec.get("caption") or spec.get("title") or "Results").strip()
    if caption and caption[-1] not in ".!?":
        caption += "."
    return caption
