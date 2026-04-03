import asyncio
import json
import logging
import os
import re
import sys
import threading
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

_TIMESTAMP_PATTERNS = [
    re.compile(r"^\[(?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]"),
    re.compile(r"^(?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?)"),
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _duration_seconds(started_at: Optional[str], ended_at: Optional[str]) -> Optional[float]:
    started = _parse_iso(started_at)
    ended = _parse_iso(ended_at)
    if started is None or ended is None:
        return None
    return max((ended - started).total_seconds(), 0.0)


def _repo_log_dir() -> str:
    service_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(service_dir, "..", "..", ".."))
    log_dir = os.environ.get("NANODLNA_LOG_DIR") or os.path.join(root_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


class ServiceDiagnosticsService:
    def __init__(self, log_dir: Optional[str] = None):
        self.log_dir = os.path.abspath(log_dir or _repo_log_dir())
        os.makedirs(self.log_dir, exist_ok=True)
        self.state_path = os.path.join(self.log_dir, "service_diagnostics_state.json")
        self.incidents_path = os.path.join(self.log_dir, "service_diagnostics_incidents.jsonl")
        self.runs_path = os.path.join(self.log_dir, "service_diagnostics_runs.jsonl")
        self._state_lock = threading.RLock()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._hooks_installed = False
        self._previous_sys_excepthook = None
        self._previous_threading_excepthook = None
        self._previous_asyncio_exception_handler = None

    def install_exception_hooks(self) -> None:
        if self._hooks_installed:
            return
        self._hooks_installed = True
        self._previous_sys_excepthook = sys.excepthook
        self._previous_threading_excepthook = threading.excepthook

        def sys_hook(exc_type, exc_value, exc_tb):
            if issubclass(exc_type, KeyboardInterrupt):
                return self._previous_sys_excepthook(exc_type, exc_value, exc_tb)
            self.record_fatal_exception(
                source="sys",
                exc_type=exc_type,
                exc_value=exc_value,
                exc_tb=exc_tb,
            )
            if self._previous_sys_excepthook:
                self._previous_sys_excepthook(exc_type, exc_value, exc_tb)

        def threading_hook(args):
            if args.exc_type and issubclass(args.exc_type, KeyboardInterrupt):
                return self._previous_threading_excepthook(args)
            self.record_fatal_exception(
                source="thread",
                exc_type=args.exc_type,
                exc_value=args.exc_value,
                exc_tb=args.exc_traceback,
                thread_name=getattr(args.thread, "name", None),
            )
            if self._previous_threading_excepthook:
                self._previous_threading_excepthook(args)

        sys.excepthook = sys_hook
        threading.excepthook = threading_hook

    def install_asyncio_exception_handler(self, loop: asyncio.AbstractEventLoop) -> None:
        self._previous_asyncio_exception_handler = loop.get_exception_handler()

        def handler(current_loop: asyncio.AbstractEventLoop, context: Dict[str, Any]) -> None:
            exc = context.get("exception")
            if exc is not None:
                self.record_fatal_exception(
                    source="asyncio",
                    exc_type=type(exc),
                    exc_value=exc,
                    exc_tb=exc.__traceback__,
                )
            else:
                self.record_failure_details(
                    source="asyncio",
                    message=context.get("message", "Unhandled asyncio exception"),
                    traceback_text=context.get("message", ""),
                )

            if self._previous_asyncio_exception_handler is not None:
                self._previous_asyncio_exception_handler(current_loop, context)
            else:
                current_loop.default_exception_handler(context)

        loop.set_exception_handler(handler)

    def start_run(self) -> Dict[str, Any]:
        now = _utc_now()
        with self._state_lock:
            previous_state = self._read_json(self.state_path)
            if previous_state and not previous_state.get("clean_shutdown"):
                self._archive_unclean_run(previous_state, recovered_at=now)

            state = {
                "run_id": str(uuid.uuid4()),
                "pid": os.getpid(),
                "started_at": _to_iso(now),
                "last_heartbeat_at": _to_iso(now),
                "clean_shutdown": False,
                "shutdown_at": None,
                "shutdown_reason": None,
                "failure": None,
                "service_label": os.environ.get("NANODLNA_SERVICE_LABEL", "com.nanodlna.dashboard"),
                "backend_port": os.environ.get("NANODLNA_BACKEND_PORT", "8000"),
                "host": os.environ.get("NANODLNA_HOST", "0.0.0.0"),
            }
            self._write_json(self.state_path, state)
            return state

    async def start_heartbeat(self, interval_seconds: int = 15) -> None:
        if self._heartbeat_task and not self._heartbeat_task.done():
            return

        async def heartbeat_loop():
            while True:
                self.touch_heartbeat()
                await asyncio.sleep(interval_seconds)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def stop_heartbeat(self) -> None:
        if self._heartbeat_task is None:
            return
        self._heartbeat_task.cancel()
        try:
            await self._heartbeat_task
        except asyncio.CancelledError:
            pass
        self._heartbeat_task = None

    def touch_heartbeat(self) -> None:
        with self._state_lock:
            state = self._read_json(self.state_path)
            if not state:
                return
            state["last_heartbeat_at"] = _to_iso(_utc_now())
            self._write_json(self.state_path, state)

    def mark_clean_shutdown(self, reason: str = "shutdown_event") -> None:
        with self._state_lock:
            state = self._read_json(self.state_path)
            if not state:
                return
            ended_at = _utc_now()
            state["clean_shutdown"] = True
            state["shutdown_at"] = _to_iso(ended_at)
            state["shutdown_reason"] = reason
            self._write_json(self.state_path, state)
            self._append_jsonl(
                self.runs_path,
                {
                    "run_id": state.get("run_id"),
                    "started_at": state.get("started_at"),
                    "ended_at": state.get("shutdown_at"),
                    "duration_seconds": _duration_seconds(state.get("started_at"), state.get("shutdown_at")),
                    "ended_reason": reason,
                    "clean_shutdown": True,
                    "pid": state.get("pid"),
                },
            )

    def record_failure_details(self, *, source: str, message: str, traceback_text: str) -> None:
        with self._state_lock:
            state = self._read_json(self.state_path)
            if not state:
                return
            state["failure"] = {
                "source": source,
                "message": message,
                "traceback": traceback_text,
                "captured_at": _to_iso(_utc_now()),
            }
            state["last_heartbeat_at"] = _to_iso(_utc_now())
            self._write_json(self.state_path, state)

    def record_fatal_exception(
        self,
        *,
        source: str,
        exc_type: type,
        exc_value: BaseException,
        exc_tb,
        thread_name: Optional[str] = None,
    ) -> None:
        traceback_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        message = str(exc_value) or exc_type.__name__
        self.record_failure_details(
            source=source,
            message=message,
            traceback_text=traceback_text,
        )
        logger.critical(
            "Captured fatal exception from %s%s: %s\n%s",
            source,
            f" ({thread_name})" if thread_name else "",
            message,
            traceback_text,
        )

    def get_service_snapshot(
        self,
        *,
        incident_limit: int = 10,
        run_limit: int = 10,
        supervisor_limit: int = 10,
    ) -> Dict[str, Any]:
        current_state = self._read_json(self.state_path) or {}
        now = _utc_now()
        started_at = _parse_iso(current_state.get("started_at"))
        uptime_seconds = (now - started_at).total_seconds() if started_at else None
        current_run = {
            **current_state,
            "uptime_seconds": uptime_seconds,
            "status": "running" if current_state and not current_state.get("clean_shutdown") else "stopped",
        }
        return {
            "current_run": current_run,
            "recent_runs": self._read_jsonl(self.runs_path, limit=run_limit),
            "recent_incidents": self._read_jsonl(self.incidents_path, limit=incident_limit),
            "supervisor_events": self.get_supervisor_events(limit=supervisor_limit),
            "log_files": self.get_log_file_status(),
        }

    def get_incident_detail(self, incident_id: str, context_minutes: int = 3) -> Dict[str, Any]:
        incident = next(
            (item for item in self._read_jsonl(self.incidents_path, limit=None) if item.get("incident_id") == incident_id),
            None,
        )
        if incident is None:
            raise KeyError(incident_id)

        failed_at = _parse_iso(incident.get("failed_at")) or _parse_iso(incident.get("captured_at"))
        recovered_at = _parse_iso(incident.get("recovered_at"))
        window_start = failed_at - timedelta(minutes=context_minutes) if failed_at else None
        window_end_base = recovered_at or failed_at
        window_end = window_end_base + timedelta(minutes=context_minutes) if window_end_base else None

        related_logs = []
        for log_name in ("dashboard_run.log", "errors.log", "launchd-dashboard.err.log", "service-supervisor.log"):
            related_logs.extend(self._read_log_entries_in_window(log_name, window_start, window_end, limit=20))

        related_logs.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
        return {
            "incident": incident,
            "related_logs": related_logs[:40],
        }

    def get_supervisor_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        path = os.path.join(self.log_dir, "service-supervisor.log")
        if not os.path.exists(path):
            return []

        events: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                match = re.match(r"^\[(?P<stamp>[^]]+)\] (?P<message>.+)$", line)
                if not match:
                    continue
                message = match.group("message")
                event_type = "restart"
                if "Starting dashboard" in message:
                    event_type = "start"
                elif "Received stop signal" in message:
                    event_type = "stop"
                elif "exited with code" in message:
                    event_type = "restart"
                events.append(
                    {
                        "timestamp": _to_iso(self._parse_log_timestamp(match.group("stamp"))),
                        "event_type": event_type,
                        "message": message,
                    }
                )
        events.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
        return events[:limit]

    def get_log_file_status(self) -> List[Dict[str, Any]]:
        result = []
        for file_name in (
            "dashboard_run.log",
            "errors.log",
            "launchd-dashboard.out.log",
            "launchd-dashboard.err.log",
            "service-supervisor.log",
        ):
            path = os.path.join(self.log_dir, file_name)
            exists = os.path.exists(path)
            result.append(
                {
                    "name": file_name,
                    "exists": exists,
                    "size_bytes": os.path.getsize(path) if exists else 0,
                    "path": path,
                }
            )
        return result

    def _archive_unclean_run(self, state: Dict[str, Any], recovered_at: datetime) -> None:
        failed_at = (
            _parse_iso(state.get("failure", {}).get("captured_at"))
            or _parse_iso(state.get("last_heartbeat_at"))
            or _parse_iso(state.get("started_at"))
            or recovered_at
        )
        incident = {
            "incident_id": str(uuid.uuid4()),
            "run_id": state.get("run_id"),
            "started_at": state.get("started_at"),
            "failed_at": _to_iso(failed_at),
            "recovered_at": _to_iso(recovered_at),
            "duration_seconds": _duration_seconds(state.get("started_at"), _to_iso(failed_at)),
            "reason": "unclean_restart",
            "clean_shutdown": False,
            "pid": state.get("pid"),
            "failure_source": state.get("failure", {}).get("source"),
            "failure_message": state.get("failure", {}).get("message"),
            "traceback": state.get("failure", {}).get("traceback"),
            "captured_at": state.get("failure", {}).get("captured_at"),
            "last_heartbeat_at": state.get("last_heartbeat_at"),
            "shutdown_reason": state.get("shutdown_reason"),
        }
        self._append_jsonl(self.incidents_path, incident)
        self._append_jsonl(
            self.runs_path,
            {
                "run_id": state.get("run_id"),
                "started_at": state.get("started_at"),
                "ended_at": incident["failed_at"],
                "duration_seconds": incident["duration_seconds"],
                "ended_reason": incident["reason"],
                "clean_shutdown": False,
                "pid": state.get("pid"),
            },
        )
        logger.warning(
            "Recovered an unclean backend run from %s (failed_at=%s, last_heartbeat_at=%s)",
            state.get("started_at"),
            incident["failed_at"],
            state.get("last_heartbeat_at"),
        )

    def _read_log_entries_in_window(
        self,
        file_name: str,
        window_start: Optional[datetime],
        window_end: Optional[datetime],
        *,
        limit: int,
    ) -> List[Dict[str, Any]]:
        path = os.path.join(self.log_dir, file_name)
        if not os.path.exists(path):
            return []

        entries: List[Dict[str, Any]] = []
        current_timestamp: Optional[datetime] = None
        current_lines: List[str] = []

        def flush_entry() -> None:
            if current_timestamp is None or not current_lines:
                return
            if window_start and current_timestamp < window_start:
                return
            if window_end and current_timestamp > window_end:
                return
            entries.append(
                {
                    "log_file": file_name,
                    "timestamp": _to_iso(current_timestamp),
                    "text": "".join(current_lines).rstrip(),
                }
            )

        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                maybe_timestamp = self._match_line_timestamp(raw_line)
                if maybe_timestamp is not None:
                    flush_entry()
                    current_timestamp = maybe_timestamp
                    current_lines = [raw_line]
                elif current_lines:
                    current_lines.append(raw_line)
            flush_entry()

        entries.sort(key=lambda item: item["timestamp"], reverse=True)
        return entries[:limit]

    def _match_line_timestamp(self, line: str) -> Optional[datetime]:
        for pattern in _TIMESTAMP_PATTERNS:
            match = pattern.match(line)
            if match:
                return self._parse_log_timestamp(match.group("stamp"))
        return None

    def _parse_log_timestamp(self, value: str) -> Optional[datetime]:
        for fmt in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _read_json(self, path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to read diagnostics JSON from %s", path, exc_info=True)
            return None

    def _write_json(self, path: str, payload: Dict[str, Any]) -> None:
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, path)

    def _append_jsonl(self, path: str, payload: Dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")

    def _read_jsonl(self, path: str, limit: Optional[int]) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            return []
        items: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Skipping invalid diagnostics JSONL row from %s", path)
        items.sort(
            key=lambda item: item.get("failed_at") or item.get("ended_at") or item.get("started_at") or "",
            reverse=True,
        )
        if limit is None:
            return items
        return items[:limit]


_service_diagnostics_singleton: Optional[ServiceDiagnosticsService] = None


def get_service_diagnostics_service() -> ServiceDiagnosticsService:
    global _service_diagnostics_singleton
    if _service_diagnostics_singleton is None:
        _service_diagnostics_singleton = ServiceDiagnosticsService()
    return _service_diagnostics_singleton
