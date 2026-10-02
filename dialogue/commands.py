"""
commands.py — STUDENT B OWNS THIS FILE. Bonus command types.

Commands that only ever flow parser -> CommandQueue -> executor (all inside
dialogue/), so they live here instead of core/schema.py. The queue doesn't
care about the type.
"""

from dataclasses import dataclass


@dataclass
class LookCommand:
    """Answer a question about what the robot currently sees (VLM)."""
    question: str
    kind: str = "look"
