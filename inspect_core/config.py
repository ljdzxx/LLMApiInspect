from __future__ import annotations

from dataclasses import dataclass
import locale
from pathlib import Path
import hashlib
from typing import Any

import yaml


SUPPORTED_PROTOCOLS = {
    "openai_chat",
    "openai_responses",
    "anthropic_messages",
    "gemini_generate",
}


@dataclass(frozen=True)
class GlobalConfig:
    interval_minutes: int
    window_hours: int
    timeout_ms: int
    database_path: str


@dataclass(frozen=True)
class ColorStop:
    latency_ms: int
    color: str


@dataclass(frozen=True)
class ColorConfig:
    no_data: str
    failure: str
    latency_scale: tuple[ColorStop, ...]

    @property
    def max_latency_ms(self) -> int:
        return max(stop.latency_ms for stop in self.latency_scale)


@dataclass(frozen=True)
class TargetConfig:
    id: str
    title: str
    subtitle: str
    base_url: str
    api_key: str
    protocol: str
    model: str
    enabled: bool

    @property
    def label(self) -> str:
        if self.subtitle:
            return f"{self.title} - {self.subtitle}"
        return self.title


@dataclass(frozen=True)
class AppConfig:
    global_config: GlobalConfig
    colors: ColorConfig
    targets: tuple[TargetConfig, ...]

    @property
    def enabled_targets(self) -> tuple[TargetConfig, ...]:
        return tuple(target for target in self.targets if target.enabled)


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = yaml.safe_load(_read_config_text(config_path)) or {}
    if not isinstance(raw, dict):
        raise ValueError("config.yaml must contain a mapping at the top level")

    global_config = _parse_global(raw.get("global") or {}, config_path.parent)
    colors = _parse_colors(raw.get("colors") or {})
    targets = _parse_targets(raw.get("targets") or [])

    return AppConfig(global_config=global_config, colors=colors, targets=targets)


def _parse_global(raw: dict[str, Any], config_dir: Path) -> GlobalConfig:
    interval_minutes = _positive_int(raw, "interval_minutes")
    window_hours = _positive_int(raw, "window_hours")
    timeout_ms = _positive_int(raw, "timeout_ms")
    raw_database_path = str(raw.get("database_path") or "inspect.db")
    database_path = Path(raw_database_path)
    if not database_path.is_absolute():
        database_path = config_dir / database_path
    return GlobalConfig(
        interval_minutes=interval_minutes,
        window_hours=window_hours,
        timeout_ms=timeout_ms,
        database_path=str(database_path),
    )


def _parse_colors(raw: dict[str, Any]) -> ColorConfig:
    no_data = str(raw.get("no_data") or "#e5e7eb")
    failure = str(raw.get("failure") or "#111827")
    raw_scale = raw.get("latency_scale") or []

    if not isinstance(raw_scale, list) or len(raw_scale) < 2:
        raise ValueError("colors.latency_scale must contain at least two color stops")

    stops = []
    for index, item in enumerate(raw_scale):
        if not isinstance(item, dict):
            raise ValueError(f"colors.latency_scale[{index}] must be a mapping")
        latency_ms = _non_negative_int(item, "latency_ms")
        color = str(item.get("color") or "").strip()
        if not color:
            raise ValueError(f"colors.latency_scale[{index}].color is required")
        stops.append(ColorStop(latency_ms=latency_ms, color=color))

    stops.sort(key=lambda stop: stop.latency_ms)
    if len({stop.latency_ms for stop in stops}) != len(stops):
        raise ValueError("colors.latency_scale latency_ms values must be unique")

    return ColorConfig(no_data=no_data, failure=failure, latency_scale=tuple(stops))


def _parse_targets(raw: list[Any]) -> tuple[TargetConfig, ...]:
    if not isinstance(raw, list):
        raise ValueError("targets must be an array")

    targets = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"targets[{index}] must be a mapping")

        title = _required_str(item, "title", index)
        subtitle = str(item.get("subtitle") or "").strip()
        base_url = _required_str(item, "base_url", index).rstrip("/")
        api_key = _required_str(item, "api_key", index)
        protocol = _required_str(item, "protocol", index)
        model = _required_str(item, "model", index)
        enabled = item.get("enabled")

        if protocol not in SUPPORTED_PROTOCOLS:
            supported = ", ".join(sorted(SUPPORTED_PROTOCOLS))
            raise ValueError(f"targets[{index}].protocol must be one of: {supported}")
        if not isinstance(enabled, bool):
            raise ValueError(f"targets[{index}].enabled must be true or false")

        target_id = stable_target_id(title, base_url, protocol, model)
        targets.append(
            TargetConfig(
                id=target_id,
                title=title,
                subtitle=subtitle,
                base_url=base_url,
                api_key=api_key,
                protocol=protocol,
                model=model,
                enabled=enabled,
            )
        )

    return tuple(targets)


def stable_target_id(title: str, base_url: str, protocol: str, model: str) -> str:
    material = "\n".join([title.strip(), base_url.rstrip("/"), protocol, model.strip()])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _read_config_text(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", locale.getpreferredencoding(False), "gbk"]
    seen = set()
    last_error = None
    for encoding in encodings:
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return path.read_text(encoding="utf-8")


def _required_str(item: dict[str, Any], key: str, target_index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"targets[{target_index}].{key} is required")
    return value.strip()


def _positive_int(item: dict[str, Any], key: str) -> int:
    value = item.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"global.{key} must be a positive integer")
    return value


def _non_negative_int(item: dict[str, Any], key: str) -> int:
    value = item.get(key)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value
