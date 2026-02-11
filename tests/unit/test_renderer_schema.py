"""Unit tests for renderer and schema validation. v1.1: flashcard tests."""

import pytest
import jsonschema
from app.notion.renderer import render_checklist, render_tree, render_knowledge_page, render_flashcards, render_flashcards_csv
from app.llm.schemas import CHECKLIST_SCHEMA, TREE_SCHEMA, PAGES_SCHEMA, FLASHCARDS_SCHEMA
from tests.fixtures.samples import SAMPLE_CHECKLIST_OUTPUT, SAMPLE_TREE_OUTPUT, SAMPLE_PAGES_OUTPUT, SAMPLE_FLASHCARDS_OUTPUT


# ── Schema Tests ────────────────────────────────────────────────────

class TestChecklistSchema:
    def test_valid(self):
        jsonschema.validate(SAMPLE_CHECKLIST_OUTPUT, CHECKLIST_SCHEMA)
    def test_missing_title(self):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"checklist": []}, CHECKLIST_SCHEMA)
    def test_invalid_type(self):
        bad = {"task_title": "T", "checklist": [{"section": "S", "items": [{"text": "x", "type": "bad"}]}]}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, CHECKLIST_SCHEMA)
    def test_empty(self):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"task_title": "T", "checklist": []}, CHECKLIST_SCHEMA)


class TestTreeSchema:
    def test_valid(self):
        jsonschema.validate(SAMPLE_TREE_OUTPUT, TREE_SCHEMA)
    def test_bad_node_id(self):
        bad = {"scope": "X", "nodes": [{"node_id": "BAD", "title": "X", "summary": "Y", "parent_id": None}]}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, TREE_SCHEMA)


class TestPagesSchema:
    def test_valid(self):
        jsonschema.validate(SAMPLE_PAGES_OUTPUT, PAGES_SCHEMA)
    def test_bad_template(self):
        bad = {"pages": [{**SAMPLE_PAGES_OUTPUT["pages"][0], "template": "bad"}]}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, PAGES_SCHEMA)


class TestFlashcardsSchema:
    def test_valid(self):
        jsonschema.validate(SAMPLE_FLASHCARDS_OUTPUT, FLASHCARDS_SCHEMA)
    def test_empty_decks(self):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"decks": []}, FLASHCARDS_SCHEMA)
    def test_empty_cards(self):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"decks": [{"name": "D", "cards": []}]}, FLASHCARDS_SCHEMA)
    def test_bad_card_type(self):
        bad = {"decks": [{"name": "D", "cards": [{"front": "Q", "back": "A", "card_type": "wrong"}]}]}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, FLASHCARDS_SCHEMA)
    def test_all_card_types(self):
        for ct in ["basic", "cloze", "reverse", "definition"]:
            jsonschema.validate({"decks": [{"name": "D", "cards": [{"front": "Q", "back": "A", "card_type": ct}]}]}, FLASHCARDS_SCHEMA)
    def test_difficulty_bounds(self):
        for d in [0, 6]:
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate({"decks": [{"name": "D", "cards": [{"front": "Q", "back": "A", "card_type": "basic", "difficulty": d}]}]}, FLASHCARDS_SCHEMA)


# ── Renderer Tests ──────────────────────────────────────────────────

class TestChecklistRenderer:
    def test_basic(self):
        blocks = render_checklist(SAMPLE_CHECKLIST_OUTPUT)
        assert sum(1 for b in blocks if b["type"] == "to_do") == 3
        assert any(b["type"] == "heading_2" for b in blocks)
    def test_criteria(self):
        blocks = render_checklist(SAMPLE_CHECKLIST_OUTPUT)
        text = [b for b in blocks if b["type"] == "to_do"][0]["to_do"]["rich_text"][0]["text"]["content"]
        assert "\u2192" in text


class TestTreeRenderer:
    def test_basic(self):
        blocks = render_tree(SAMPLE_TREE_OUTPUT)
        assert any(b["type"] == "heading_1" for b in blocks)
        assert any(b["type"] == "heading_2" for b in blocks)
    def test_empty(self):
        assert render_tree({"scope": "X", "nodes": []}) == []


class TestFlashcardsRenderer:
    def test_blocks(self):
        blocks = render_flashcards(SAMPLE_FLASHCARDS_OUTPUT)
        types = {b["type"] for b in blocks}
        assert "heading_2" in types
        assert "heading_3" in types
        assert "paragraph" in types
        assert "divider" in types

    def test_csv_header(self):
        csv = render_flashcards_csv(SAMPLE_FLASHCARDS_OUTPUT)
        assert csv.startswith("Front,Back,Tags,Deck,Type,Difficulty")

    def test_csv_row_count(self):
        csv = render_flashcards_csv(SAMPLE_FLASHCARDS_OUTPUT)
        lines = csv.strip().split("\n")
        assert len(lines) == 6  # header + 5 cards

    def test_csv_content(self):
        csv = render_flashcards_csv(SAMPLE_FLASHCARDS_OUTPUT)
        assert "Single Responsibility" in csv
        assert "Clean Code - Key Concepts" in csv

    def test_difficulty_emoji_in_heading(self):
        blocks = render_flashcards(SAMPLE_FLASHCARDS_OUTPUT)
        h3s = [b["heading_3"]["rich_text"][0]["text"]["content"] for b in blocks if b["type"] == "heading_3"]
        assert any(any(e in t for e in ["\U0001f7e2", "\U0001f7e1", "\U0001f7e0"]) for t in h3s)
