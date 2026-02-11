"""Unit tests for Notion block normalizer."""

import pytest
from app.notion.normalizer import normalize_blocks, build_llm_input, _rich_text_list
from app.models import TaskMetadata, NoteEntry


class TestRichTextList:
    def test_plain_text(self):
        assert _rich_text_list([{"plain_text": "Hello", "annotations": {}}]) == "Hello"

    def test_bold(self):
        assert _rich_text_list([{"plain_text": "bold", "annotations": {"bold": True}}]) == "**bold**"

    def test_italic(self):
        assert _rich_text_list([{"plain_text": "it", "annotations": {"italic": True}}]) == "*it*"

    def test_code(self):
        assert _rich_text_list([{"plain_text": "cd", "annotations": {"code": True}}]) == "`cd`"

    def test_link(self):
        assert _rich_text_list([{"plain_text": "click", "annotations": {}, "href": "https://x.com"}]) == "[click](https://x.com)"

    def test_multiple(self):
        rt = [{"plain_text": "Hi ", "annotations": {}}, {"plain_text": "bold", "annotations": {"bold": True}}]
        assert _rich_text_list(rt) == "Hi **bold**"


class TestNormalizeBlocks:
    def _b(self, btype, text, **kw):
        return {"type": btype, btype: {"rich_text": [{"plain_text": text, "annotations": {}}], **kw}}

    def test_headings(self):
        assert normalize_blocks([self._b("heading_1", "T")]) == "# T"
        assert normalize_blocks([self._b("heading_2", "T")]) == "## T"
        assert normalize_blocks([self._b("heading_3", "T")]) == "### T"

    def test_paragraph(self):
        assert normalize_blocks([self._b("paragraph", "text")]) == "text"

    def test_bullet(self):
        assert normalize_blocks([self._b("bulleted_list_item", "item")]) == "- item"

    def test_todo(self):
        assert "[ ]" in normalize_blocks([self._b("to_do", "task", checked=False)])
        assert "[x]" in normalize_blocks([self._b("to_do", "done", checked=True)])

    def test_code(self):
        result = normalize_blocks([self._b("code", "print(1)", language="python")])
        assert "```python" in result

    def test_divider(self):
        assert normalize_blocks([{"type": "divider", "divider": {}}]) == "---"

    def test_nested(self):
        blocks = [{"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "P", "annotations": {}}]},
                   "has_children": True, "children": [{"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "C", "annotations": {}}]}}]}]
        result = normalize_blocks(blocks)
        assert "- P" in result and "  - C" in result


class TestBuildLLMInput:
    def test_basic(self):
        result = build_llm_input("content", TaskMetadata(title="Test"))
        assert "title: Test" in result and "content" in result

    def test_with_notes(self):
        notes = [NoteEntry(note_id="n1", title="Note 1", content="A quote", note_type="Quote", tags=["t1"])]
        result = build_llm_input("content", TaskMetadata(title="T"), notes=notes)
        assert "Linked Notes" in result
        assert "Note 1" in result
        assert "A quote" in result
        assert "Quote" in result
