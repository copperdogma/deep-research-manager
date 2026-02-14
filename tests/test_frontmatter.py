"""Tests for YAML frontmatter parsing and writing."""

from deep_research import frontmatter


def test_parse_basic():
    text = '---\ntype: report\ntopic: "test"\n---\n\n# Hello\n\nBody text.'
    meta, body = frontmatter.parse(text)
    assert meta["type"] == "report"
    assert meta["topic"] == "test"
    assert "Body text." in body


def test_parse_no_frontmatter():
    text = "# Just a heading\n\nNo frontmatter here."
    meta, body = frontmatter.parse(text)
    assert meta == {}
    assert body == text


def test_parse_empty_frontmatter():
    text = "---\n---\n\nBody."
    meta, body = frontmatter.parse(text)
    assert meta == {}
    assert "Body." in body


def test_dump_roundtrip():
    original_meta = {"type": "report", "topic": "test"}
    original_body = "# Hello\n\nBody text."
    text = frontmatter.dump(original_meta, original_body)
    meta, body = frontmatter.parse(text)
    assert meta["type"] == "report"
    assert meta["topic"] == "test"
    assert "Body text." in body


def test_update_field():
    text = '---\ntype: report\ntopic: "old"\n---\n\nBody.'
    updated = frontmatter.update_field(text, "topic", "new")
    meta, body = frontmatter.parse(updated)
    assert meta["topic"] == "new"
    assert meta["type"] == "report"
    assert "Body." in body
