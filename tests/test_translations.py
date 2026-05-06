"""Tests for translation wiring."""

from __future__ import annotations

import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_reconfigure_successful_translation_is_not_placeholder() -> None:
    root = Path(__file__).resolve().parents[1]
    strings = _load_json(root / "custom_components" / "peakshavr" / "strings.json")
    english = _load_json(
        root / "custom_components" / "peakshavr" / "translations" / "en.json"
    )

    strings_value = strings["config_subentries"]["load"]["abort"]["reconfigure_successful"]
    en_value = english["config_subentries"]["load"]["abort"]["reconfigure_successful"]

    assert "[%key:" not in strings_value
    assert "[%key:" not in en_value
