from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
import logging
import threading

from inspect_core.config import AppConfig, TargetConfig
from inspect_core.db import insert_probe_result
from inspect_core.probes import run_probe


logger = logging.getLogger(__name__)


class ProbeScheduler:
    def __init__(self, config: AppConfig):
        self.config = config
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active_targets: set[str] = set()
        self._active_lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        logger.info("Starting probe scheduler")
        self._thread = threading.Thread(target=self._run_loop, name="probe-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        self._run_once()
        interval_seconds = self.config.global_config.interval_minutes * 60
        while not self._stop_event.wait(interval_seconds):
            self._run_once()

    def _run_once(self) -> None:
        enabled_targets = self.config.enabled_targets
        if not enabled_targets:
            logger.info("No enabled probe targets")
            return

        worker_count = max(1, min(8, len(enabled_targets)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = []
            for target in enabled_targets:
                if self._mark_active(target):
                    futures.append(executor.submit(self._probe_and_store, target))
            if futures:
                wait(futures)

    def _probe_and_store(self, target: TargetConfig) -> None:
        try:
            result = run_probe(
                target=target,
                timeout_ms=self.config.global_config.timeout_ms,
                interval_minutes=self.config.global_config.interval_minutes,
            )
            insert_probe_result(self.config.global_config.database_path, result.as_dict())
            if result.success:
                logger.info(
                    "Probe succeeded: target=%s protocol=%s model=%s latency_ms=%s",
                    target.title,
                    target.protocol,
                    target.model,
                    result.latency_ms,
                )
            else:
                logger.warning(
                    "Probe failed: target=%s protocol=%s model=%s status=%s error=%s",
                    target.title,
                    target.protocol,
                    target.model,
                    result.http_status,
                    result.error,
                )
        except Exception:
            logger.exception("Probe worker crashed: target=%s", target.title)
        finally:
            self._clear_active(target)

    def _mark_active(self, target: TargetConfig) -> bool:
        with self._active_lock:
            if target.id in self._active_targets:
                return False
            self._active_targets.add(target.id)
            return True

    def _clear_active(self, target: TargetConfig) -> None:
        with self._active_lock:
            self._active_targets.discard(target.id)
