from __future__ import annotations

from datetime import datetime, timezone
import time


def now_epoch_ms() -> int:
    return int(time.time() * 1000)


def epoch_ms_to_local_iso(epoch_ms: int) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000).astimezone().isoformat(timespec="seconds")


def epoch_ms_to_label(epoch_ms: int) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000).astimezone().strftime("%m-%d %H:%M")


def epoch_ms_to_short_label(epoch_ms: int) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000).astimezone().strftime("%H:%M")


def floor_epoch_ms(epoch_ms: int, interval_minutes: int) -> int:
    bucket_ms = interval_minutes * 60 * 1000
    return epoch_ms - (epoch_ms % bucket_ms)


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
