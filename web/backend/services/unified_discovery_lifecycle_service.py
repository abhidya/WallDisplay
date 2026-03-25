import asyncio
import logging
import threading
from typing import Optional


logger = logging.getLogger(__name__)


class UnifiedDiscoveryLifecycleService:
    """
    Own the background event loop used to run unified-discovery backends.

    This keeps discovery-v2 lifecycle out of the migration adapter so the
    runtime composition root is the explicit owner of starting/stopping
    backend discovery.
    """

    def __init__(self, discovery_manager):
        self.discovery_manager = discovery_manager
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ready = threading.Event()
        self._stop_requested = False
        self._paused = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            self._paused = False
            return

        self._stop_requested = False
        self._paused = False
        self._ready.clear()
        self._thread = threading.Thread(target=self._run_loop, name="unified-discovery", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)

    def stop(self) -> None:
        self._stop_requested = True
        loop = self._loop
        if loop is not None and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.discovery_manager.stop_discovery(), loop)
            try:
                future.result(timeout=5.0)
            except Exception as exc:
                logger.warning("Error stopping unified discovery: %s", exc)
            loop.call_soon_threadsafe(loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._thread = None
        self._loop = None
        self._paused = False
        self._ready.clear()

    def pause(self) -> None:
        if self._paused:
            return
        self.stop()
        self._paused = True

    def resume(self) -> None:
        if self.is_running:
            self._paused = False
            return
        self.start()

    def get_status(self) -> dict:
        devices = self.discovery_manager.get_all_devices()
        device_sessions = getattr(self.discovery_manager, "device_sessions", {})
        active_sessions = sum(
            1
            for sessions in device_sessions.values()
            for session in sessions
            if getattr(session, "is_active", True)
        )
        backend_intervals = [
            getattr(backend, "discovery_interval", None)
            for backend in getattr(self.discovery_manager, "backends", {}).values()
            if getattr(backend, "discovery_interval", None) is not None
        ]

        status = {
            "running": self.is_running and not self._paused,
            "paused": self._paused,
            "devices_discovered": len(devices),
            "devices_playing": active_sessions,
        }
        if backend_intervals:
            status["interval"] = min(backend_intervals)
        return status

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self.discovery_manager.is_running)

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.discovery_manager.start_discovery())
            self._ready.set()
            loop.run_forever()
        except Exception as exc:
            logger.error("Unified discovery lifecycle failed: %s", exc)
            self._ready.set()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                try:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
            loop.close()
