"""Compliance-Alert Layer.

Implements the contract's "compliance-alert layer": every analytical/AI output
that leaves the system carries an explicit *not-investment-advice* disclaimer,
source traceability, and a guardrail scan that flags non-compliant phrasing
(e.g. guaranteed returns, buy/sell recommendations) for human review.

This is intentionally lightweight and dependency-free so it can wrap any dict
payload returned by the API.
"""

from __future__ import annotations

import re
from typing import Any

DISCLAIMER_EN = (
    "This output is AI-assisted, decision-support content generated from public "
    "and user-provided data. It is NOT investment advice, a securities recommendation, "
    "a buy/sell/hold signal, or a guarantee of returns. Apply independent human review "
    "under your own compliance process before acting."
)
DISCLAIMER_ZH = (
    "本输出为基于公开信息及用户提供数据生成的 AI 辅助决策内容，不构成投资建议、证券推荐、"
    "买入/卖出/持有信号或收益保证。使用前请在贵机构合规流程下进行独立人工复核。"
)

# (regex, human-readable flag). Patterns are case-insensitive; Chinese included
# because this is a China-context product.
_RISKY_PATTERNS: list[tuple[str, str]] = [
    (r"guarantee[ds]?\s+(returns?|profit|gains?)", "claims_guaranteed_return"),
    (r"risk[\s-]*free", "claims_risk_free"),
    (r"\b(strong\s+)?(buy|sell)\b\s+(recommendation|rating|call)", "explicit_recommendation"),
    (r"\bwill\s+(definitely|certainly|surely)\s+(rise|go up|increase|moon)", "certainty_of_gain"),
    (r"保证(收益|盈利|回报|赚钱)", "claims_guaranteed_return_zh"),
    (r"稳赚|包赚|必涨|必赚|稳赢", "certainty_of_gain_zh"),
    (r"(建议|推荐)\s*(买入|卖出|加仓|清仓)", "explicit_recommendation_zh"),
    (r"无风险", "claims_risk_free_zh"),
]
_COMPILED = [(re.compile(pat, re.IGNORECASE), flag) for pat, flag in _RISKY_PATTERNS]


def disclaimer() -> dict[str, Any]:
    """Standard compliance block attached to every regulated output."""
    return {
        "not_investment_advice": True,
        "ai_generated": True,
        "requires_human_review": True,
        "disclaimer_en": DISCLAIMER_EN,
        "disclaimer_zh": DISCLAIMER_ZH,
    }


def scan_text(text: str) -> list[str]:
    """Return guardrail flags for any non-compliant phrasing in ``text``."""
    if not text:
        return []
    return sorted({flag for pattern, flag in _COMPILED if pattern.search(text)})


def scan_payload(value: Any) -> list[str]:
    """Recursively scan all string content in a payload for risky phrasing."""
    flags: set[str] = set()

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            flags.update(scan_text(node))
        elif isinstance(node, dict):
            for item in node.values():
                _walk(item)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    _walk(value)
    return sorted(flags)


def attach_compliance(payload: dict, *, sources: list | None = None,
                      scan: bool = True) -> dict:
    """Wrap an API payload with the compliance block (non-mutating).

    - ``sources``: list of source descriptors for traceability.
    - ``scan``: also run the guardrail scan and record any flags.
    """
    enriched = dict(payload)
    block = disclaimer()
    block["sources"] = sources if sources is not None else []
    block["flags"] = scan_payload(payload) if scan else []
    enriched["compliance"] = block
    return enriched


def source(kind: str, ref: str, detail: str | None = None) -> dict[str, str]:
    """Build a single source-traceability descriptor."""
    out = {"kind": kind, "ref": ref}
    if detail:
        out["detail"] = detail
    return out
