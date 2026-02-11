"""
LLM Client — wraps Anthropic Claude API for structured JSON generation.
Handles prompt loading, generation, schema validation, and repair retries.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

import anthropic
import jsonschema

from app.config import settings
from app.llm.schemas import get_schema

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"


class LLMClient:
    """Claude API wrapper for structured knowledge generation."""

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model

    def load_prompt(self, action_type: str) -> str:
        """Load a versioned prompt template from disk."""
        version = settings.prompt_version.lower().replace("-", "_").replace(".", "_")
        # Try versioned filename first, fall back to v1
        for suffix in [f"_{version}", "_v1"]:
            path = PROMPT_DIR / f"{action_type}{suffix}.txt"
            if path.exists():
                return path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"No prompt template found for {action_type}")

    def generate(
        self,
        action_type: str,
        content: str,
        metadata_header: str = "",
    ) -> tuple[dict, int, int]:
        """
        Generate structured JSON output via Claude.

        Returns:
            (parsed_json, input_tokens, output_tokens)

        Raises:
            SchemaValidationError if output fails validation after repair.
        """
        prompt_template = self.load_prompt(action_type)
        schema = get_schema(action_type)

        # Build the user message
        user_message = f"{metadata_header}\n\n{content}" if metadata_header else content

        # System prompt with schema constraint
        system_prompt = (
            f"{prompt_template}\n\n"
            f"---\n"
            f"OUTPUT INSTRUCTIONS:\n"
            f"- Return ONLY valid JSON, no markdown fences, no explanation.\n"
            f"- The JSON must conform to this schema:\n"
            f"```json\n{json.dumps(schema, indent=2)}\n```\n"
        )

        # First attempt
        raw, in_tok, out_tok = self._call_claude(system_prompt, user_message)
        parsed = self._parse_json(raw)

        if parsed is not None:
            errors = self._validate(parsed, schema)
            if not errors:
                return parsed, in_tok, out_tok

            # Repair attempt
            logger.warning(f"Schema validation failed, attempting repair. Errors: {errors}")
            parsed, repair_in, repair_out = self._repair(raw, errors, schema)
            in_tok += repair_in
            out_tok += repair_out
            if parsed is not None:
                return parsed, in_tok, out_tok

        raise SchemaValidationError(
            f"LLM output failed schema validation after repair attempt. "
            f"Raw output (truncated): {raw[:500]}"
        )

    def _call_claude(self, system: str, user_message: str) -> tuple[str, int, int]:
        """Make a Claude API call and return (text, input_tokens, output_tokens)."""
        response = self._client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        usage = response.usage
        return text.strip(), usage.input_tokens, usage.output_tokens

    def _parse_json(self, raw: str) -> Optional[dict]:
        """Parse JSON from LLM output, stripping markdown fences if present."""
        cleaned = raw.strip()
        # Remove ```json ... ``` wrapper
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]  # remove opening ```json
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}")
            return None

    def _validate(self, data: dict, schema: dict) -> list[str]:
        """Validate JSON against schema. Returns list of error messages."""
        errors = []
        validator = jsonschema.Draft7Validator(schema)
        for error in validator.iter_errors(data):
            errors.append(f"{error.json_path}: {error.message}")
        return errors

    def _repair(
        self, raw_output: str, errors: list[str], schema: dict
    ) -> tuple[Optional[dict], int, int]:
        """
        Attempt to repair invalid JSON via a follow-up Claude call.
        Returns (parsed_json_or_None, input_tokens, output_tokens).
        """
        repair_prompt = (
            "The following JSON output failed schema validation.\n\n"
            f"Errors:\n" + "\n".join(f"- {e}" for e in errors[:10]) + "\n\n"
            f"Original output:\n{raw_output[:6000]}\n\n"
            f"Schema:\n```json\n{json.dumps(schema, indent=2)}\n```\n\n"
            "Please fix the JSON to conform to the schema. "
            "Return ONLY the fixed JSON, no explanation."
        )

        raw, in_tok, out_tok = self._call_claude(
            "You are a JSON repair assistant. Return only valid JSON.",
            repair_prompt,
        )

        parsed = self._parse_json(raw)
        if parsed is not None:
            remaining_errors = self._validate(parsed, schema)
            if not remaining_errors:
                logger.info("Repair succeeded")
                return parsed, in_tok, out_tok
            logger.warning(f"Repair still has errors: {remaining_errors}")

        return None, in_tok, out_tok


class SchemaValidationError(Exception):
    """Raised when LLM output cannot be validated even after repair."""
    pass


# Singleton
llm = LLMClient()
