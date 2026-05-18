"""
Persistent user memory backed by a JSON file.

Stores:
  preferred_style       — e.g. "hand-drawn 2D sketch, warm tones"
  preferred_resolution  — {"width": 1280, "height": 720}
  language              — user's preferred language, e.g. "zh" or "en"
  successful_prompts    — ring-buffer of the last MAX_PROMPTS enhanced prompts
                          that produced an accepted video (most useful for future
                          planner context)
  notes                 — freeform string the user can set for persistent hints

`as_context_str()` produces a compact block injected into the planner prompt
so DeepSeek is aware of past preferences without seeing the full history.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_PROMPTS = 10   # ring-buffer capacity for successful prompts


class UserMemory:
    def __init__(self, path: Path | str = "user_memory.json") -> None:
        self._path = Path(path)
        self.preferred_style: str           = ""
        self.preferred_resolution: dict     = {"width": 1280, "height": 720}
        self.language: str                  = "en"
        self.successful_prompts: deque[str] = deque(maxlen=_MAX_PROMPTS)
        self.notes: str                     = ""

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> "UserMemory":
        if not self._path.exists():
            return self
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self.preferred_style      = raw.get("preferred_style", "")
            self.preferred_resolution = raw.get("preferred_resolution", {"width": 1280, "height": 720})
            self.language             = raw.get("language", "en")
            self.successful_prompts   = deque(raw.get("successful_prompts", []), maxlen=_MAX_PROMPTS)
            self.notes                = raw.get("notes", "")
            logger.debug("Memory loaded from %s", self._path)
        except Exception:
            logger.warning("Could not load memory from %s — starting fresh", self._path, exc_info=True)
        return self

    def save(self) -> None:
        data = {
            "preferred_style":      self.preferred_style,
            "preferred_resolution": self.preferred_resolution,
            "language":             self.language,
            "successful_prompts":   list(self.successful_prompts),
            "notes":                self.notes,
        }
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Memory saved to %s", self._path)

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def record_success(self, enhanced_prompt: str) -> None:
        """Call after a successful run to remember the prompt that worked."""
        if enhanced_prompt and enhanced_prompt not in self.successful_prompts:
            self.successful_prompts.append(enhanced_prompt)
            self.save()

    def update(self, **kwargs) -> None:
        """Bulk-update known fields and persist. Unknown keys are ignored."""
        allowed = {"preferred_style", "preferred_resolution", "language", "notes"}
        for k, v in kwargs.items():
            if k in allowed:
                setattr(self, k, v)
        self.save()

    # ------------------------------------------------------------------
    # Planner context string
    # ------------------------------------------------------------------

    def as_context_str(self) -> str:
        """Return a compact block for injection into the planner system prompt."""
        lines = ["[User Memory]"]
        if self.preferred_style:
            lines.append(f"- Preferred style: {self.preferred_style}")
        res = self.preferred_resolution
        lines.append(f"- Preferred resolution: {res.get('width', 1280)}×{res.get('height', 720)}")
        if self.language:
            lines.append(f"- Language: {self.language}")
        if self.notes:
            lines.append(f"- Notes: {self.notes}")
        if self.successful_prompts:
            recent = list(self.successful_prompts)[-3:]  # last 3 only to keep prompt short
            lines.append("- Recent successful prompts (use as style reference, not copy-paste):")
            for p in recent:
                lines.append(f"    • {p}")
        return "\n".join(lines)
