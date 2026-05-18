"""
Tool registry — one class per Volcengine capability.

Each tool:
  • has a `name`, `description`, and `input_schema` consumed by the planner
  • implements  async run(ctx: dict) -> dict
  • handles its own submit + poll loop internally

Shared context dict keys produced by each tool:
  image_to_video  → video_url, task_id
  audio_portrait  → video_url, task_id
  video_effects   → video_url, task_id

TODO: verify all req_key values against live docs before going to production:
  https://www.volcengine.com/docs/85621/1783678   (image_to_video)
  https://www.volcengine.com/docs/86081/1804513   (audio_portrait)
  https://www.volcengine.com/docs/86081/1804543   (video_effects)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod

from volcengine.visual.VisualService import VisualService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared Volcengine helpers
# ---------------------------------------------------------------------------

_STATUS_DONE    = 2
_STATUS_FAILED  = 3
_POLL_INTERVAL  = 5    # seconds between status checks
_MAX_TRIES      = 72   # 72 × 5 s = 6 min ceiling


def _make_svc() -> VisualService:
    svc = VisualService()
    svc.set_ak(os.environ["VOLC_ACCESSKEY"])
    svc.set_sk(os.environ["VOLC_SECRETKEY"])
    return svc


def _assert_ok(resp: dict, ctx: str) -> None:
    code = resp.get("code")
    if code != 10000:
        raise RuntimeError(
            f"[{ctx}] Volcengine error code={code} "
            f"msg='{resp.get('message')}' req_id={resp.get('request_id')}"
        )


def _extract_video_url(data: dict) -> str:
    for info in data.get("video_infos") or []:
        if url := info.get("video_url"):
            return url
    raw = data.get("resp_data", "{}")
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    if url := parsed.get("video_url"):
        return url
    raise RuntimeError(f"No video_url found in response data: {data}")


async def _submit_and_poll(body: dict, label: str) -> dict:
    """
    Submit a Volcengine async task and poll until done.
    Returns {"task_id": str, "data": dict} on success.
    """
    loop = asyncio.get_running_loop()

    # Submit
    resp = await loop.run_in_executor(None, lambda: _make_svc().cv_submit_task(body))
    _assert_ok(resp, f"{label}/submit")
    task_id = resp["data"]["task_id"]
    logger.info("%s submitted  task_id=%s", label, task_id)

    # Poll
    poll_body = {"req_key": body["req_key"], "task_id": task_id}
    for attempt in range(1, _MAX_TRIES + 1):
        poll_resp = await loop.run_in_executor(None, lambda: _make_svc().cv_get_result(poll_body))
        _assert_ok(poll_resp, f"{label}/poll")
        data = poll_resp["data"]
        status = data.get("status")

        if status == _STATUS_DONE:
            logger.info("%s done  task_id=%s", label, task_id)
            return {"task_id": task_id, "data": data}

        if status == _STATUS_FAILED:
            reason = data.get("message") or data.get("err_msg", "unknown")
            raise RuntimeError(f"{label} failed  task_id={task_id}  reason={reason}")

        logger.debug("%s attempt=%d/%d status=%s", label, attempt, _MAX_TRIES, status)
        await asyncio.sleep(_POLL_INTERVAL)

    raise TimeoutError(
        f"{label} task_id={task_id} timed out after {_MAX_TRIES * _POLL_INTERVAL}s"
    )


# ---------------------------------------------------------------------------
# Base tool interface
# ---------------------------------------------------------------------------

class BaseTool(ABC):
    name: str         # key used in plan JSON
    description: str  # injected verbatim into planner system prompt
    input_schema: dict  # JSON Schema for planner-settable overrides only

    @abstractmethod
    async def run(self, ctx: dict) -> dict:
        """
        Execute the tool against the accumulated execution context.
        Returns a dict whose keys are merged back into ctx.
        """


# ---------------------------------------------------------------------------
# Tool 1 — Image-to-Video  (JiMeng 3.0 Pro)
# docs: https://www.volcengine.com/docs/85621/1783678
# ---------------------------------------------------------------------------

class ImageToVideoTool(BaseTool):
    name = "image_to_video"
    description = (
        "Animates a hand-drawn sketch into a short video using JiMeng 3.0 Pro. "
        "Requires context keys: image_url (str), enhanced_prompt (str). "
        "Optional overrides: duration (4 or 8 s), width (int), height (int). "
        "Produces: video_url."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "duration": {"type": "integer", "enum": [4, 8], "default": 4},
            "width":    {"type": "integer", "default": 1280},
            "height":   {"type": "integer", "default": 720},
        },
        "required": [],
    }

    # TODO: confirm req_key with https://www.volcengine.com/docs/85621/1783678
    _REQ_KEY = "jimeng_ti2v_v30_pro"

    async def run(self, ctx: dict) -> dict:
        body = {
            "req_key":    self._REQ_KEY,
            "prompt":     ctx["enhanced_prompt"],
            "image_urls": [ctx["image_url"]],
            "duration":   ctx.get("duration", 4),
            "width":      ctx.get("width", 1280),
            "height":     ctx.get("height", 720),
        }
        result = await _submit_and_poll(body, "ImageToVideo")
        return {
            "video_url": _extract_video_url(result["data"]),
            "task_id":   result["task_id"],
        }


# ---------------------------------------------------------------------------
# Tool 2 — Audio-driven Portrait Video
# docs: https://www.volcengine.com/docs/86081/1804513
#
# Two-step flow (handled internally as one logical tool):
#   Step A: register the portrait image  → portrait_id
#   Step B: submit video generation with portrait_id + audio_url  → video_url
# ---------------------------------------------------------------------------

class AudioPortraitTool(BaseTool):
    name = "audio_portrait"
    description = (
        "Creates a talking-head / lip-sync video from a still portrait photo and an audio clip. "
        "Requires context keys: image_url (str), audio_url (str). "
        "Produces: video_url."
    )
    input_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    # TODO: confirm both req_keys with https://www.volcengine.com/docs/86081/1804513
    _REQ_KEY_CREATE = "jimeng_audio_driven_img_create"
    _REQ_KEY_VIDEO  = "jimeng_audio_driven_video_gen"

    async def run(self, ctx: dict) -> dict:
        loop = asyncio.get_running_loop()

        # Step A: register portrait image → portrait_id
        create_body = {
            "req_key":   self._REQ_KEY_CREATE,
            "image_url": ctx["image_url"],
        }
        create_resp = await loop.run_in_executor(
            None, lambda: _make_svc().cv_submit_task(create_body)
        )
        _assert_ok(create_resp, "AudioPortrait/create")
        create_data = create_resp.get("data", {})

        # The create call may be synchronous (portrait_id returned immediately)
        # or async (task_id returned, then poll separately). Handle both.
        portrait_id = create_data.get("portrait_id")
        if not portrait_id:
            create_task_id = create_data.get("task_id")
            if not create_task_id:
                raise RuntimeError(
                    f"AudioPortrait: neither portrait_id nor task_id in create response: {create_data}"
                )
            logger.info("AudioPortrait create is async, polling task_id=%s", create_task_id)
            poll_body = {"req_key": self._REQ_KEY_CREATE, "task_id": create_task_id}
            for attempt in range(1, _MAX_TRIES + 1):
                pr = await loop.run_in_executor(None, lambda: _make_svc().cv_get_result(poll_body))
                _assert_ok(pr, "AudioPortrait/create/poll")
                d = pr["data"]
                if d.get("status") == _STATUS_DONE:
                    portrait_id = d.get("portrait_id")
                    break
                if d.get("status") == _STATUS_FAILED:
                    raise RuntimeError(f"AudioPortrait create failed: {d}")
                await asyncio.sleep(_POLL_INTERVAL)
            else:
                raise TimeoutError("AudioPortrait create timed out")

        logger.info("AudioPortrait portrait_id=%s", portrait_id)

        # Step B: generate video
        video_body = {
            "req_key":     self._REQ_KEY_VIDEO,
            "portrait_id": portrait_id,
            "audio_url":   ctx["audio_url"],
        }
        result = await _submit_and_poll(video_body, "AudioPortrait/video")
        return {
            "video_url": _extract_video_url(result["data"]),
            "task_id":   result["task_id"],
        }


# ---------------------------------------------------------------------------
# Tool 3 — Video Special Effects
# docs: https://www.volcengine.com/docs/86081/1804543
# ---------------------------------------------------------------------------

class VideoEffectsTool(BaseTool):
    name = "video_effects"
    description = (
        "Applies a named visual effect to an existing video. "
        "Requires context key: video_url (str) — produced by a previous step. "
        "Optional override: effect (str) — the effect name, e.g. 'glitch', 'vintage', 'cinematic'. "
        "Produces: video_url (the processed video, replaces prior video_url in context)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "effect": {
                "type": "string",
                "description": "Effect name to apply. Ask the user if unspecified.",
            },
        },
        "required": [],
    }

    # TODO: confirm req_key and 'effect' param name with https://www.volcengine.com/docs/86081/1804543
    _REQ_KEY = "jimeng_video_effects_v2"

    async def run(self, ctx: dict) -> dict:
        body = {
            "req_key":   self._REQ_KEY,
            "video_url": ctx["video_url"],
            "effect":    ctx.get("effect", ""),
        }
        result = await _submit_and_poll(body, "VideoEffects")
        return {
            "video_url": _extract_video_url(result["data"]),
            "task_id":   result["task_id"],
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_TOOLS: list[BaseTool] = [
    ImageToVideoTool(),
    AudioPortraitTool(),
    VideoEffectsTool(),
]

TOOL_MAP: dict[str, BaseTool] = {t.name: t for t in ALL_TOOLS}
