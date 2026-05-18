"""
Hand-drawn Animation Agent — Orchestrator
==========================================
Single public entry point: run_agent(user_request, assets) -> AgentResult

Pipeline:
  1. Load persistent user memory (user_memory.json)
  2. Planner  — DeepSeek returns a JSON plan [{tool, inputs, reason}, …]
  3. Executor — walks each step, piping outputs into a rolling context dict
  4. Memory   — persist the enhanced_prompt that produced a successful video
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from executor import execute_plan
from memory import UserMemory
from planner import Plan, make_plan

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    video_url:       Optional[str]  = None
    plan:            list[dict]     = field(default_factory=list)  # serialisable plan summary
    enhanced_prompt: Optional[str]  = None
    final_context:   dict[str, Any] = field(default_factory=dict)
    error:           Optional[str]  = None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def run_agent(
    user_request: str,
    assets: dict[str, Any],
    memory_path: Path | str = "user_memory.json",
) -> AgentResult:
    """
    Run the full agent pipeline.

    Args:
        user_request:  Natural-language request (any language).
        assets:        Pre-resolved inputs available to the tools, e.g.:
                         image_to_video  → {"image_url": "https://…"}
                         audio_portrait  → {"image_url": "…", "audio_url": "…"}
                         chained         → {"image_url": "…", "audio_url": "…"}
                       Always include "user_description" for prompt enhancement.
        memory_path:   Path for the persistent JSON memory file.

    Returns:
        AgentResult — check `.error` first; `.video_url` populated on success.
    """
    # 1. Memory
    memory = UserMemory(memory_path).load()

    # 2. Plan
    available_assets: set[str] = set(assets.keys())
    plan: Plan = await make_plan(
        user_request=user_request,
        memory=memory,
        available_assets=available_assets,
        deepseek_api_key=DEEPSEEK_API_KEY,
    )
    plan_summary = [
        {"tool": s.tool, "inputs": s.inputs, "reason": s.reason}
        for s in plan
    ]
    logger.info("Executing plan: %s", plan_summary)

    # 3. Execute
    initial_ctx: dict[str, Any] = {"user_description": user_request, **assets}
    final_ctx = await execute_plan(plan, initial_ctx, DEEPSEEK_API_KEY)

    # 4. Persist memory
    if ep := final_ctx.get("enhanced_prompt"):
        memory.record_success(ep)

    return AgentResult(
        video_url=final_ctx.get("video_url"),
        plan=plan_summary,
        enhanced_prompt=final_ctx.get("enhanced_prompt"),
        final_context=final_ctx,
    )
