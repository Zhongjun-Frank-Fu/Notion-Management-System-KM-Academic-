"""
JSON schemas for validating LLM outputs.
v1.1: Added FLASHCARDS_SCHEMA.
"""

CHECKLIST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["task_title", "checklist"],
    "properties": {
        "task_title": {"type": "string"},
        "checklist": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object", "required": ["section", "items"],
                "properties": {
                    "section": {"type": "string"},
                    "items": {
                        "type": "array", "minItems": 1,
                        "items": {
                            "type": "object", "required": ["text", "type"],
                            "properties": {
                                "text": {"type": "string", "maxLength": 500},
                                "type": {"enum": ["read", "extract", "reflect", "apply"]},
                                "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
                                "estimated_minutes": {"type": "integer", "minimum": 1, "maximum": 480},
                                "depends_on": {"type": "array", "items": {"type": "string"}},
                                "acceptance_criteria": {"type": "string", "maxLength": 300},
                            },
                        },
                    },
                },
            },
        },
    },
}

TREE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["scope", "nodes"],
    "properties": {
        "scope": {"type": "string"},
        "nodes": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object", "required": ["node_id", "title", "summary"],
                "properties": {
                    "node_id": {"type": "string", "pattern": "^node_[a-z0-9_]+$"},
                    "title": {"type": "string", "maxLength": 200},
                    "summary": {"type": "string", "maxLength": 1000},
                    "parent_id": {"type": ["string", "null"]},
                    "keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                    "source_anchors": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

PAGES_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["pages"],
    "properties": {
        "pages": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object", "required": ["title", "template", "sections"],
                "properties": {
                    "title": {"type": "string", "maxLength": 200},
                    "node_id": {"type": ["string", "null"]},
                    "template": {"enum": ["concept", "summary", "study_guide"]},
                    "sections": {
                        "type": "array", "minItems": 1,
                        "items": {
                            "type": "object", "required": ["heading", "content_markdown"],
                            "properties": {
                                "heading": {"type": "string"},
                                "content_markdown": {"type": "string", "maxLength": 5000},
                            },
                        },
                    },
                    "review_questions": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                    "links_to": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

FLASHCARDS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["decks"],
    "properties": {
        "decks": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "cards"],
                "properties": {
                    "name": {"type": "string", "maxLength": 200},
                    "description": {"type": "string", "maxLength": 500},
                    "cards": {
                        "type": "array", "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["front", "back", "card_type"],
                            "properties": {
                                "front": {"type": "string", "maxLength": 500},
                                "back": {"type": "string", "maxLength": 2000},
                                "card_type": {"enum": ["basic", "cloze", "reverse", "definition"]},
                                "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
                                "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                                "context": {"type": "string", "maxLength": 500},
                                "source_ref": {"type": "string", "maxLength": 200},
                            },
                        },
                    },
                },
            },
        },
    },
}

SCHEMAS = {
    "checklist": CHECKLIST_SCHEMA,
    "tree": TREE_SCHEMA,
    "pages": PAGES_SCHEMA,
    "flashcards": FLASHCARDS_SCHEMA,
}


def get_schema(action_type: str) -> dict:
    schema = SCHEMAS.get(action_type)
    if not schema:
        raise ValueError(f"No schema for action type: {action_type}")
    return schema
