"""Tests for packaging dependency constraints."""

from __future__ import annotations

try:
    import tomllib
except ImportError:
    import tomli as tomllib
from pathlib import Path


def _load_pyproject() -> dict:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    return tomllib.loads(pyproject.read_text())


def test_openai_extra_pins_httpx_below_028():
    data = _load_pyproject()
    openai_deps = data["project"]["optional-dependencies"]["openai"]
    assert "httpx<0.28" in openai_deps


def test_all_extra_pins_httpx_below_028():
    data = _load_pyproject()
    all_deps = data["project"]["optional-dependencies"]["all"]
    assert "httpx<0.28" in all_deps

