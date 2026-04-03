import json
from datetime import datetime, timedelta, timezone

from web.backend.services.service_diagnostics_service import ServiceDiagnosticsService


def _read_jsonl(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_service_diagnostics_archives_unclean_previous_run(tmp_path):
    service = ServiceDiagnosticsService(log_dir=str(tmp_path))
    previous_started = datetime(2026, 4, 1, 6, 0, tzinfo=timezone.utc)
    previous_failed = previous_started + timedelta(minutes=12)
    service._write_json(
        service.state_path,
        {
            "run_id": "old-run",
            "pid": 123,
            "started_at": previous_started.isoformat(),
            "last_heartbeat_at": previous_failed.isoformat(),
            "clean_shutdown": False,
            "failure": {
                "source": "sys",
                "message": "Too many open files",
                "traceback": "Traceback details",
                "captured_at": previous_failed.isoformat(),
            },
        },
    )

    state = service.start_run()
    incidents = _read_jsonl(service.incidents_path)
    runs = _read_jsonl(service.runs_path)

    assert state["run_id"] != "old-run"
    assert incidents[0]["run_id"] == "old-run"
    assert incidents[0]["failure_message"] == "Too many open files"
    assert incidents[0]["traceback"] == "Traceback details"
    assert runs[0]["run_id"] == "old-run"
    assert runs[0]["clean_shutdown"] is False


def test_service_diagnostics_archives_unclean_previous_run_without_failure_details(tmp_path):
    service = ServiceDiagnosticsService(log_dir=str(tmp_path))
    previous_started = datetime(2026, 4, 1, 6, 0, tzinfo=timezone.utc)
    previous_heartbeat = previous_started + timedelta(minutes=12)
    service._write_json(
        service.state_path,
        {
            "run_id": "old-run",
            "pid": 123,
            "started_at": previous_started.isoformat(),
            "last_heartbeat_at": previous_heartbeat.isoformat(),
            "clean_shutdown": False,
            "failure": None,
        },
    )

    state = service.start_run()
    incidents = _read_jsonl(service.incidents_path)
    runs = _read_jsonl(service.runs_path)

    assert state["run_id"] != "old-run"
    assert incidents[0]["run_id"] == "old-run"
    assert incidents[0]["failed_at"] == previous_heartbeat.isoformat()
    assert incidents[0]["failure_message"] is None
    assert runs[0]["run_id"] == "old-run"
    assert runs[0]["clean_shutdown"] is False


def test_service_diagnostics_marks_clean_shutdown_and_keeps_uptime_log(tmp_path):
    service = ServiceDiagnosticsService(log_dir=str(tmp_path))
    state = service.start_run()

    service.mark_clean_shutdown("shutdown_event")

    stored_state = service._read_json(service.state_path)
    runs = _read_jsonl(service.runs_path)

    assert stored_state["clean_shutdown"] is True
    assert stored_state["shutdown_reason"] == "shutdown_event"
    assert runs[0]["run_id"] == state["run_id"]
    assert runs[0]["clean_shutdown"] is True


def test_service_diagnostics_incident_detail_includes_related_log_window(tmp_path):
    service = ServiceDiagnosticsService(log_dir=str(tmp_path))
    failed_at = datetime(2026, 4, 1, 7, 30, tzinfo=timezone.utc)
    service._append_jsonl(
        service.incidents_path,
        {
            "incident_id": "incident-1",
            "run_id": "run-1",
            "started_at": (failed_at - timedelta(minutes=10)).isoformat(),
            "failed_at": failed_at.isoformat(),
            "recovered_at": (failed_at + timedelta(minutes=1)).isoformat(),
            "traceback": "boom",
        },
    )
    with open(tmp_path / "errors.log", "w", encoding="utf-8") as handle:
        handle.write("2026-04-01 07:29:59 - app - ERROR - right before crash\n")
        handle.write("Traceback (most recent call last):\n")
        handle.write("ValueError: boom\n")
        handle.write("2026-04-01 07:40:00 - app - INFO - too late\n")

    detail = service.get_incident_detail("incident-1", context_minutes=2)

    assert detail["incident"]["incident_id"] == "incident-1"
    assert any(entry["log_file"] == "errors.log" for entry in detail["related_logs"])
    assert "ValueError: boom" in detail["related_logs"][0]["text"]
