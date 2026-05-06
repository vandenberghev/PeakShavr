"""Tests for integration manifest metadata."""

from __future__ import annotations

import json
from pathlib import Path


def test_manifest_enforces_single_top_level_entry() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "custom_components" / "peakshavr" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest.get("single_config_entry") is True
