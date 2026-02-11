"""
Test fixtures — sample data for all action types.
v1.1: Added flashcard samples.
"""

SAMPLE_BLOCKS = [
    {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Chapter 1: Clean Code", "annotations": {}}]}},
    {"type": "paragraph", "paragraph": {"rich_text": [
        {"plain_text": "Clean code is code that has been taken care of. ", "annotations": {}},
        {"plain_text": "Someone has taken the time to keep it simple.", "annotations": {"italic": True}},
    ]}},
    {"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Meaningful Names", "annotations": {}}]}},
    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "Use intention-revealing names", "annotations": {}}]}},
    {"type": "code", "code": {"rich_text": [{"plain_text": "def get_them():\n    return the_list", "annotations": {}}], "language": "python"}},
    {"type": "quote", "quote": {"rich_text": [{"plain_text": "The name of a variable should tell you why it exists.", "annotations": {}}]}},
    {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "Review naming conventions", "annotations": {}}], "checked": False}},
    {"type": "divider", "divider": {}},
]

SAMPLE_CHECKLIST_OUTPUT = {
    "task_title": "Clean Code - Chapter 1",
    "checklist": [
        {"section": "Meaningful Names", "items": [
            {"text": "Read Section 2.1 on intention-revealing names", "type": "read", "difficulty": 1, "estimated_minutes": 10, "depends_on": [], "acceptance_criteria": "Can explain why variable names matter"},
            {"text": "Extract 3 poor naming examples from your codebase", "type": "extract", "difficulty": 2, "estimated_minutes": 20, "depends_on": ["Read Section 2.1 on intention-revealing names"], "acceptance_criteria": "Listed 3 examples with improvements"},
        ]},
        {"section": "Functions", "items": [
            {"text": "Refactor one function to follow small functions principle", "type": "apply", "difficulty": 3, "estimated_minutes": 30, "depends_on": [], "acceptance_criteria": "Function < 20 lines, single responsibility"},
        ]},
    ]
}

SAMPLE_TREE_OUTPUT = {
    "scope": "Clean Code - Chapter 1",
    "nodes": [
        {"node_id": "node_root", "title": "Clean Code Fundamentals", "summary": "Core principles of writing clean, maintainable code.", "parent_id": None, "keywords": ["clean code", "readability"], "source_anchors": ["Chapter 1"]},
        {"node_id": "node_naming", "title": "Meaningful Names", "summary": "How to choose names that communicate intent.", "parent_id": "node_root", "keywords": ["naming", "variables"], "source_anchors": ["Section 2.1"]},
        {"node_id": "node_functions", "title": "Functions", "summary": "Principles for writing small, focused functions.", "parent_id": "node_root", "keywords": ["functions", "single responsibility"], "source_anchors": ["Chapter 3"]},
    ]
}

SAMPLE_PAGES_OUTPUT = {
    "pages": [{
        "title": "Meaningful Names",
        "node_id": "node_naming",
        "template": "concept",
        "sections": [
            {"heading": "Definition", "content_markdown": "Meaningful names are identifiers that **clearly communicate** purpose."},
            {"heading": "Key Principles", "content_markdown": "- Use intention-revealing names\n- Avoid disinformation\n- Make meaningful distinctions"},
        ],
        "review_questions": ["Why is `d` a poor variable name?", "What makes a name intention-revealing?"],
        "links_to": ["node_functions"],
    }]
}

SAMPLE_FLASHCARDS_OUTPUT = {
    "decks": [
        {
            "name": "Clean Code - Key Concepts",
            "description": "Core concepts from Chapter 1",
            "cards": [
                {
                    "front": "What is the main principle behind meaningful variable names?",
                    "back": "Variable names should reveal intent — they should tell you why the variable exists, what it does, and how it is used.",
                    "card_type": "basic",
                    "difficulty": 2,
                    "tags": ["naming", "clean-code"],
                    "context": "Chapter 2: Meaningful Names",
                    "source_ref": "Section 2.1",
                },
                {
                    "front": "The _____ principle states that functions should do one thing, do it well, and do it only.",
                    "back": "Single Responsibility",
                    "card_type": "cloze",
                    "difficulty": 1,
                    "tags": ["functions", "SRP"],
                },
                {
                    "front": "Single Responsibility Principle (SRP)",
                    "back": "A function or class should have one, and only one, reason to change.",
                    "card_type": "definition",
                    "difficulty": 1,
                    "tags": ["SRP", "principles"],
                },
                {
                    "front": "Clean code",
                    "back": "Code that is easy to understand, modify, and maintain. It reads like well-written prose.",
                    "card_type": "reverse",
                    "difficulty": 2,
                    "tags": ["definition", "clean-code"],
                },
            ]
        },
        {
            "name": "Clean Code - Practice Problems",
            "description": "Application and analysis questions",
            "cards": [
                {
                    "front": "Given `int d; // elapsed time in days`, how would you improve this variable name?",
                    "back": "Rename to `elapsedTimeInDays` or `daysSinceCreation` — the name should convey both the measurement and its unit.",
                    "card_type": "basic",
                    "difficulty": 3,
                    "tags": ["naming", "refactoring"],
                },
            ]
        },
    ]
}
