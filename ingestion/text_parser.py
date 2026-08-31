"""Normalization helpers for pasted and extracted text."""

import re


_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+")
_EXCESSIVE_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Normalize whitespace while retaining paragraph boundaries."""
    if not text or not text.strip():
        raise ValueError("Source text cannot be empty.")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(
        _HORIZONTAL_WHITESPACE.sub(" ", line).strip() for line in normalized.splitlines()
    )
    normalized = _EXCESSIVE_BLANK_LINES.sub("\n\n", normalized)
    return normalized.strip()

