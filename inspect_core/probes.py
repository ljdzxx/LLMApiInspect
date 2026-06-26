from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Iterable

import httpx

from inspect_core.config import TargetConfig
from inspect_core.time_utils import epoch_ms_to_local_iso, floor_epoch_ms, now_epoch_ms


PROMPT = "ping. Reply with the single word: pong"
ANTHROPIC_VERSION = "2023-06-01"


@dataclass(frozen=True)
class ProbeOutcome:
    target_id: str
    target_title: str
    target_subtitle: str
    protocol: str
    model: str
    started_at_ms: int
    started_at_iso: str
    bucket_start_ms: int
    first_token_at_ms: int | None
    latency_ms: int | None
    success: bool
    http_status: int | None
    error: str | None
    response_preview: str | None

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def run_probe(target: TargetConfig, timeout_ms: int, interval_minutes: int) -> ProbeOutcome:
    started_at_ms = now_epoch_ms()
    started_at_perf = time.perf_counter()
    status_code = None
    first_text = None
    error = None

    try:
        with httpx.Client(timeout=timeout_ms / 1000, follow_redirects=True) as client:
            if target.protocol == "openai_chat":
                status_code, first_text = _probe_openai_chat(client, target)
            elif target.protocol == "openai_responses":
                status_code, first_text = _probe_openai_responses(client, target)
            elif target.protocol == "anthropic_messages":
                status_code, first_text = _probe_anthropic_messages(client, target)
            elif target.protocol == "gemini_generate":
                status_code, first_text = _probe_gemini(client, target)
            else:
                raise ValueError(f"Unsupported protocol: {target.protocol}")
    except Exception as exc:
        error = _shorten_error(exc)

    first_token_at_ms = None
    latency_ms = None
    success = bool(first_text)
    if success:
        elapsed_ms = int((time.perf_counter() - started_at_perf) * 1000)
        latency_ms = max(0, elapsed_ms)
        first_token_at_ms = started_at_ms + latency_ms
    elif error is None:
        error = "Stream ended without text content"

    return ProbeOutcome(
        target_id=target.id,
        target_title=target.title,
        target_subtitle=target.subtitle,
        protocol=target.protocol,
        model=target.model,
        started_at_ms=started_at_ms,
        started_at_iso=epoch_ms_to_local_iso(started_at_ms),
        bucket_start_ms=floor_epoch_ms(started_at_ms, interval_minutes),
        first_token_at_ms=first_token_at_ms,
        latency_ms=latency_ms,
        success=success,
        http_status=status_code,
        error=error,
        response_preview=(first_text or "")[:80] if first_text else None,
    )


def _probe_openai_chat(client: httpx.Client, target: TargetConfig) -> tuple[int, str | None]:
    payload = {
        "model": target.model,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": True,
    }
    headers = _json_bearer_headers(target.api_key)
    with client.stream("POST", f"{target.base_url}/v1/chat/completions", headers=headers, json=payload) as response:
        response.raise_for_status()
        return response.status_code, _first_text_from_sse(response.iter_lines(), _extract_openai_chat_text)


def _probe_openai_responses(client: httpx.Client, target: TargetConfig) -> tuple[int, str | None]:
    payload = {
        "model": target.model,
        "input": PROMPT,
        "stream": True,
    }
    headers = _json_bearer_headers(target.api_key)
    with client.stream("POST", f"{target.base_url}/v1/responses", headers=headers, json=payload) as response:
        response.raise_for_status()
        return response.status_code, _first_text_from_sse(response.iter_lines(), _extract_openai_responses_text)


def _probe_anthropic_messages(client: httpx.Client, target: TargetConfig) -> tuple[int, str | None]:
    payload = {
        "model": target.model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 8,
        "stream": True,
    }
    headers = {
        "content-type": "application/json",
        "x-api-key": target.api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    }
    with client.stream("POST", f"{target.base_url}/v1/messages", headers=headers, json=payload) as response:
        response.raise_for_status()
        return response.status_code, _first_text_from_sse(response.iter_lines(), _extract_anthropic_text)


def _probe_gemini(client: httpx.Client, target: TargetConfig) -> tuple[int, str | None]:
    payload = {
        "contents": [{"parts": [{"text": PROMPT}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 8,
        },
    }
    path_model = target.model if target.model.startswith("models/") else f"models/{target.model}"
    url = f"{target.base_url}/v1beta/{path_model}:streamGenerateContent?alt=sse&key={target.api_key}"
    with client.stream("POST", url, headers={"content-type": "application/json"}, json=payload) as response:
        response.raise_for_status()
        return response.status_code, _first_text_from_sse(response.iter_lines(), _extract_gemini_text)


def _json_bearer_headers(api_key: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }


def _first_text_from_sse(lines: Iterable[str], extractor) -> str | None:
    event_data: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            text = _extract_from_event_data(event_data, extractor)
            if text:
                return text
            event_data = []
            continue
        if line.startswith("data:"):
            event_data.append(line[5:].strip())

    return _extract_from_event_data(event_data, extractor)


def _extract_from_event_data(event_data: list[str], extractor) -> str | None:
    if not event_data:
        return None
    data = "\n".join(event_data).strip()
    if not data or data == "[DONE]":
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    return _clean_text(extractor(payload))


def _extract_openai_chat_text(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices") or []
    for choice in choices:
        delta = choice.get("delta") or {}
        text = delta.get("content")
        if text:
            return text
    return None


def _extract_openai_responses_text(payload: dict[str, Any]) -> str | None:
    event_type = payload.get("type")
    if event_type in {"response.output_text.delta", "response.refusal.delta"}:
        return payload.get("delta")

    if event_type == "response.output_item.done":
        item = payload.get("item") or {}
        for content in item.get("content") or []:
            text = content.get("text")
            if text:
                return text

    return None


def _extract_anthropic_text(payload: dict[str, Any]) -> str | None:
    delta = payload.get("delta") or {}
    if delta.get("type") == "text_delta":
        return delta.get("text")
    content_block = payload.get("content_block") or {}
    if content_block.get("type") == "text":
        return content_block.get("text")
    return None


def _extract_gemini_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if text:
                return text
    return None


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def _shorten_error(exc: Exception) -> str:
    message = str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        response_text = exc.response.text[:500] if exc.response is not None else ""
        message = f"HTTP {exc.response.status_code}: {response_text or exc.response.reason_phrase}"
    return message[:1000]
