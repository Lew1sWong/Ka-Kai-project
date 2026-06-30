"""Configurable LLM provider for MirrorQuant finance features.

Supports two providers, selected via the ``MIRRORQUANT_LLM_PROVIDER`` env var:

  - ``deepseek`` (default) — OpenAI-compatible API, matching the existing
    planner/executor usage in this repo.
  - ``anthropic`` — Claude via the official Anthropic SDK.

Both SDKs are imported lazily so importing this module never fails just because
one SDK or API key is missing. When the selected provider is not configured,
``complete()`` raises :class:`LLMUnavailable` — callers should catch it and fall
back to a non-LLM (retrieval-only / template) response so the product keeps
working offline / on-prem without keys.
"""

from __future__ import annotations

import json
import os
import re

from dotenv import load_dotenv

load_dotenv()

# --- provider selection -----------------------------------------------------
PROVIDER = os.getenv("MIRRORQUANT_LLM_PROVIDER", "deepseek").strip().lower()

# DeepSeek (OpenAI-compatible) — same pattern as planner.py / executor.py
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
DEEPSEEK_MODEL = os.getenv("MIRRORQUANT_DEEPSEEK_MODEL", "deepseek-chat").strip()

# Anthropic Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("MIRRORQUANT_ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()


class LLMUnavailable(RuntimeError):
    """Raised when the selected LLM provider has no usable API key/SDK."""


def provider_name() -> str:
    return PROVIDER


def is_configured() -> bool:
    """True if the *currently selected* provider has an API key."""
    if PROVIDER == "anthropic":
        return bool(ANTHROPIC_API_KEY)
    return bool(DEEPSEEK_API_KEY)


def _extract_json(text: str) -> str:
    """Pull the first JSON object out of an LLM reply (handles code fences)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    return brace.group(0) if brace else text


async def _complete_deepseek(system: str, user: str, *, json_mode: bool,
                             temperature: float, max_tokens: int) -> str:
    if not DEEPSEEK_API_KEY:
        raise LLMUnavailable("DEEPSEEK_API_KEY is not set")
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise LLMUnavailable(f"openai SDK not installed: {exc}") from exc

    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    kwargs: dict = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


async def _complete_anthropic(system: str, user: str, *, json_mode: bool,
                              temperature: float, max_tokens: int) -> str:
    if not ANTHROPIC_API_KEY:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise LLMUnavailable(f"anthropic SDK not installed: {exc}") from exc

    if json_mode:
        system = f"{system}\n\nRespond with a single valid JSON object and nothing else."
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model=ANTHROPIC_MODEL,
        system=system,
        messages=[{"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
    return "".join(parts)


async def complete(system: str, user: str, *, json_mode: bool = False,
                   temperature: float = 0.3, max_tokens: int = 1500) -> str:
    """Single-shot completion against the configured provider.

    Raises ``LLMUnavailable`` if the provider has no key/SDK so callers can
    degrade gracefully.
    """
    if PROVIDER == "anthropic":
        return await _complete_anthropic(
            system, user, json_mode=json_mode, temperature=temperature, max_tokens=max_tokens
        )
    return await _complete_deepseek(
        system, user, json_mode=json_mode, temperature=temperature, max_tokens=max_tokens
    )


async def complete_json(system: str, user: str, *, temperature: float = 0.2,
                        max_tokens: int = 1500) -> dict:
    """Completion that returns a parsed JSON object."""
    text = await complete(
        system, user, json_mode=True, temperature=temperature, max_tokens=max_tokens
    )
    try:
        return json.loads(_extract_json(text))
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMUnavailable(f"LLM did not return valid JSON: {exc}") from exc
