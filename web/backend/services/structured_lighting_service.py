import json
import math
import os
import shutil
import subprocess
import sys
import threading
import uuid
import zipfile
import asyncio
from datetime import UTC, datetime
from io import BytesIO
from typing import Dict, List, Optional
from urllib.parse import urlparse

from PIL import Image
from web.backend.core.streaming_service import get_streaming_service
from discovery.base import CastingMethod, Device, DeviceCapability
from web.backend.services.app_runtime import get_app_runtime


WORKER_TIMEOUT_SECONDS = 15


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


class StructuredLightingService:
    def __init__(self):
        self._sessions: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._worker: Dict = {
            "worker_id": None,
            "state": "unavailable",
            "connected": False,
            "last_seen_at": None,
            "camera_indices": [],
            "hostname": None,
            "message": "Host capture worker not connected yet.",
            "process_state": "stopped",
            "process_pid": None,
            "process_started_at": None,
            "process_exited_at": None,
            "last_exit_code": None,
            "log_path": None,
            "operator_ready": False,
            "launch_config": {},
        }
        self._worker_process: Optional[subprocess.Popen] = None
        self._worker_log_handle = None
        self._active_step_stream_server = None
        self._active_step_cast_session_id: Optional[str] = None
        self._upload_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "uploads",
            "structured_lighting",
        )
        os.makedirs(self._upload_root, exist_ok=True)
        self._load_sessions_from_disk()

    def list_sessions(self) -> List[Dict]:
        with self._lock:
            return sorted(
                (dict(session) for session in self._sessions.values()),
                key=lambda session: session["updated_at"],
                reverse=True,
            )

    def get_status(self) -> Dict:
        sessions = self.list_sessions()
        active_sessions = [session for session in sessions if session["status"] not in {"completed", "failed", "deleted"}]
        total_frames = sum(session["pattern_frame_count"] for session in sessions)
        total_estimated_seconds = sum(
            round((session["pattern_frame_count"] * session["hold_ms"]) / 1000, 1)
            for session in sessions
        )
        return {
            "worker": self._get_worker_status(),
            "summary": {
                "total_sessions": len(sessions),
                "active_sessions": len(active_sessions),
                "total_planned_frames": total_frames,
                "total_estimated_capture_seconds": total_estimated_seconds,
            },
        }

    def update_worker_status(
        self,
        worker_id: str,
        hostname: Optional[str],
        camera_indices: List[int],
        state: str = "idle",
        message: Optional[str] = None,
    ) -> Dict:
        now = _utcnow()
        with self._lock:
            self._refresh_worker_process_state_locked()
            self._worker.update({
                "worker_id": worker_id,
                "state": state,
                "connected": True,
                "last_seen_at": now.isoformat(),
                "camera_indices": camera_indices,
                "hostname": hostname,
                "message": message or "Host capture worker connected.",
            })
        return self._get_worker_status()

    def start_worker(
        self,
        base_url: str,
        camera_index: int,
        projector_screen_x: int,
        projector_screen_y: int,
        projector_width: int,
        projector_height: int,
        settle_seconds: float = 1.0,
        flush_count: int = 30,
        pump_ms: int = 400,
        poll_seconds: float = 1.0,
    ) -> Dict:
        with self._lock:
            self._refresh_worker_process_state_locked()
            if self._worker_process and self._worker_process.poll() is None:
                return self._get_worker_status()

            worker_id = str(uuid.uuid4())
            log_path = os.path.join(self._upload_root, "worker.log")
            self._close_worker_log_handle_locked()
            self._worker_log_handle = open(log_path, "ab")
            worker_script = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "structured_lighting_worker.py",
            )
            cmd = [
                sys.executable,
                worker_script,
                "--base-url", base_url,
                "--camera-index", str(camera_index),
                "--projector-screen-x", str(projector_screen_x),
                "--projector-screen-y", str(projector_screen_y),
                "--projector-width", str(projector_width),
                "--projector-height", str(projector_height),
                "--settle-seconds", str(settle_seconds),
                "--flush-count", str(flush_count),
                "--pump-ms", str(pump_ms),
                "--poll-seconds", str(poll_seconds),
                "--worker-id", worker_id,
            ]
            self._worker_process = subprocess.Popen(
                cmd,
                stdout=self._worker_log_handle,
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(worker_script),
                start_new_session=True,
            )
            now = _utcnow_iso()
            self._worker.update({
                "worker_id": worker_id,
                "state": "starting",
                "connected": False,
                "last_seen_at": None,
                "camera_indices": [camera_index],
                "hostname": None,
                "message": "Starting host capture worker.",
                "process_state": "starting",
                "process_pid": self._worker_process.pid,
                "process_started_at": now,
                "process_exited_at": None,
                "last_exit_code": None,
                "log_path": log_path,
                "operator_ready": False,
                "launch_config": {
                    "base_url": base_url,
                    "camera_index": camera_index,
                    "projector_screen_x": projector_screen_x,
                    "projector_screen_y": projector_screen_y,
                    "projector_width": projector_width,
                    "projector_height": projector_height,
                    "settle_seconds": settle_seconds,
                    "flush_count": flush_count,
                    "pump_ms": pump_ms,
                    "poll_seconds": poll_seconds,
                },
            })
            return self._get_worker_status()

    def stop_worker(self) -> Dict:
        with self._lock:
            proc = self._worker_process
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            self._worker_process = None
            self._close_worker_log_handle_locked()
            self._worker.update({
                "state": "stopped",
                "connected": False,
                "message": "Host capture worker stopped.",
                "process_state": "stopped",
                "process_pid": None,
                "process_exited_at": _utcnow_iso(),
                "operator_ready": False,
            })
            return self._get_worker_status()

    def confirm_worker_ready(self, worker_id: str) -> Dict:
        with self._lock:
            if self._worker.get("worker_id") != worker_id:
                raise RuntimeError("Structured-lighting worker is not available for confirmation.")
            self._worker["operator_ready"] = True
            self._worker["message"] = "Operator confirmed camera framing. Worker is arming capture."
            return self._get_worker_status()

    def get_worker_control(self, worker_id: str) -> Dict:
        with self._lock:
            if self._worker.get("worker_id") != worker_id:
                return {"worker_id": worker_id, "operator_ready": False}
            return {
                "worker_id": worker_id,
                "operator_ready": bool(self._worker.get("operator_ready")),
            }

    def start_session(self, session_id: str) -> Optional[Dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            self._clear_derived_outputs(session_id)
            self._clear_capture_dir(session_id)
            session["status"] = "waiting_for_worker" if not self._worker_is_connected() else "ready"
            session["current_step_index"] = 0
            session["captured_frames"] = 0
            session["last_capture_at"] = None
            session["captured_step_indices"] = []
            session["captures"] = {}
            session["decode"] = self._default_decode_state()
            session["calibration"] = self._default_calibration_state()
            session["review"] = self._default_review_state()
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)
            return dict(session)

    def get_runtime(self, session_id: str) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None
        plan = self.get_capture_plan(session_id)
        current_step_index = session.get("current_step_index", 0)
        current_step = None
        if plan and 0 <= current_step_index < len(plan["steps"]):
            current_step = plan["steps"][current_step_index]
        return {
            "session": session,
            "worker": self._get_worker_status(),
            "progress": {
                "captured_frames": session.get("captured_frames", 0),
                "remaining_frames": max(0, session["pattern_frame_count"] - session.get("captured_frames", 0)),
                "current_step_index": current_step_index,
                "last_capture_at": session.get("last_capture_at"),
            },
            "current_step": current_step,
        }

    def claim_next_step(self, worker_id: str) -> Optional[Dict]:
        with self._lock:
            if self._worker.get("worker_id") != worker_id or not self._worker_is_connected():
                return None
            for session in self._sessions.values():
                if session.get("status") not in {"ready", "capturing", "waiting_for_worker"}:
                    continue
                plan = self.get_capture_plan(session["session_id"])
                current_step_index = session.get("current_step_index", 0)
                if current_step_index >= len(plan["steps"]):
                    session["status"] = "completed"
                    session["updated_at"] = _utcnow_iso()
                    self._persist_session(session)
                    continue
                step = plan["steps"][current_step_index]
                if session["presentation_mode"] == "dlna_step":
                    self._present_step_via_dlna(session, step)
                session["status"] = "capturing"
                session["updated_at"] = _utcnow_iso()
                self._persist_session(session)
                return {
                    "session_id": session["session_id"],
                    "session_name": session["name"],
                    "step": step,
                    "projector_device_id": session.get("projector_device_id"),
                    "camera_index": session["camera_index"],
                    "presentation_mode": session["presentation_mode"],
                    "step_image_url": (
                        f"/api/structured-lighting/sessions/{session['session_id']}/steps/"
                        f"{current_step_index}/image"
                    ),
                }
        return None

    def record_capture(
        self,
        session_id: str,
        step_index: int,
        file_bytes: bytes,
        original_filename: str,
    ) -> Optional[Dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            self._clear_derived_outputs(session_id)
            capture_dir = self._ensure_capture_dir(session_id)
            step = self._get_step(session, step_index)
            extension = os.path.splitext(original_filename or "")[1].lower() or ".png"
            if step and step["kind"] == "reference_white":
                stored_name = f"img_white{extension}"
            elif step and step["kind"] == "reference_black":
                stored_name = f"img_black{extension}"
            else:
                stored_name = f"img_{step_index:04d}{extension}"
            stored_path = os.path.join(capture_dir, stored_name)
            with open(stored_path, "wb") as handle:
                handle.write(file_bytes)

            captures = dict(session.get("captures", {}))
            captures[str(step_index)] = {
                "step_index": step_index,
                "step_kind": step["kind"] if step else "unknown",
                "filename": stored_name,
                "stored_path": stored_path,
                "captured_at": _utcnow_iso(),
            }
            session["captures"] = captures

            captured_steps = list(session.get("captured_step_indices", []))
            if step_index not in captured_steps:
                captured_steps.append(step_index)
                captured_steps.sort()
            session["captured_step_indices"] = captured_steps
            session["captured_frames"] = len(captured_steps)
            session["last_capture_at"] = _utcnow_iso()
            session["current_step_index"] = step_index + 1
            session["status"] = "ready" if session["captured_frames"] < session["pattern_frame_count"] else "completed"
            session["decode"] = self._default_decode_state()
            session["calibration"] = self._default_calibration_state()
            session["review"] = self._default_review_state()
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)
            return dict(session)

    def list_captures(self, session_id: str) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None
        captures = sorted(
            session.get("captures", {}).values(),
            key=lambda capture: capture["step_index"],
        )
        captures = [
            {
                **capture,
                "url": f"/api/structured-lighting/sessions/{session_id}/captures/{capture['step_index']}/image",
            }
            for capture in captures
        ]
        return {
            "session_id": session_id,
            "captures": captures,
            "captured_frames": session.get("captured_frames", 0),
            "expected_frames": session["pattern_frame_count"],
        }

    def render_capture_image(self, session_id: str, step_index: int) -> Optional[bytes]:
        session = self.get_session(session_id)
        if not session:
            return None
        capture = session.get("captures", {}).get(str(step_index))
        if not capture:
            return None
        stored_path = capture.get("stored_path")
        if not stored_path or not os.path.exists(stored_path):
            return None
        with open(stored_path, "rb") as handle:
            return handle.read()

    def decode_session(self, session_id: str, sample_step: int = 1, tuning_params: Optional[Dict] = None) -> Optional[Dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            self._clear_derived_outputs(session_id)
            session["decode"] = {
                **self._default_decode_state(),
                "status": "running",
                "started_at": _utcnow_iso(),
                "message": "Decoding graycode captures and generating repaired projector layers.",
                "progress": {
                    "phase": "initializing",
                    "label": "Preparing decode",
                    "percent": 2,
                },
            }
            session["calibration"] = self._default_calibration_state()
            session["review"] = self._default_review_state()
            session["tuning_search"] = self._default_tuning_search_state()
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)

        try:
            result = self._decode_graycode_session(
                session_id,
                sample_step=max(1, sample_step),
                tuning_params=tuning_params,
            )
        except Exception as exc:
            with self._lock:
                session = self._sessions.get(session_id)
                if session:
                    session["decode"] = {
                        **self._default_decode_state(),
                        "status": "failed",
                        "started_at": session.get("decode", {}).get("started_at"),
                        "finished_at": _utcnow_iso(),
                        "message": str(exc),
                    }
                    session["updated_at"] = _utcnow_iso()
                    self._persist_session(session)
                    return dict(session)
            raise

        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            session["decode"] = result
            session["calibration"] = self._build_calibration_record(session, result)
            session["review"] = self._build_review_state(result)
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)
            return dict(session)

    def run_tuning_search(
        self,
        session_id: str,
        sample_step: int = 1,
        tuning_params: Optional[Dict] = None,
        parameter_grid: Optional[Dict] = None,
    ) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None

        base_params = self._normalize_tuning_params(tuning_params)
        cam2proj, white_path, black_path = self._decode_raw_cam2proj(
            session_id,
            sample_step=max(1, sample_step),
            tuning_params=base_params,
        )
        projector_width = session["projector_width"]
        projector_height = session["projector_height"]
        decode_dir = self._ensure_decode_dir(session_id)
        search_dir = os.path.join(decode_dir, "tuning_search")
        if os.path.isdir(search_dir):
            shutil.rmtree(search_dir)
        os.makedirs(search_dir, exist_ok=True)

        search_candidates = self._parameter_search_candidates(base_params, parameter_grid)
        total_candidates = len(search_candidates)
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            session["tuning_search"] = {
                "status": "running",
                "message": "Generating tuning candidates.",
                "generated_at": None,
                "sample_step": sample_step,
                "base_tuning_params": base_params,
                "parameter_grid": parameter_grid or {},
                "candidates": [],
                "progress": {
                    "current": 0,
                    "total": total_candidates,
                    "percent": 0,
                    "label": "Preparing tuning search",
                },
            }
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)

        candidates = []
        for candidate_index, candidate in enumerate(search_candidates):
            candidate_id = f"candidate_{candidate_index:02d}"
            candidate_dir = os.path.join(search_dir, candidate_id)
            os.makedirs(candidate_dir, exist_ok=True)
            with self._lock:
                session = self._sessions.get(session_id)
                if session:
                    session["tuning_search"] = {
                        **session.get("tuning_search", self._default_tuning_search_state()),
                        "status": "running",
                        "message": f"Generating candidate {candidate_index + 1} of {total_candidates}.",
                        "progress": {
                            "current": candidate_index,
                            "total": total_candidates,
                            "percent": int((candidate_index / max(total_candidates, 1)) * 100),
                            "label": f"Testing {candidate['label']}",
                        },
                        "candidates": list(candidates),
                    }
                    session["updated_at"] = _utcnow_iso()
                    self._persist_session(session)
            result = self._generate_filtered_projector_masks(
                session_id=session_id,
                white_path=white_path,
                black_path=black_path,
                cam2proj=cam2proj,
                projector_width=projector_width,
                projector_height=projector_height,
                tuning_params=candidate["params"],
                output_dir=candidate_dir,
            )
            with open(result["manifest_path"], "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            candidates.append(
                {
                    "id": candidate_id,
                    "label": candidate["label"],
                    "description": candidate["description"],
                    "params": candidate["params"],
                    "metrics": {
                        "filtered_layer_count": manifest.get("filtered_layer_count", 0),
                        "raw_layer_count": manifest.get("raw_layer_count", 0),
                        "projector_components_kept": manifest.get("projector_components_kept", 0),
                    },
                    "previews": {
                        "warp": f"/api/structured-lighting/sessions/{session_id}/tuning-search/{candidate_id}/previews/warp",
                        "mask": f"/api/structured-lighting/sessions/{session_id}/tuning-search/{candidate_id}/previews/mask",
                    },
                }
            )
            with self._lock:
                session = self._sessions.get(session_id)
                if session:
                    session["tuning_search"] = {
                        **session.get("tuning_search", self._default_tuning_search_state()),
                        "status": "running",
                        "message": f"Completed candidate {candidate_index + 1} of {total_candidates}.",
                        "progress": {
                            "current": candidate_index + 1,
                            "total": total_candidates,
                            "percent": int(((candidate_index + 1) / max(total_candidates, 1)) * 100),
                            "label": f"Completed {candidate['label']}",
                        },
                        "candidates": list(candidates),
                    }
                    session["updated_at"] = _utcnow_iso()
                    self._persist_session(session)

        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            session["tuning_search"] = {
                "status": "completed",
                "message": f"Generated {len(candidates)} tuning candidates.",
                "generated_at": _utcnow_iso(),
                "sample_step": sample_step,
                "base_tuning_params": base_params,
                "parameter_grid": parameter_grid or {},
                "candidates": candidates,
                "progress": {
                    "current": len(candidates),
                    "total": total_candidates,
                    "percent": 100,
                    "label": "Parameter search completed",
                },
            }
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)
            return dict(session["tuning_search"])

    def get_tuning_search(self, session_id: str) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None
        return session.get("tuning_search", self._default_tuning_search_state())

    def run_preview_tuning(
        self,
        session_id: str,
        sample_step: int = 1,
        tuning_params: Optional[Dict] = None,
        parameter_grid: Optional[Dict] = None,
    ) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None

        base_params = self._normalize_tuning_params(tuning_params)
        decode_dir = self._ensure_decode_dir(session_id)
        preview_dir = os.path.join(decode_dir, "preview_tuning")
        if os.path.isdir(preview_dir):
            shutil.rmtree(preview_dir)
        os.makedirs(preview_dir, exist_ok=True)

        search_candidates = self._parameter_search_candidates(base_params, parameter_grid)
        total_candidates = len(search_candidates)
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            session["preview_tuning"] = {
                "status": "running",
                "message": "Preparing preview tuning candidates.",
                "generated_at": None,
                "sample_step": sample_step,
                "base_tuning_params": base_params,
                "parameter_grid": parameter_grid or {},
                "candidates": [],
                "progress": {
                    "current": 0,
                    "total": total_candidates,
                    "percent": 0,
                    "label": "Preparing preview tuning",
                },
            }
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)

        candidates = []
        for candidate_index, candidate in enumerate(search_candidates):
            candidate_id = f"candidate_{candidate_index:02d}"
            candidate_dir = os.path.join(preview_dir, candidate_id)
            os.makedirs(candidate_dir, exist_ok=True)
            with self._lock:
                session = self._sessions.get(session_id)
                if session:
                    session["preview_tuning"] = {
                        **session.get("preview_tuning", self._default_preview_tuning_state()),
                        "status": "running",
                        "message": f"Building preview candidate {candidate_index + 1} of {total_candidates}.",
                        "progress": {
                            "current": candidate_index,
                            "total": total_candidates,
                            "percent": int((candidate_index / max(total_candidates, 1)) * 100),
                            "label": f"Previewing {candidate['label']}",
                        },
                        "candidates": list(candidates),
                    }
                    session["updated_at"] = _utcnow_iso()
                    self._persist_session(session)

            cam2proj, white_path, black_path = self._decode_raw_cam2proj(
                session_id,
                sample_step=max(1, sample_step),
                tuning_params=candidate["params"],
            )
            preview_result = self._generate_preview_tuning_candidate(
                session_id=session_id,
                candidate_id=candidate_id,
                white_path=white_path,
                black_path=black_path,
                cam2proj=cam2proj,
                projector_width=session["projector_width"],
                projector_height=session["projector_height"],
                tuning_params=candidate["params"],
                output_dir=candidate_dir,
            )
            candidates.append(
                {
                    "id": candidate_id,
                    "label": candidate["label"],
                    "description": candidate["description"],
                    "params": candidate["params"],
                    "metrics": preview_result["metrics"],
                    "previews": {
                        "edge": f"/api/structured-lighting/sessions/{session_id}/preview-tuning/{candidate_id}/previews/edge",
                        "segmentation": f"/api/structured-lighting/sessions/{session_id}/preview-tuning/{candidate_id}/previews/segmentation",
                        "trusted_mask": f"/api/structured-lighting/sessions/{session_id}/preview-tuning/{candidate_id}/previews/trusted_mask",
                        "projector_occupancy": f"/api/structured-lighting/sessions/{session_id}/preview-tuning/{candidate_id}/previews/projector_occupancy",
                    },
                }
            )
            with self._lock:
                session = self._sessions.get(session_id)
                if session:
                    session["preview_tuning"] = {
                        **session.get("preview_tuning", self._default_preview_tuning_state()),
                        "status": "running",
                        "message": f"Completed preview candidate {candidate_index + 1} of {total_candidates}.",
                        "progress": {
                            "current": candidate_index + 1,
                            "total": total_candidates,
                            "percent": int(((candidate_index + 1) / max(total_candidates, 1)) * 100),
                            "label": f"Completed {candidate['label']}",
                        },
                        "candidates": list(candidates),
                    }
                    session["updated_at"] = _utcnow_iso()
                    self._persist_session(session)

        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            session["preview_tuning"] = {
                "status": "completed",
                "message": f"Generated {len(candidates)} preview candidates.",
                "generated_at": _utcnow_iso(),
                "sample_step": sample_step,
                "base_tuning_params": base_params,
                "parameter_grid": parameter_grid or {},
                "candidates": candidates,
                "progress": {
                    "current": len(candidates),
                    "total": total_candidates,
                    "percent": 100,
                    "label": "Preview tuning completed",
                },
            }
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)
            return dict(session["preview_tuning"])

    def get_preview_tuning(self, session_id: str) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None
        return session.get("preview_tuning", self._default_preview_tuning_state())

    def render_tuning_search_preview(self, session_id: str, candidate_id: str, preview_name: str) -> Optional[bytes]:
        session = self.get_session(session_id)
        if not session:
            return None
        search = session.get("tuning_search", {})
        candidate = next((item for item in search.get("candidates", []) if item.get("id") == candidate_id), None)
        if not candidate:
            return None
        decode_dir = self._ensure_decode_dir(session_id)
        candidate_dir = os.path.join(decode_dir, "tuning_search", candidate_id)
        file_name = {
            "warp": "warped_for_projector_second_pass_filled.png",
            "mask": "projector_wall_mask_second_pass.png",
        }.get(preview_name)
        if not file_name:
            return None
        file_path = os.path.join(candidate_dir, file_name)
        if not os.path.exists(file_path):
            return None
        with open(file_path, "rb") as handle:
            return handle.read()

    def render_preview_tuning_preview(self, session_id: str, candidate_id: str, preview_name: str) -> Optional[bytes]:
        session = self.get_session(session_id)
        if not session:
            return None
        search = session.get("preview_tuning", {})
        candidate = next((item for item in search.get("candidates", []) if item.get("id") == candidate_id), None)
        if not candidate:
            return None
        decode_dir = self._ensure_decode_dir(session_id)
        candidate_dir = os.path.join(decode_dir, "preview_tuning", candidate_id)
        file_name = {
            "edge": "edge_map.png",
            "segmentation": "segmentation.png",
            "trusted_mask": "trusted_cam_mask.png",
            "projector_occupancy": "projector_occupancy.png",
        }.get(preview_name)
        if not file_name:
            return None
        file_path = os.path.join(candidate_dir, file_name)
        if not os.path.exists(file_path):
            return None
        with open(file_path, "rb") as handle:
            return handle.read()

    def get_calibration(self, session_id: str) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None
        return {
            "session_id": session_id,
            "calibration": session.get("calibration", self._default_calibration_state()),
        }

    def update_review(
        self,
        session_id: str,
        verdict: str,
        notes: Optional[str] = None,
        reviewed_by: Optional[str] = None,
    ) -> Optional[Dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            review = dict(session.get("review", self._default_review_state()))
            review["status"] = verdict
            review["notes"] = notes or ""
            review["reviewed_by"] = reviewed_by or ""
            review["updated_at"] = _utcnow_iso()
            review["accepted_at"] = review["updated_at"] if verdict == "accepted" else None
            review["message"] = (
                "Session accepted for export." if verdict == "accepted"
                else "Session marked for recapture."
            )
            session["review"] = review
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)
            return dict(session)

    def export_session_bundle(self, session_id: str) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None
        if session.get("review", {}).get("status") != "accepted":
            raise RuntimeError("Session must be accepted in artifact review before export.")

        bundle_dir = self._session_dir(session_id)
        export_path = os.path.join(bundle_dir, "export_bundle.zip")

        with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            session_json = os.path.join(bundle_dir, "session.json")
            if os.path.exists(session_json):
                archive.write(session_json, arcname="session.json")

            calibration_path = os.path.join(bundle_dir, "calibration.json")
            if os.path.exists(calibration_path):
                archive.write(calibration_path, arcname="calibration.json")

            decode_dir = os.path.join(bundle_dir, "decode")
            if os.path.isdir(decode_dir):
                for root, _, files in os.walk(decode_dir):
                    for entry in sorted(files):
                        full_path = os.path.join(root, entry)
                        rel_path = os.path.relpath(full_path, bundle_dir)
                        archive.write(full_path, arcname=rel_path.replace("\\", "/"))

            capture_dir = os.path.join(bundle_dir, "captures")
            if os.path.isdir(capture_dir):
                for root, _, files in os.walk(capture_dir):
                    for entry in sorted(files):
                        full_path = os.path.join(root, entry)
                        rel_path = os.path.relpath(full_path, bundle_dir)
                        archive.write(full_path, arcname=rel_path.replace("\\", "/"))

        return {
            "session_id": session_id,
            "export_path": export_path,
            "filename": f"structured_lighting_{session_id}.zip",
        }

    def get_artifact_review(self, session_id: str) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None

        decode = session.get("decode", self._default_decode_state())
        calibration = session.get("calibration", self._default_calibration_state())
        previews = []
        for preview_id, label, description in self._artifact_preview_specs():
            if self._can_render_artifact_preview(session_id, preview_id):
                previews.append(
                    {
                        "id": preview_id,
                        "label": label,
                        "description": description,
                        "url": f"/api/structured-lighting/sessions/{session_id}/artifacts/previews/{preview_id}",
                    }
                )

        coverage_ratio = decode.get("metrics", {}).get("coverage_ratio")
        coverage_status = "unknown"
        if isinstance(coverage_ratio, (int, float)):
            if coverage_ratio >= 0.7:
                coverage_status = "good"
            elif coverage_ratio >= 0.45:
                coverage_status = "review"
            else:
                coverage_status = "poor"

        return {
            "session_id": session_id,
            "decode_status": decode.get("status"),
            "calibration_status": calibration.get("status"),
            "review": session.get("review", self._default_review_state()),
            "coverage_status": coverage_status,
            "metrics": decode.get("metrics", {}),
            "previews": previews,
        }

    def get_session(self, session_id: str) -> Optional[Dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            return dict(session) if session else None

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if not session:
                return False
            session["status"] = "deleted"
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)
            return True

    def create_session(
        self,
        name: str,
        projector_device_id: Optional[str],
        camera_index: int,
        projector_width: int,
        projector_height: int,
        presentation_mode: str,
        hold_ms: int,
        notes: Optional[str] = None,
    ) -> Dict:
        now = _utcnow_iso()
        bit_planes_x = max(1, math.ceil(math.log2(max(2, projector_width))))
        bit_planes_y = max(1, math.ceil(math.log2(max(2, projector_height))))
        pattern_frame_count = self._graycode_pattern_count(projector_width, projector_height)
        session = {
            "session_id": str(uuid.uuid4()),
            "name": name,
            "projector_device_id": projector_device_id,
            "camera_index": camera_index,
            "projector_width": projector_width,
            "projector_height": projector_height,
            "presentation_mode": presentation_mode,
            "hold_ms": hold_ms,
            "notes": notes or "",
            "status": "draft",
            "bit_planes_x": bit_planes_x,
            "bit_planes_y": bit_planes_y,
            "pattern_frame_count": pattern_frame_count,
            "current_step_index": 0,
            "captured_frames": 0,
            "captured_step_indices": [],
            "captures": {},
            "decode": self._default_decode_state(),
            "calibration": self._default_calibration_state(),
            "review": self._default_review_state(),
            "tuning_search": self._default_tuning_search_state(),
            "preview_tuning": self._default_preview_tuning_state(),
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._sessions[session["session_id"]] = session
            self._persist_session(session)
        return dict(session)

    def get_capture_plan(self, session_id: str) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None

        graycode_patterns = self._generate_graycode_patterns(
            session["projector_width"],
            session["projector_height"],
        )

        steps = [
            {
                "index": 0,
                "kind": "reference_white",
                "label": "Reference White",
                "hold_ms": session["hold_ms"],
                "capture_required": True,
            },
            {
                "index": 1,
                "kind": "reference_black",
                "label": "Reference Black",
                "hold_ms": session["hold_ms"],
                "capture_required": True,
            },
        ]

        for pattern_index, _pattern in enumerate(graycode_patterns):
            steps.append(
                {
                    "index": pattern_index + 2,
                    "kind": "graycode",
                    "pattern_index": pattern_index,
                    "label": f"Graycode Pattern {pattern_index:03d}",
                    "hold_ms": session["hold_ms"],
                    "capture_required": True,
                }
            )

        return {
            "session": session,
            "summary": {
                "reference_frames": 2,
                "graycode_frames": len(steps) - 2,
                "total_frames": len(steps),
                "estimated_capture_seconds": round((len(steps) * session["hold_ms"]) / 1000, 1),
            },
            "steps": steps,
        }

    def render_step_image(self, session_id: str, step_index: int) -> Optional[bytes]:
        plan = self.get_capture_plan(session_id)
        if not plan:
            return None
        steps = plan["steps"]
        if step_index < 0 or step_index >= len(steps):
            return None

        step = steps[step_index]
        session = plan["session"]
        width = session["projector_width"]
        height = session["projector_height"]

        if step["kind"] == "reference_white":
            image = Image.new("L", (width, height), color=255)
        elif step["kind"] == "reference_black":
            image = Image.new("L", (width, height), color=0)
        elif step["kind"] == "graycode":
            patterns = self._generate_graycode_patterns(width, height)
            image = Image.fromarray(patterns[step["pattern_index"]], mode="L")
        else:
            return None

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def render_step_image_for_dlna(self, session_id: str, step_index: int) -> Optional[bytes]:
        plan = self.get_capture_plan(session_id)
        if not plan:
            return None
        steps = plan["steps"]
        if step_index < 0 or step_index >= len(steps):
            return None

        image_bytes = self.render_step_image(session_id, step_index)
        if image_bytes is None:
            return None

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=95, subsampling=0)
        return buffer.getvalue()

    def render_artifact_preview(self, session_id: str, preview_id: str) -> Optional[bytes]:
        if not self._can_render_artifact_preview(session_id, preview_id):
            return None

        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Artifact preview generation requires numpy in the backend environment.") from exc

        session = self.get_session(session_id)
        if not session:
            return None

        decode_artifacts = session.get("decode", {}).get("artifacts", {})
        image = None

        if preview_id == "valid-mask":
            valid_mask = np.load(decode_artifacts["valid_mask_cam"])
            preview = (valid_mask > 0).astype(np.uint8) * 255
            image = Image.fromarray(preview, mode="L")
        elif preview_id == "projector-coverage":
            proj2cam_x = np.load(decode_artifacts["proj2cam_x"])
            coverage = np.isfinite(proj2cam_x).astype(np.uint8) * 255
            image = Image.fromarray(coverage, mode="L")
        elif preview_id == "cam2proj-xy":
            cam2proj = np.load(decode_artifacts["cam2proj"])
            valid = (cam2proj[:, :, 0] >= 0) & (cam2proj[:, :, 1] >= 0)
            preview = np.zeros((cam2proj.shape[0], cam2proj.shape[1], 3), dtype=np.uint8)
            if valid.any():
                proj_w = max(1, session["projector_width"] - 1)
                proj_h = max(1, session["projector_height"] - 1)
                preview[:, :, 0] = np.where(valid, np.clip((cam2proj[:, :, 0] * 255) / proj_w, 0, 255), 0).astype(np.uint8)
                preview[:, :, 1] = np.where(valid, np.clip((cam2proj[:, :, 1] * 255) / proj_h, 0, 255), 0).astype(np.uint8)
                preview[:, :, 2] = np.where(valid, 255, 0).astype(np.uint8)
            image = Image.fromarray(preview, mode="RGB")
        else:
            return None

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _decode_graycode_session(self, session_id: str, sample_step: int, tuning_params: Optional[Dict] = None) -> Dict:
        session = self.get_session(session_id)
        if not session:
            raise RuntimeError("Structured lighting session not found")
        tuning = self._normalize_tuning_params(tuning_params)
        self._set_decode_progress(session_id, phase="loading", label="Loading captures", percent=5)
        cam2proj_u, white_path, black_path = self._decode_raw_cam2proj(session_id, sample_step, tuning)
        self._set_decode_progress(session_id, phase="mapping", label="Building projector maps", percent=60)

        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Decoding requires opencv-contrib-python and numpy in the backend environment.") from exc

        white_img = cv2.imread(white_path, cv2.IMREAD_GRAYSCALE)
        black_img = cv2.imread(black_path, cv2.IMREAD_GRAYSCALE)
        if white_img is None or black_img is None:
            raise RuntimeError("Failed to read reference captures.")

        h, w = white_img.shape
        valid_mask_cam = (cam2proj_u[:, :, 0] >= 0) & (cam2proj_u[:, :, 1] >= 0)
        proj_w = session["projector_width"]
        proj_h = session["projector_height"]
        proj2cam_x = np.full((proj_h, proj_w), np.nan, dtype=np.float32)
        proj2cam_y = np.full((proj_h, proj_w), np.nan, dtype=np.float32)

        ys, xs = np.where(valid_mask_cam)
        px = cam2proj_u[ys, xs, 0]
        py = cam2proj_u[ys, xs, 1]
        in_bounds = (px >= 0) & (px < proj_w) & (py >= 0) & (py < proj_h)
        ys, xs, px, py = ys[in_bounds], xs[in_bounds], px[in_bounds], py[in_bounds]
        proj2cam_x[py, px] = xs.astype(np.float32)
        proj2cam_y[py, px] = ys.astype(np.float32)

        decode_dir = self._ensure_decode_dir(session_id)
        np.save(os.path.join(decode_dir, "cam2proj.npy"), cam2proj_u)
        np.save(os.path.join(decode_dir, "valid_mask_cam.npy"), valid_mask_cam.astype(np.uint8))
        np.save(os.path.join(decode_dir, "proj2cam_x.npy"), proj2cam_x)
        np.save(os.path.join(decode_dir, "proj2cam_y.npy"), proj2cam_y)

        self._set_decode_progress(session_id, phase="repair", label="Preparing second-pass repair", percent=68)
        filtered_mask_result = self._generate_filtered_projector_masks(
            session_id=session_id,
            white_path=white_path,
            black_path=black_path,
            cam2proj=cam2proj_u,
            projector_width=session["projector_width"],
            projector_height=session["projector_height"],
            tuning_params=tuning,
        )

        white_delta = float(white_img.mean() - black_img.mean())
        coverage = float(valid_mask_cam.sum()) / float(valid_mask_cam.size) if valid_mask_cam.size else 0.0
        self._set_decode_progress(session_id, phase="finalizing", label="Writing decode artifacts", percent=96)
        manifest = {
            "status": "completed",
            "started_at": _utcnow_iso(),
            "finished_at": _utcnow_iso(),
            "message": "Gray-code decode completed.",
            "progress": {
                "phase": "completed",
                "label": "Decode complete",
                "percent": 100,
            },
            "metrics": {
                "camera_width": int(w),
                "camera_height": int(h),
                "valid_camera_pixels": int(valid_mask_cam.sum()),
                "valid_projector_samples": int(np.isfinite(proj2cam_x).sum()),
                "coverage_ratio": round(coverage, 4),
                "white_black_mean_delta": round(white_delta, 2),
                "sample_step": sample_step,
                "filtered_mask_count": filtered_mask_result["filtered_mask_count"],
                "tuning_params": tuning,
            },
            "artifacts": {
                "decode_dir": decode_dir,
                "cam2proj": os.path.join(decode_dir, "cam2proj.npy"),
                "valid_mask_cam": os.path.join(decode_dir, "valid_mask_cam.npy"),
                "proj2cam_x": os.path.join(decode_dir, "proj2cam_x.npy"),
                "proj2cam_y": os.path.join(decode_dir, "proj2cam_y.npy"),
                "projector_wall_mask": filtered_mask_result["combined_mask_path"],
                "filtered_masks_dir": filtered_mask_result["filtered_masks_dir"],
                "filtered_masks_manifest": filtered_mask_result["manifest_path"],
                "raw_layers_dir": filtered_mask_result["raw_layers_dir"],
                "second_pass_proj2cam_x": filtered_mask_result["second_pass_proj2cam_x_path"],
                "second_pass_proj2cam_y": filtered_mask_result["second_pass_proj2cam_y_path"],
                "second_pass_warp_raw": filtered_mask_result["second_pass_raw_path"],
                "second_pass_warp_filled": filtered_mask_result["second_pass_filled_path"],
                "repair_support_mask": filtered_mask_result["repair_support_mask_path"],
            },
        }
        with open(os.path.join(decode_dir, "decode_manifest.json"), "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
        return manifest

    def _generate_graycode_patterns(self, projector_width: int, projector_height: int):
        try:
            import cv2
        except ImportError:
            cv2 = None

        if cv2 is not None:
            if hasattr(cv2, "structured_light_GrayCodePattern"):
                graycode = cv2.structured_light_GrayCodePattern.create(projector_width, projector_height)
            elif hasattr(cv2, "structured_light") and hasattr(cv2.structured_light, "GrayCodePattern_create"):
                graycode = cv2.structured_light.GrayCodePattern_create(projector_width, projector_height)
            else:
                graycode = None

            if graycode is not None:
                graycode.setWhiteThreshold(5)
                graycode.setBlackThreshold(40)
                ok, patterns = graycode.generate()
                if not ok:
                    raise RuntimeError("Pattern generation failed.")
                return patterns

        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("OpenCV structured light module is unavailable and numpy fallback is missing.") from exc

        bit_planes_x = max(1, math.ceil(math.log2(max(2, projector_width))))
        bit_planes_y = max(1, math.ceil(math.log2(max(2, projector_height))))
        xs = np.arange(projector_width, dtype=np.uint32)
        ys = np.arange(projector_height, dtype=np.uint32)

        def _gray(v):
            return v ^ (v >> 1)

        gray_x = _gray(xs)
        gray_y = _gray(ys)
        patterns = []
        for bit in range(bit_planes_x - 1, -1, -1):
            row = (((gray_x >> bit) & 1) * 255).astype(np.uint8)
            patterns.append(np.tile(row, (projector_height, 1)))
            patterns.append(np.tile((255 - row).astype(np.uint8), (projector_height, 1)))
        for bit in range(bit_planes_y - 1, -1, -1):
            col = (((gray_y >> bit) & 1) * 255).astype(np.uint8).reshape(projector_height, 1)
            patterns.append(np.tile(col, (1, projector_width)))
            patterns.append(np.tile((255 - col).astype(np.uint8), (1, projector_width)))
        return patterns

    def _graycode_pattern_count(self, projector_width: int, projector_height: int) -> int:
        return 2 + len(self._generate_graycode_patterns(projector_width, projector_height))

    def _generate_filtered_projector_masks(
        self,
        *,
        session_id: str,
        white_path: str,
        black_path: str,
        cam2proj,
        projector_width: int,
        projector_height: int,
        tuning_params: Optional[Dict] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, object]:
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Filtered mask generation requires opencv-contrib-python and numpy.") from exc

        white_bgr = cv2.imread(white_path, cv2.IMREAD_COLOR)
        black_bgr = cv2.imread(black_path, cv2.IMREAD_COLOR)
        if white_bgr is None or black_bgr is None:
            raise RuntimeError("Failed to load white reference image for mask generation.")

        params = self._normalize_tuning_params(tuning_params)
        brightness_gain = float(params["brightness_gain"])
        white_bgr = self._apply_brightness_gain(white_bgr, brightness_gain)
        black_bgr = self._apply_brightness_gain(black_bgr, brightness_gain)
        decode_dir = output_dir or self._ensure_decode_dir(session_id)
        raw_layers_dir = os.path.join(decode_dir, "second_pass_projector_layers")
        filtered_masks_dir = os.path.join(decode_dir, "second_pass_projector_layers_filtered")
        os.makedirs(raw_layers_dir, exist_ok=True)
        os.makedirs(filtered_masks_dir, exist_ok=True)

        proj_w = projector_width
        proj_h = projector_height
        if proj_w <= 0 or proj_h <= 0:
            raise RuntimeError("Structured-light decode produced no valid projector coordinates.")

        edge_data = self._build_wall_edge_map(
            white_bgr,
            blur_ksize=int(params["median_blur_ksize"]),
            bilateral_params=(
                int(params["bilateral_d"]),
                int(params["bilateral_sigma_color"]),
                int(params["bilateral_sigma_space"]),
            ),
            gradient_kernel=int(params["gradient_kernel_size"]),
            edge_mode=str(params["edge_mode"]),
            canny_low=int(params["canny_low_threshold"]),
            canny_high=int(params["canny_high_threshold"]),
            laplacian_ksize=int(params["laplacian_ksize"]),
        )
        self._set_decode_progress(session_id, phase="segmentation", label="Building wall-edge image", percent=70)
        segmentation_source_path = os.path.join(decode_dir, "warped_for_projector.png")
        segmentation_source = cv2.resize(
            cv2.cvtColor(edge_data["gradient"], cv2.COLOR_GRAY2BGR),
            (white_bgr.shape[1], white_bgr.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )
        cv2.imwrite(segmentation_source_path, segmentation_source)
        segmentation = self._segment_projector_source(
            edge_data["gradient"],
            scale=float(params["segmentation_scale"]),
            threshold_value=int(params["segmentation_threshold"]),
            blur_value=int(params["segmentation_blur"]),
            min_area_fraction=float(params["min_area_ratio"]),
            close_kernel=int(params["room_close_kernel_size"]),
        )
        self._set_decode_progress(session_id, phase="segmentation", label="Segmenting camera-space regions", percent=74)
        final_bgr = cv2.cvtColor(segmentation["final_rgb"], cv2.COLOR_RGB2BGR)
        camera_segmentation_path = os.path.join(decode_dir, "best_result_S1.0_T5_B7.png")
        cv2.imwrite(camera_segmentation_path, final_bgr)

        decode_diag = self._build_decode_diagnostics(
            cam2proj,
            white_bgr,
            black_bgr,
            proj_w,
            proj_h,
            contrast_thresh=int(params["contrast_threshold"]),
        )
        filtered_projector_occupancy, _, kept_components = self._filter_projector_occupancy(
            decode_diag["projector_occupancy"],
            min_area=int(params["min_projector_component_area"]),
            close_kernel_size=int(params["room_close_kernel_size"]),
        )
        self._set_decode_progress(session_id, phase="repair", label="Filtering projector occupancy", percent=78)
        repair_support = self._refine_support_mask(
            filtered_projector_occupancy,
            fill_holes=bool(params["repair_fill_holes"]),
            restrict_to_bbox=bool(params["repair_restrict_to_bbox"]),
            max_hole_area=int(params["repair_max_hole_area"]),
        )
        self._set_decode_progress(session_id, phase="repair", label="Building repair support mask", percent=82)
        confidence_map = self._confidence_from_contrast_percentiles(
            decode_diag["contrast"],
            decode_diag["trusted_cam_mask"],
            low_percentile=float(params["confidence_low_percentile"]),
            high_percentile=float(params["confidence_high_percentile"]),
            contrast_thresh=int(params["contrast_threshold"]),
        )
        weighted_aggregation = self._aggregate_projector_hits_weighted(
            cam2proj,
            decode_diag["trusted_cam_mask"],
            confidence_map,
            proj_w,
            proj_h,
            support_mask=repair_support["clean"],
            conflict_sigma=float(params["aggregation_sigma"]),
        )
        self._set_decode_progress(session_id, phase="repair", label="Aggregating trusted projector hits", percent=86)
        kernel_filled_proj2cam_x = self._normalized_kernel_fill(
            weighted_aggregation["proj2cam_x"],
            repair_support["clean"],
            radius=int(params["kernel_radius"]),
            sigma=float(params["kernel_sigma"]),
            min_valid_neighbors=int(params["kernel_min_valid_neighbors"]),
            max_passes=int(params["kernel_max_passes"]),
        )
        kernel_filled_proj2cam_y = self._normalized_kernel_fill(
            weighted_aggregation["proj2cam_y"],
            repair_support["clean"],
            radius=int(params["kernel_radius"]),
            sigma=float(params["kernel_sigma"]),
            min_valid_neighbors=int(params["kernel_min_valid_neighbors"]),
            max_passes=int(params["kernel_max_passes"]),
        )
        kernel_repaired_proj2cam_x = np.where(
            np.isfinite(weighted_aggregation["proj2cam_x"]),
            weighted_aggregation["proj2cam_x"],
            kernel_filled_proj2cam_x,
        ).astype(np.float32)
        kernel_repaired_proj2cam_y = np.where(
            np.isfinite(weighted_aggregation["proj2cam_y"]),
            weighted_aggregation["proj2cam_y"],
            kernel_filled_proj2cam_y,
        ).astype(np.float32)

        first_pass_missing_mask = (repair_support["clean"] > 0) & (~np.isfinite(kernel_repaired_proj2cam_x))
        second_pass_proj2cam_x = self._normalized_kernel_fill_from_source(
            kernel_repaired_proj2cam_x,
            first_pass_missing_mask,
            repair_support["clean"],
            radius=int(params["second_pass_kernel_radius"]),
            sigma=float(params["second_pass_kernel_sigma"]),
            min_valid_neighbors=int(params["second_pass_min_valid_neighbors"]),
            max_passes=int(params["second_pass_max_passes"]),
        )
        second_pass_proj2cam_y = self._normalized_kernel_fill_from_source(
            kernel_repaired_proj2cam_y,
            first_pass_missing_mask,
            repair_support["clean"],
            radius=int(params["second_pass_kernel_radius"]),
            sigma=float(params["second_pass_kernel_sigma"]),
            min_valid_neighbors=int(params["second_pass_min_valid_neighbors"]),
            max_passes=int(params["second_pass_max_passes"]),
        )
        self._set_decode_progress(session_id, phase="repair", label="Completing second-pass repaired maps", percent=90)

        second_pass_map_x_for_remap = np.nan_to_num(second_pass_proj2cam_x, nan=0.0).astype(np.float32)
        second_pass_map_y_for_remap = np.nan_to_num(second_pass_proj2cam_y, nan=0.0).astype(np.float32)
        second_pass_warp_raw = cv2.remap(
            final_bgr,
            second_pass_map_x_for_remap,
            second_pass_map_y_for_remap,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
        second_pass_warp_raw[repair_support["clean"] == 0] = 0
        second_pass_warp_filled = cv2.morphologyEx(
            second_pass_warp_raw,
            cv2.MORPH_CLOSE,
            np.ones((5, 5), np.uint8),
        )

        second_pass_raw_path = os.path.join(decode_dir, "warped_for_projector_second_pass_raw.png")
        second_pass_filled_path = os.path.join(decode_dir, "warped_for_projector_second_pass_filled.png")
        combined_mask_path = os.path.join(decode_dir, "projector_wall_mask_second_pass.png")
        second_pass_proj2cam_x_path = os.path.join(decode_dir, "second_pass_proj2cam_x.npy")
        second_pass_proj2cam_y_path = os.path.join(decode_dir, "second_pass_proj2cam_y.npy")
        repair_support_mask_path = os.path.join(decode_dir, "projector_repair_support_mask.png")
        cv2.imwrite(second_pass_raw_path, second_pass_warp_raw)
        cv2.imwrite(second_pass_filled_path, second_pass_warp_filled)
        cv2.imwrite(combined_mask_path, (cv2.cvtColor(second_pass_warp_filled, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8) * 255)
        cv2.imwrite(repair_support_mask_path, repair_support["clean"])
        np.save(second_pass_proj2cam_x_path, second_pass_proj2cam_x)
        np.save(second_pass_proj2cam_y_path, second_pass_proj2cam_y)
        self._set_decode_progress(session_id, phase="layers", label="Warping repaired layers into projector space", percent=92)

        raw_layer_paths = self._save_layer_masks_from_color_image(
            second_pass_warp_filled,
            raw_layers_dir,
            prefix="second_pass_layer",
        )
        self._set_decode_progress(session_id, phase="layers", label="Extracting projector layer masks", percent=94)
        layer_info = self._collect_layer_areas(raw_layer_paths)
        chosen_min_area = int(params["layer_min_area"])
        mask_manifest = []
        filtered_layer_paths = []
        kept_layer_info = [info for info in layer_info if info["area"] >= chosen_min_area]
        for output_index, item in enumerate(kept_layer_info):
            mask = cv2.imread(item["path"], cv2.IMREAD_GRAYSCALE)
            if mask is None:
                continue
            file_name = f"second_pass_layer_min{chosen_min_area}_{output_index:03d}.png"
            file_path = os.path.join(filtered_masks_dir, file_name)
            cv2.imwrite(file_path, mask)
            filtered_layer_paths.append(file_path)
            mask_manifest.append(
                {
                    "name": os.path.splitext(file_name)[0],
                    "file_name": file_name,
                    "file_path": file_path,
                    "area": int(item["area"]),
                    "sort_order": output_index,
                }
            )

        manifest_path = os.path.join(filtered_masks_dir, "mask_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "masks": mask_manifest,
                    "min_area": chosen_min_area,
                    "raw_layer_count": len(raw_layer_paths),
                    "filtered_layer_count": len(mask_manifest),
                    "projector_components_kept": int(kept_components),
                    "tuning_params": params,
                },
                handle,
                indent=2,
                sort_keys=True,
            )

        return {
            "combined_mask_path": combined_mask_path,
            "filtered_masks_dir": filtered_masks_dir,
            "manifest_path": manifest_path,
            "filtered_mask_count": len(mask_manifest),
            "raw_layers_dir": raw_layers_dir,
            "second_pass_proj2cam_x_path": second_pass_proj2cam_x_path,
            "second_pass_proj2cam_y_path": second_pass_proj2cam_y_path,
            "second_pass_raw_path": second_pass_raw_path,
            "second_pass_filled_path": second_pass_filled_path,
            "repair_support_mask_path": repair_support_mask_path,
        }

    def _build_wall_edge_map(
        self,
        img_white_bgr,
        blur_ksize: int,
        bilateral_params,
        gradient_kernel: int,
        *,
        edge_mode: str,
        canny_low: int,
        canny_high: int,
        laplacian_ksize: int,
    ):
        import cv2
        import numpy as np

        # clean = cv2.medianBlur(img_white_bgr, blur_ksize)
        # smooth = cv2.bilateralFilter(clean, bilateral_params[0], bilateral_params[1], bilateral_params[2])
        gray = cv2.cvtColor(img_white_bgr, cv2.COLOR_BGR2GRAY)
        edge_mode = (edge_mode or "morph_gradient").lower()

        if edge_mode == "canny":
            gradient = cv2.Canny(gray, canny_low, canny_high)
        elif edge_mode == "laplacian":
            laplace = cv2.Laplacian(gray, cv2.CV_32F, ksize=max(1, laplacian_ksize | 1))
            gradient = cv2.convertScaleAbs(np.abs(laplace))
        else:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (gradient_kernel, gradient_kernel))
            gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)

        return {"clean": clean, "smooth": smooth, "gray": gray, "gradient": gradient, "edge_mode": edge_mode}

    def _segment_projector_source(
        self,
        gray_image,
        *,
        scale: float,
        threshold_value: int,
        blur_value: int,
        min_area_fraction: float,
        close_kernel: int,
    ):
        import cv2
        import numpy as np

        scaled_w = max(1, int(gray_image.shape[1] * scale))
        scaled_h = max(1, int(gray_image.shape[0] * scale))
        small_base = cv2.resize(gray_image, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
        blurred = cv2.GaussianBlur(small_base, (blur_value, blur_value), 0)
        _, walls = cv2.threshold(blurred, threshold_value, 255, cv2.THRESH_BINARY)
        walls = cv2.morphologyEx(walls, cv2.MORPH_CLOSE, np.ones((close_kernel, close_kernel), np.uint8))
        rooms = cv2.bitwise_not(walls)
        component_count, labels = cv2.connectedComponents(rooms)

        min_area = (scaled_w * scaled_h) * min_area_fraction
        filtered_labels = labels.copy()
        for label_id in range(1, component_count):
            if np.sum(filtered_labels == label_id) < min_area:
                filtered_labels[filtered_labels == label_id] = 0

        np.random.seed(42)
        colors = np.random.randint(0, 255, size=(component_count + 1, 3), dtype=np.uint8)
        colors[0] = [0, 0, 0]
        filled = colors[filtered_labels]
        upsampled = cv2.resize(filled, (gray_image.shape[1], gray_image.shape[0]), interpolation=cv2.INTER_NEAREST)
        final = cv2.medianBlur(upsampled, 7)
        return {"labels": filtered_labels, "final_rgb": final}

    def _build_decode_diagnostics(
        self,
        cam2proj_map,
        img_white_bgr,
        img_black_bgr,
        projector_width: int,
        projector_height: int,
        *,
        contrast_thresh: int,
    ):
        import cv2
        import numpy as np

        white_gray = cv2.cvtColor(img_white_bgr, cv2.COLOR_BGR2GRAY)
        black_gray = cv2.cvtColor(img_black_bgr, cv2.COLOR_BGR2GRAY)
        contrast = white_gray.astype(np.int16) - black_gray.astype(np.int16)
        contrast_mask = contrast > contrast_thresh
        valid_decode_mask = (cam2proj_map[:, :, 0] >= 0) & (cam2proj_map[:, :, 1] >= 0)
        trusted_cam_mask = valid_decode_mask & contrast_mask

        projector_occupancy = np.zeros((projector_height, projector_width), dtype=np.uint8)
        projector_hit_count = np.zeros((projector_height, projector_width), dtype=np.int32)
        ys, xs = np.where(trusted_cam_mask)
        px = cam2proj_map[ys, xs, 0]
        py = cam2proj_map[ys, xs, 1]
        in_bounds = (px >= 0) & (px < projector_width) & (py >= 0) & (py < projector_height)
        ys, xs, px, py = ys[in_bounds], xs[in_bounds], px[in_bounds], py[in_bounds]
        np.add.at(projector_hit_count, (py, px), 1)
        projector_occupancy[py, px] = 255

        return {
            "contrast": contrast,
            "contrast_mask": contrast_mask,
            "valid_decode_mask": valid_decode_mask,
            "trusted_cam_mask": trusted_cam_mask,
            "projector_occupancy": projector_occupancy,
            "projector_hit_count": projector_hit_count,
            "trusted_sample_count": len(px),
        }

    def _generate_preview_tuning_candidate(
        self,
        *,
        session_id: str,
        candidate_id: str,
        white_path: str,
        black_path: str,
        cam2proj,
        projector_width: int,
        projector_height: int,
        tuning_params: Optional[Dict] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, object]:
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Preview tuning requires opencv-contrib-python and numpy.") from exc

        white_bgr = cv2.imread(white_path, cv2.IMREAD_COLOR)
        black_bgr = cv2.imread(black_path, cv2.IMREAD_COLOR)
        if white_bgr is None or black_bgr is None:
            raise RuntimeError("Failed to load white/black reference images for preview tuning.")

        params = self._normalize_tuning_params(tuning_params)
        brightness_gain = float(params["brightness_gain"])
        white_bgr = self._apply_brightness_gain(white_bgr, brightness_gain)
        black_bgr = self._apply_brightness_gain(black_bgr, brightness_gain)
        candidate_dir = output_dir or os.path.join(self._ensure_decode_dir(session_id), "preview_tuning", candidate_id)
        os.makedirs(candidate_dir, exist_ok=True)

        edge_data = self._build_wall_edge_map(
            white_bgr,
            blur_ksize=int(params["median_blur_ksize"]),
            bilateral_params=(
                int(params["bilateral_d"]),
                int(params["bilateral_sigma_color"]),
                int(params["bilateral_sigma_space"]),
            ),
            gradient_kernel=int(params["gradient_kernel_size"]),
            edge_mode=str(params["edge_mode"]),
            canny_low=int(params["canny_low_threshold"]),
            canny_high=int(params["canny_high_threshold"]),
            laplacian_ksize=int(params["laplacian_ksize"]),
        )
        segmentation = self._segment_projector_source(
            edge_data["gradient"],
            scale=float(params["segmentation_scale"]),
            threshold_value=int(params["segmentation_threshold"]),
            blur_value=int(params["segmentation_blur"]),
            min_area_fraction=float(params["min_area_ratio"]),
            close_kernel=int(params["room_close_kernel_size"]),
        )
        decode_diag = self._build_decode_diagnostics(
            cam2proj,
            white_bgr,
            black_bgr,
            projector_width,
            projector_height,
            contrast_thresh=int(params["contrast_threshold"]),
        )

        cv2.imwrite(os.path.join(candidate_dir, "edge_map.png"), edge_data["gradient"])
        cv2.imwrite(
            os.path.join(candidate_dir, "segmentation.png"),
            cv2.cvtColor(segmentation["final_rgb"], cv2.COLOR_RGB2BGR),
        )
        cv2.imwrite(
            os.path.join(candidate_dir, "trusted_cam_mask.png"),
            (decode_diag["trusted_cam_mask"].astype(np.uint8) * 255),
        )
        cv2.imwrite(
            os.path.join(candidate_dir, "projector_occupancy.png"),
            decode_diag["projector_occupancy"],
        )

        labels = segmentation["labels"]
        kept_labels = [int(label_id) for label_id in np.unique(labels) if int(label_id) > 0]
        coverage_ratio = (
            float(np.count_nonzero(decode_diag["projector_occupancy"])) / float(decode_diag["projector_occupancy"].size)
            if decode_diag["projector_occupancy"].size
            else 0.0
        )
        metrics = {
            "edge_mode": params["edge_mode"],
            "trusted_sample_count": int(decode_diag["trusted_sample_count"]),
            "camera_valid_ratio": round(
                float(np.count_nonzero(decode_diag["trusted_cam_mask"])) / float(decode_diag["trusted_cam_mask"].size),
                4,
            ) if decode_diag["trusted_cam_mask"].size else 0.0,
            "projector_coverage_ratio": round(coverage_ratio, 4),
            "segmentation_region_count": len(kept_labels),
        }
        with open(os.path.join(candidate_dir, "manifest.json"), "w", encoding="utf-8") as handle:
            json.dump({"params": params, "metrics": metrics}, handle, indent=2, sort_keys=True)
        return {"metrics": metrics}

    def _filter_projector_occupancy(self, occupancy_mask, *, min_area: int, close_kernel_size: int):
        import cv2
        import numpy as np

        kernel = np.ones((close_kernel_size, close_kernel_size), np.uint8)
        closed = cv2.morphologyEx(occupancy_mask, cv2.MORPH_CLOSE, kernel)
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
        filtered = np.zeros_like(occupancy_mask)
        kept_components = 0
        for label_id in range(1, component_count):
            if stats[label_id, cv2.CC_STAT_AREA] >= min_area:
                filtered[labels == label_id] = 255
                kept_components += 1
        return filtered, closed, kept_components

    def _fill_small_enclosed_holes(self, mask, *, max_hole_area: int):
        import cv2
        import numpy as np

        filled = mask.copy()
        h, w = filled.shape
        flood = filled.copy()
        flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
        cv2.floodFill(flood, flood_mask, (0, 0), 255)
        holes = cv2.bitwise_not(flood) & cv2.bitwise_not(filled)

        kept_holes = np.zeros_like(mask)
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(holes, connectivity=8)
        for label_id in range(1, component_count):
            if stats[label_id, cv2.CC_STAT_AREA] <= max_hole_area:
                kept_holes[labels == label_id] = 255
        return cv2.bitwise_or(filled, kept_holes), kept_holes

    def _largest_component_bbox(self, mask):
        import cv2
        import numpy as np

        component_count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if component_count <= 1:
            return None
        largest_label = int(np.argmax(stats[1:, cv2.CC_STAT_AREA])) + 1
        return (
            int(stats[largest_label, cv2.CC_STAT_LEFT]),
            int(stats[largest_label, cv2.CC_STAT_TOP]),
            int(stats[largest_label, cv2.CC_STAT_WIDTH]),
            int(stats[largest_label, cv2.CC_STAT_HEIGHT]),
        )

    def _refine_support_mask(self, base_support, *, fill_holes: bool, restrict_to_bbox: bool, max_hole_area: int):
        import cv2
        import numpy as np

        support = base_support.copy()
        holes = np.zeros_like(base_support)
        if fill_holes:
            support, holes = self._fill_small_enclosed_holes(support, max_hole_area=max_hole_area)

        bbox_mask = np.full_like(base_support, 255)
        if restrict_to_bbox:
            bbox = self._largest_component_bbox(base_support)
            bbox_mask[:] = 0
            if bbox is not None:
                x, y, w, h = bbox
                bbox_mask[y:y + h, x:x + w] = 255
                support = cv2.bitwise_and(support, bbox_mask)
                holes = cv2.bitwise_and(holes, bbox_mask)
        return {"clean": support, "holes": holes, "bbox_mask": bbox_mask}

    def _gaussian_kernel(self, radius: int, sigma: float):
        import numpy as np

        ys, xs = np.mgrid[-radius:radius + 1, -radius:radius + 1]
        kernel = np.exp(-(xs * xs + ys * ys) / (2.0 * sigma * sigma))
        kernel /= kernel.sum()
        return kernel.astype(np.float32)

    def _confidence_from_contrast_percentiles(
        self,
        contrast_image,
        valid_mask,
        *,
        low_percentile: float,
        high_percentile: float,
        contrast_thresh: int,
    ):
        import numpy as np

        contrast = contrast_image.astype(np.float32)
        candidate_mask = valid_mask & (contrast > float(contrast_thresh))
        conf = np.zeros_like(contrast, dtype=np.float32)
        if not np.any(candidate_mask):
            return conf
        values = contrast[candidate_mask]
        low = float(np.percentile(values, low_percentile))
        high = float(np.percentile(values, high_percentile))
        if high <= low:
            high = low + 1.0
        conf[candidate_mask] = np.clip((contrast[candidate_mask] - low) / (high - low), 0.0, 1.0)
        return conf

    def _aggregate_projector_hits_weighted(
        self,
        cam2proj_map,
        trusted_cam_mask,
        confidence_map,
        projector_width: int,
        projector_height: int,
        *,
        support_mask=None,
        conflict_sigma: float,
    ):
        import numpy as np

        px_sum = np.zeros((projector_height, projector_width), dtype=np.float64)
        py_sum = np.zeros((projector_height, projector_width), dtype=np.float64)
        w_sum = np.zeros((projector_height, projector_width), dtype=np.float64)
        hit_count = np.zeros((projector_height, projector_width), dtype=np.int32)

        ys, xs = np.where(trusted_cam_mask)
        proj_x = cam2proj_map[ys, xs, 0]
        proj_y = cam2proj_map[ys, xs, 1]
        conf = confidence_map[ys, xs]
        in_bounds = (proj_x >= 0) & (proj_x < projector_width) & (proj_y >= 0) & (proj_y < projector_height) & (conf > 0)
        ys, xs, proj_x, proj_y, conf = ys[in_bounds], xs[in_bounds], proj_x[in_bounds], proj_y[in_bounds], conf[in_bounds]
        if support_mask is not None:
            keep = support_mask[proj_y, proj_x] > 0
            ys, xs, proj_x, proj_y, conf = ys[keep], xs[keep], proj_x[keep], proj_y[keep], conf[keep]

        np.add.at(hit_count, (proj_y, proj_x), 1)
        np.add.at(px_sum, (proj_y, proj_x), xs * conf)
        np.add.at(py_sum, (proj_y, proj_x), ys * conf)
        np.add.at(w_sum, (proj_y, proj_x), conf)

        proj2cam_x = np.full((projector_height, projector_width), np.nan, dtype=np.float32)
        proj2cam_y = np.full((projector_height, projector_width), np.nan, dtype=np.float32)
        valid = w_sum > 0
        proj2cam_x[valid] = (px_sum[valid] / w_sum[valid]).astype(np.float32)
        proj2cam_y[valid] = (py_sum[valid] / w_sum[valid]).astype(np.float32)

        grouped = {}
        for cx, cy, px, py, cw in zip(xs, ys, proj_x, proj_y, conf):
            grouped.setdefault((int(py), int(px)), []).append((float(cx), float(cy), float(cw)))
        for (pyi, pxi), samples in grouped.items():
            if len(samples) <= 1:
                continue
            avg_x = proj2cam_x[pyi, pxi]
            avg_y = proj2cam_y[pyi, pxi]
            distances = [((sx - avg_x) ** 2 + (sy - avg_y) ** 2) ** 0.5 for sx, sy, _ in samples]
            if np.average(distances, weights=[max(sw, 1e-6) for _, _, sw in samples]) > conflict_sigma:
                best = max(samples, key=lambda item: item[2])
                proj2cam_x[pyi, pxi] = np.float32(best[0])
                proj2cam_y[pyi, pxi] = np.float32(best[1])
        return {
            "proj2cam_x": proj2cam_x,
            "proj2cam_y": proj2cam_y,
            "hit_count": hit_count,
            "weighted_sum": w_sum.astype(np.float32),
        }

    def _normalized_kernel_fill(
        self,
        map_array,
        support_mask,
        *,
        radius: int,
        sigma: float,
        min_valid_neighbors: int,
        max_passes: int,
    ):
        import cv2
        import numpy as np

        filled = map_array.astype(np.float32).copy()
        kernel = self._gaussian_kernel(radius, sigma)
        support = support_mask > 0
        for _ in range(max_passes):
            valid = np.isfinite(filled) & support
            missing = (~valid) & support
            if not np.any(missing):
                break
            src = np.where(valid, filled, 0.0).astype(np.float32)
            weight_src = valid.astype(np.float32)
            weighted_sum = cv2.filter2D(src, -1, kernel, borderType=cv2.BORDER_REPLICATE)
            weight_sum = cv2.filter2D(weight_src, -1, kernel, borderType=cv2.BORDER_REPLICATE)
            neighbor_count = cv2.filter2D(
                weight_src,
                -1,
                np.ones((2 * radius + 1, 2 * radius + 1), np.float32),
                borderType=cv2.BORDER_REPLICATE,
            )
            can_fill = missing & (weight_sum > 1e-6) & (neighbor_count >= float(min_valid_neighbors))
            if not np.any(can_fill):
                break
            filled[can_fill] = weighted_sum[can_fill] / weight_sum[can_fill]
        filled[~support] = np.nan
        return filled

    def _normalized_kernel_fill_from_source(
        self,
        source_map,
        target_missing_mask,
        support_mask,
        *,
        radius: int,
        sigma: float,
        min_valid_neighbors: int,
        max_passes: int,
    ):
        import cv2
        import numpy as np

        filled = source_map.astype(np.float32).copy()
        kernel = self._gaussian_kernel(radius, sigma)
        support = support_mask > 0
        target_missing = target_missing_mask & support
        for _ in range(max_passes):
            valid = np.isfinite(filled) & support
            can_target = target_missing & (~valid)
            if not np.any(can_target):
                break
            src = np.where(valid, filled, 0.0).astype(np.float32)
            weight_src = valid.astype(np.float32)
            weighted_sum = cv2.filter2D(src, -1, kernel, borderType=cv2.BORDER_REPLICATE)
            weight_sum = cv2.filter2D(weight_src, -1, kernel, borderType=cv2.BORDER_REPLICATE)
            neighbor_count = cv2.filter2D(
                weight_src,
                -1,
                np.ones((2 * radius + 1, 2 * radius + 1), np.float32),
                borderType=cv2.BORDER_REPLICATE,
            )
            fill_now = can_target & (weight_sum > 1e-6) & (neighbor_count >= float(min_valid_neighbors))
            if not np.any(fill_now):
                break
            filled[fill_now] = weighted_sum[fill_now] / weight_sum[fill_now]
        filled[~support] = np.nan
        return filled

    def _save_layer_masks_from_color_image(self, color_bgr, out_dir: str, *, prefix: str):
        import cv2
        import numpy as np

        os.makedirs(out_dir, exist_ok=True)
        flat = color_bgr.reshape(-1, 3)
        unique_colors = np.unique(flat, axis=0)
        unique_colors = [color for color in unique_colors if np.any(color != 0)]
        saved_paths = []
        for idx, color in enumerate(unique_colors):
            mask = np.all(color_bgr == color, axis=2).astype(np.uint8) * 255
            out_path = os.path.join(out_dir, f"{prefix}_{idx:03d}.png")
            cv2.imwrite(out_path, mask)
            saved_paths.append(out_path)
        return saved_paths

    def _collect_layer_areas(self, layer_paths: List[str]):
        import cv2
        import numpy as np

        layer_info = []
        for layer_path in layer_paths:
            mask = cv2.imread(layer_path, cv2.IMREAD_GRAYSCALE)
            if mask is None:
                continue
            layer_info.append({"path": layer_path, "area": int(np.count_nonzero(mask))})
        return layer_info

    def _ensure_unique_mapping_scene_name(self, mapping_service, base_name: str) -> str:
        existing_names = {scene.name for scene in mapping_service.list_scenes()}
        if base_name not in existing_names:
            return base_name
        suffix = 2
        while f"{base_name} {suffix}" in existing_names:
            suffix += 1
        return f"{base_name} {suffix}"

    def publish_mapping_scene(self, session_id: str, scene_name: Optional[str] = None) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None
        if session.get("review", {}).get("status") != "accepted":
            raise RuntimeError("Session must be accepted before publishing to Mapping.")

        artifacts = session.get("decode", {}).get("artifacts", {})
        manifest_path = artifacts.get("filtered_masks_manifest")
        if not manifest_path or not os.path.exists(manifest_path):
            raise RuntimeError("Filtered masks have not been generated for this session.")

        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)

        mask_entries = manifest.get("masks", [])
        if not mask_entries:
            raise RuntimeError("No filtered masks are available to publish.")

        from database.database import get_db
        from schemas.mapping_scene import MappingSceneCreate
        from services.mapping_scene_service import MappingSceneService

        requested_name = (scene_name or f"{session['name']} {session_id[:8]}").strip()
        db_generator = get_db()
        db = next(db_generator)
        try:
            mapping_service = MappingSceneService(db)
            scene = mapping_service.create_scene(
                MappingSceneCreate(
                    name=self._ensure_unique_mapping_scene_name(mapping_service, requested_name),
                    canvas_width=session["projector_width"],
                    canvas_height=session["projector_height"],
                    mask_mode="luminance",
                    masks=[],
                    groups=[],
                    render_settings={"background": "#000000"},
                )
            )
            scene = mapping_service.add_mask_files(
                scene.id,
                [
                    {
                        "file_path": entry["file_path"],
                        "name": entry["name"],
                        "file_name": entry.get("file_name") or os.path.basename(entry["file_path"]),
                    }
                    for entry in mask_entries
                ],
            )
            return {
                "session_id": session_id,
                "scene_id": scene.id,
                "scene_name": scene.name,
                "mask_count": len(scene.masks or []),
            }
        finally:
            try:
                db_generator.close()
            except Exception:
                pass

    def _worker_is_connected(self) -> bool:
        last_seen = self._worker.get("last_seen_at")
        if not last_seen:
            return False
        try:
            last_seen_dt = datetime.fromisoformat(last_seen)
        except ValueError:
            return False
        return (_utcnow() - last_seen_dt).total_seconds() <= WORKER_TIMEOUT_SECONDS

    def _get_worker_status(self) -> Dict:
        with self._lock:
            self._refresh_worker_process_state_locked()
            worker = dict(self._worker)
            if not self._worker_is_connected():
                worker["connected"] = False
                if worker.get("process_state") in {"starting", "running"}:
                    worker["state"] = worker.get("state") if worker.get("state") in {"starting", "awaiting_operator"} else "starting"
                    worker["message"] = worker.get("message") or "Host capture worker is starting."
                elif worker.get("state") in {"stopped", "error"}:
                    pass
                else:
                    worker["state"] = "unavailable"
                    worker["message"] = "Host capture worker not connected yet."
        return worker

    def _refresh_worker_process_state_locked(self) -> None:
        proc = self._worker_process
        if not proc:
            return
        return_code = proc.poll()
        if return_code is None:
            if self._worker.get("process_state") not in {"running", "awaiting_operator"}:
                self._worker["process_state"] = "running"
            return

        self._worker["process_state"] = "stopped"
        self._worker["connected"] = False
        self._worker["state"] = "stopped"
        self._worker["process_exited_at"] = _utcnow_iso()
        self._worker["last_exit_code"] = return_code
        self._worker["process_pid"] = None
        self._worker["operator_ready"] = False
        self._worker["message"] = f"Host capture worker exited with code {return_code}."
        self._worker_process = None
        self._close_worker_log_handle_locked()

    def _close_worker_log_handle_locked(self) -> None:
        if self._worker_log_handle:
            self._worker_log_handle.close()
            self._worker_log_handle = None

    def _present_step_via_dlna(self, session: Dict, step: Dict) -> None:
        projector_device_id = session.get("projector_device_id")
        if not projector_device_id:
            raise RuntimeError("DLNA presentation mode requires a selected projector device.")

        step_dir = os.path.join(self._session_dir(session["session_id"]), "step_images")
        os.makedirs(step_dir, exist_ok=True)
        step_filename = f"step_{step['index']:04d}.jpg"
        step_path = os.path.join(step_dir, step_filename)
        step_bytes = self.render_step_image_for_dlna(session["session_id"], step["index"])
        if step_bytes is None:
            raise RuntimeError(f"Failed to render structured-lighting step {step['index']} for DLNA presentation.")
        with open(step_path, "wb") as handle:
            handle.write(step_bytes)

        runtime = get_app_runtime()
        discovery_manager = runtime.discovery_manager
        resolved_device = self._resolve_dlna_projector(projector_device_id, discovery_manager, runtime)
        if not resolved_device or not getattr(resolved_device, "action_url", None):
            raise RuntimeError("Selected DLNA projector is unavailable or missing an action URL.")

        serve_ip = runtime.get_serve_ip()
        streaming_service = get_streaming_service()
        if self._active_step_stream_server is not None:
            try:
                streaming_service.stop_server(self._active_step_stream_server)
            except Exception:
                pass
            self._active_step_stream_server = None

        files_urls, server = streaming_service.start_server(
            files={step_filename: step_path},
            serve_ip=serve_ip,
            port_range=(9010, 9100),
            device_name=projector_device_id,
            stream_type="structured_lighting_step",
            consumer_id=session["session_id"],
        )
        self._active_step_stream_server = server

        if self._active_step_cast_session_id:
            try:
                self._run_async(discovery_manager.stop_casting(self._active_step_cast_session_id))
            except Exception:
                pass
            self._active_step_cast_session_id = None

        cast_session = self._run_async(
            self._cast_to_resolved_device(
                discovery_manager=discovery_manager,
                target_device=resolved_device,
                selected_device_id=projector_device_id,
                content_url=files_urls[step_filename],
                content_type="image/jpeg",
                title=f"{session['name']} - {step['label']}",
            )
        )
        if not cast_session:
            raise RuntimeError("Failed to cast structured-lighting step to the selected DLNA projector.")
        self._active_step_cast_session_id = cast_session.id

    async def _cast_to_resolved_device(
        self,
        *,
        discovery_manager,
        target_device: Device,
        selected_device_id: str,
        content_url: str,
        content_type: str,
        title: str,
    ):
        registered_device = discovery_manager.get_device_by_id(target_device.id)
        if registered_device is not None:
            return await discovery_manager.cast_content(
                device_id=registered_device.id,
                content_url=content_url,
                content_type=content_type,
                metadata={"title": title},
            )

        backend = discovery_manager._get_backend_for_device(target_device)
        if backend is None:
            return None

        cast_session = await backend.cast_content(
            target_device,
            content_url,
            content_type,
            {"title": title},
        )
        with discovery_manager._device_lock:
            discovery_manager.device_sessions.setdefault(selected_device_id, []).append(cast_session)
        return cast_session

    def _resolve_dlna_projector(self, projector_device_id: str, discovery_manager, runtime) -> Optional[Device]:
        device = discovery_manager.get_device_by_id(projector_device_id)
        if device and getattr(device, "action_url", None):
            return device

        host, port = self._parse_dlna_device_identity(projector_device_id)
        for candidate in discovery_manager.get_all_devices():
            if candidate.casting_method != CastingMethod.DLNA:
                continue
            if host and candidate.hostname != host:
                continue
            if port is not None and candidate.port != port:
                continue
            if getattr(candidate, "action_url", None):
                return candidate

        for legacy_device in runtime.get_devices():
            candidate = self._build_unified_dlna_device(projector_device_id, legacy_device, host, port)
            if candidate is not None:
                return candidate

        return device

    def _parse_dlna_device_identity(self, projector_device_id: str):
        if not projector_device_id.startswith("dlna_"):
            return None, None
        parts = projector_device_id.split("_")
        if len(parts) < 3:
            return None, None
        host = parts[1]
        try:
            port = int(parts[2])
        except ValueError:
            port = None
        return host, port

    def _build_unified_dlna_device(
        self,
        projector_device_id: str,
        legacy_device,
        host: Optional[str],
        port: Optional[int],
    ) -> Optional[Device]:
        action_url = getattr(legacy_device, "action_url", None)
        if not action_url:
            return None

        legacy_name = getattr(legacy_device, "name", None)
        legacy_friendly_name = getattr(legacy_device, "friendly_name", None) or legacy_name or projector_device_id
        legacy_hostname = getattr(legacy_device, "hostname", None)
        parsed = urlparse(action_url)
        action_host = parsed.hostname or legacy_hostname
        action_port = parsed.port or (443 if parsed.scheme == "https" else 80)

        if host and action_host != host:
            return None
        if port is not None and action_port != port:
            return None
        if host is None and projector_device_id not in {legacy_name, legacy_friendly_name}:
            return None

        return Device(
            id=projector_device_id,
            name=legacy_friendly_name,
            friendly_name=legacy_friendly_name,
            casting_method=CastingMethod.DLNA,
            hostname=action_host or host or "unknown",
            port=action_port,
            capabilities=[
                DeviceCapability.IMAGE_DISPLAY,
                DeviceCapability.VIDEO_PLAYBACK,
                DeviceCapability.AUDIO_PLAYBACK,
                DeviceCapability.VOLUME_CONTROL,
                DeviceCapability.SEEK_CONTROL,
            ],
            metadata={},
            action_url=action_url,
            location=getattr(legacy_device, "location", None),
            manufacturer=getattr(legacy_device, "manufacturer", None),
        )

    def _run_async(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _load_sessions_from_disk(self) -> None:
        if not os.path.isdir(self._upload_root):
            return
        for entry in os.listdir(self._upload_root):
            session_dir = os.path.join(self._upload_root, entry)
            session_path = os.path.join(session_dir, "session.json")
            if not os.path.isfile(session_path):
                continue
            try:
                with open(session_path, "r", encoding="utf-8") as handle:
                    session = json.load(handle)
            except Exception:
                continue
            session_id = session.get("session_id")
            if not session_id:
                continue
            self._sessions[session_id] = session

    def _session_dir(self, session_id: str) -> str:
        path = os.path.join(self._upload_root, session_id)
        os.makedirs(path, exist_ok=True)
        return path

    def _ensure_capture_dir(self, session_id: str) -> str:
        capture_dir = os.path.join(self._session_dir(session_id), "captures")
        os.makedirs(capture_dir, exist_ok=True)
        return capture_dir

    def _clear_capture_dir(self, session_id: str) -> None:
        capture_dir = os.path.join(self._session_dir(session_id), "captures")
        if os.path.isdir(capture_dir):
            shutil.rmtree(capture_dir)

    def _ensure_decode_dir(self, session_id: str) -> str:
        decode_dir = os.path.join(self._session_dir(session_id), "decode")
        os.makedirs(decode_dir, exist_ok=True)
        return decode_dir

    def _clear_derived_outputs(self, session_id: str) -> None:
        session_dir = self._session_dir(session_id)
        decode_dir = os.path.join(session_dir, "decode")
        if os.path.isdir(decode_dir):
            shutil.rmtree(decode_dir)
        for filename in ("calibration.json", "export_bundle.zip"):
            path = os.path.join(session_dir, filename)
            if os.path.exists(path):
                os.remove(path)

    def _persist_session(self, session: Dict) -> None:
        session_dir = self._session_dir(session["session_id"])
        with open(os.path.join(session_dir, "session.json"), "w", encoding="utf-8") as handle:
            json.dump(session, handle, indent=2, sort_keys=True)
        calibration_path = os.path.join(session_dir, "calibration.json")
        calibration = session.get("calibration")
        if calibration and calibration.get("status") == "completed":
            with open(calibration_path, "w", encoding="utf-8") as handle:
                json.dump(calibration, handle, indent=2, sort_keys=True)
        elif os.path.exists(calibration_path):
            os.remove(calibration_path)

    def _get_step(self, session: Dict, step_index: int) -> Optional[Dict]:
        plan = self.get_capture_plan(session["session_id"])
        if not plan:
            return None
        for step in plan["steps"]:
            if step["index"] == step_index:
                return step
        return None

    def _find_capture_file(self, capture_dir: str, names: tuple[str, ...]) -> Optional[str]:
        for name in names:
            candidate = os.path.join(capture_dir, name)
            if os.path.exists(candidate):
                return candidate
        return None

    def _decode_raw_cam2proj(self, session_id: str, sample_step: int, tuning_params: Optional[Dict] = None):
        session = self.get_session(session_id)
        if not session:
            raise RuntimeError("Structured lighting session not found")

        capture_dir = self._ensure_capture_dir(session_id)
        white_path = self._find_capture_file(capture_dir, ("img_white.png", "img_white.jpg", "img_white.jpeg"))
        black_path = self._find_capture_file(capture_dir, ("img_black.png", "img_black.jpg", "img_black.jpeg"))
        if not white_path or not black_path:
            raise RuntimeError("Reference white/black captures are missing.")

        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Decoding requires opencv-contrib-python and numpy in the backend environment.") from exc

        params = self._normalize_tuning_params(tuning_params)
        brightness_gain = float(params["brightness_gain"])

        plan = self.get_capture_plan(session_id)
        graycode_steps = [step for step in plan["steps"] if step["kind"] == "graycode"]
        pattern_images = []
        for step in graycode_steps:
            capture_meta = session.get("captures", {}).get(str(step["index"]))
            if not capture_meta:
                raise RuntimeError(f"Missing capture for graycode step {step['index']}.")
            image = cv2.imread(capture_meta["stored_path"], cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise RuntimeError(f"Failed to load capture {capture_meta['stored_path']}.")
            pattern_images.append(self._apply_brightness_gain(image, brightness_gain))

        if hasattr(cv2, "structured_light_GrayCodePattern"):
            graycode = cv2.structured_light_GrayCodePattern.create(session["projector_width"], session["projector_height"])
        elif hasattr(cv2, "structured_light") and hasattr(cv2.structured_light, "GrayCodePattern_create"):
            graycode = cv2.structured_light.GrayCodePattern_create(session["projector_width"], session["projector_height"])
        else:
            raise RuntimeError("OpenCV structured light module is unavailable.")

        graycode.setWhiteThreshold(int(params["white_threshold"]))
        graycode.setBlackThreshold(int(params["black_threshold"]))

        h, w = pattern_images[0].shape
        cam2proj = np.full((h, w, 2), -1, dtype=np.int32)
        row_positions = list(range(0, h, sample_step))
        total_rows = max(1, len(row_positions))
        for row_index, y in enumerate(row_positions):
            for x in range(0, w, sample_step):
                ok, p = graycode.getProjPixel(pattern_images, x, y)
                if ok:
                    cam2proj[y, x, 0] = int(p[0])
                    cam2proj[y, x, 1] = int(p[1])
            if row_index == 0 or row_index == total_rows - 1 or row_index % max(1, total_rows // 12) == 0:
                percent = 8 + int((row_index + 1) / total_rows * 47)
                self._set_decode_progress(
                    session_id,
                    phase="decoding",
                    label=f"Decoding projector correspondence ({row_index + 1}/{total_rows} rows)",
                    percent=min(percent, 55),
                )
        return cam2proj, white_path, black_path

    def _apply_brightness_gain(self, image, gain: float):
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Brightness adjustment requires opencv-contrib-python and numpy in the backend environment.") from exc

        gain = max(0.1, float(gain))
        if abs(gain - 1.0) < 1e-6:
            return image
        adjusted = np.clip(image.astype(np.float32) * gain, 0, 255).astype(np.uint8)
        return adjusted

    def _set_decode_progress(self, session_id: str, *, phase: str, label: str, percent: int) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            decode = {**self._default_decode_state(), **session.get("decode", {})}
            decode["status"] = "running" if phase != "completed" else "completed"
            decode["message"] = label
            decode["progress"] = {
                "phase": phase,
                "label": label,
                "percent": max(0, min(int(percent), 100)),
            }
            session["decode"] = decode
            session["updated_at"] = _utcnow_iso()
            self._persist_session(session)

    def _default_tuning_params(self) -> Dict:
        return {
            "edge_mode": "morph_gradient",
            "brightness_gain": 1.0,
            "white_threshold": 5,
            "black_threshold": 40,
            "median_blur_ksize": 11,
            "bilateral_d": 15,
            "bilateral_sigma_color": 75,
            "bilateral_sigma_space": 75,
            "gradient_kernel_size": 5,
            "canny_low_threshold": 30,
            "canny_high_threshold": 90,
            "laplacian_ksize": 3,
            "segmentation_scale": 1.0,
            "segmentation_threshold": 5,
            "segmentation_blur": 7,
            "room_close_kernel_size": 3,
            "min_area_ratio": 0.001,
            "contrast_threshold": 25,
            "min_projector_component_area": 25,
            "repair_fill_holes": True,
            "repair_restrict_to_bbox": False,
            "repair_max_hole_area": 5000,
            "confidence_low_percentile": 60.0,
            "confidence_high_percentile": 97.0,
            "aggregation_sigma": 1.5,
            "kernel_radius": 5,
            "kernel_sigma": 2.0,
            "kernel_min_valid_neighbors": 6,
            "kernel_max_passes": 6,
            "second_pass_kernel_radius": 9,
            "second_pass_kernel_sigma": 3.5,
            "second_pass_min_valid_neighbors": 10,
            "second_pass_max_passes": 4,
            "layer_min_area": 1000,
        }

    def _normalize_tuning_params(self, overrides: Optional[Dict] = None) -> Dict:
        params = self._default_tuning_params()
        if overrides:
            params.update(overrides)
        params["brightness_gain"] = max(0.1, float(params["brightness_gain"]))
        params["white_threshold"] = int(max(0, min(255, int(params["white_threshold"]))))
        params["black_threshold"] = int(max(0, min(255, int(params["black_threshold"]))))
        return params

    def _parameter_search_candidates(self, base_params: Optional[Dict] = None, parameter_grid: Optional[Dict] = None) -> List[Dict]:
        normalized_base = self._normalize_tuning_params(base_params)
        normalized_grid = self._normalize_parameter_grid(parameter_grid)
        grid_candidates = []
        seen = set()

        for edge_mode in normalized_grid["edge_mode"]:
            for brightness_gain in normalized_grid["brightness_gain"]:
                for white_threshold in normalized_grid["white_threshold"]:
                    for black_threshold in normalized_grid["black_threshold"]:
                        key = (edge_mode, brightness_gain, white_threshold, black_threshold)
                        if key in seen:
                            continue
                        seen.add(key)
                        params = self._normalize_tuning_params(
                            {
                                **normalized_base,
                                "edge_mode": edge_mode,
                                "brightness_gain": brightness_gain,
                                "white_threshold": white_threshold,
                                "black_threshold": black_threshold,
                            }
                        )
                        grid_candidates.append(
                            {
                                "label": f"{edge_mode} • b{brightness_gain:g} • w{white_threshold} • k{black_threshold}",
                                "description": "Grid search candidate across edge mode, brightness, and GrayCode thresholds.",
                                "params": params,
                            }
                        )
                        if len(grid_candidates) >= 18:
                            return grid_candidates

        if grid_candidates:
            return grid_candidates

        return [
            {
                "label": "Balanced",
                "description": "Default repair and layer filtering.",
                "params": self._normalize_tuning_params(normalized_base),
            },
            {
                "label": "Canny Edges",
                "description": "Use Canny edges for crisper boundary extraction before segmentation.",
                "params": self._normalize_tuning_params({
                    **normalized_base,
                    "edge_mode": "canny",
                    "canny_low_threshold": 25,
                    "canny_high_threshold": 80,
                    "segmentation_threshold": 4,
                    "segmentation_blur": 5,
                }),
            },
            {
                "label": "Laplacian Edges",
                "description": "Use Laplacian edges to emphasize softer wall boundaries.",
                "params": self._normalize_tuning_params({
                    **normalized_base,
                    "edge_mode": "laplacian",
                    "laplacian_ksize": 5,
                    "segmentation_blur": 9,
                    "layer_min_area": 750,
                }),
            },
            {
                "label": "Fine Layers",
                "description": "Keep smaller layers and sharper segmentation.",
                "params": self._normalize_tuning_params({**normalized_base, "segmentation_blur": 5, "layer_min_area": 250}),
            },
            {
                "label": "Smooth Segmentation",
                "description": "Heavier blur for cleaner large regions.",
                "params": self._normalize_tuning_params({**normalized_base, "segmentation_blur": 11}),
            },
            {
                "label": "Low Threshold",
                "description": "More aggressive wall detection and lighter layer filtering.",
                "params": self._normalize_tuning_params({**normalized_base, "segmentation_threshold": 3, "contrast_threshold": 20, "layer_min_area": 500}),
            },
            {
                "label": "High Contrast",
                "description": "Stricter trusted pixels and more conservative masks.",
                "params": self._normalize_tuning_params({**normalized_base, "contrast_threshold": 35, "layer_min_area": 2500}),
            },
            {
                "label": "Strict Segmentation",
                "description": "Higher segmentation threshold with smoother region boundaries.",
                "params": self._normalize_tuning_params({**normalized_base, "segmentation_threshold": 7, "segmentation_blur": 11, "layer_min_area": 1000}),
            },
            {
                "label": "Wide Gradient",
                "description": "Use a broader morphological gradient kernel for large structural edges.",
                "params": self._normalize_tuning_params({
                    **normalized_base,
                    "edge_mode": "morph_gradient",
                    "gradient_kernel_size": 9,
                    "segmentation_blur": 9,
                    "layer_min_area": 1200,
                }),
            },
        ]

    def _normalize_parameter_grid(self, parameter_grid: Optional[Dict] = None) -> Dict:
        grid = parameter_grid or {}

        def _normalize_numeric_list(key: str, fallback: List[float], cast):
            raw_values = grid.get(key)
            if not isinstance(raw_values, list) or not raw_values:
                return fallback
            values = []
            for item in raw_values:
                try:
                    values.append(cast(item))
                except (TypeError, ValueError):
                    continue
            return values or fallback

        edge_modes = grid.get("edge_mode")
        if not isinstance(edge_modes, list) or not edge_modes:
            edge_modes = ["morph_gradient", "canny", "laplacian"]
        edge_modes = [
            str(item)
            for item in edge_modes
            if str(item) in {"morph_gradient", "canny", "laplacian"}
        ] or ["morph_gradient", "canny", "laplacian"]

        return {
            "edge_mode": edge_modes,
            "brightness_gain": _normalize_numeric_list("brightness_gain", [1.0], float),
            "white_threshold": _normalize_numeric_list("white_threshold", [5, 12], int),
            "black_threshold": _normalize_numeric_list("black_threshold", [30, 40, 55], int),
        }

    def _artifact_preview_specs(self) -> List[tuple[str, str, str]]:
        return [
            ("valid-mask", "Camera Valid Mask", "White pixels decoded to projector coordinates."),
            ("projector-coverage", "Projector Coverage", "Projector pixels hit by at least one camera sample."),
            ("cam2proj-xy", "Camera To Projector Map", "Red and green encode projector X/Y for valid camera pixels."),
        ]

    def _can_render_artifact_preview(self, session_id: str, preview_id: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        artifacts = session.get("decode", {}).get("artifacts", {})
        required = {
            "valid-mask": ("valid_mask_cam",),
            "projector-coverage": ("proj2cam_x",),
            "cam2proj-xy": ("cam2proj",),
        }.get(preview_id)
        if not required:
            return False
        for artifact_key in required:
            artifact_path = artifacts.get(artifact_key)
            if not artifact_path or not os.path.exists(artifact_path):
                return False
        return True

    def _default_decode_state(self) -> Dict:
        return {
            "status": "not_started",
            "started_at": None,
            "finished_at": None,
            "message": "Decode has not run yet.",
            "progress": None,
            "metrics": {},
            "artifacts": {},
        }

    def _default_calibration_state(self) -> Dict:
        return {
            "status": "not_started",
            "message": "Calibration record has not been generated yet.",
            "generated_at": None,
            "summary": {},
            "artifacts": {},
        }

    def _default_review_state(self) -> Dict:
        return {
            "status": "pending",
            "message": "Artifact review has not been completed yet.",
            "notes": "",
            "reviewed_by": "",
            "accepted_at": None,
            "updated_at": None,
        }

    def _default_tuning_search_state(self) -> Dict:
        return {
            "status": "not_started",
            "message": "Parameter search has not run yet.",
            "generated_at": None,
            "sample_step": 1,
            "candidates": [],
            "progress": None,
        }

    def _default_preview_tuning_state(self) -> Dict:
        return {
            "status": "not_started",
            "message": "Preview tuning has not run yet.",
            "generated_at": None,
            "sample_step": 1,
            "candidates": [],
            "progress": None,
        }

    def _build_calibration_record(self, session: Dict, decode_result: Dict) -> Dict:
        artifacts = decode_result.get("artifacts", {})
        summary = {
            "projector_width": session["projector_width"],
            "projector_height": session["projector_height"],
            "camera_index": session["camera_index"],
            "presentation_mode": session["presentation_mode"],
            **decode_result.get("metrics", {}),
        }
        return {
            "status": "completed",
            "message": "Calibration record generated from Gray-code decode.",
            "generated_at": _utcnow_iso(),
            "summary": summary,
            "artifacts": {
                "cam2proj": artifacts.get("cam2proj"),
                "proj2cam_x": artifacts.get("proj2cam_x"),
                "proj2cam_y": artifacts.get("proj2cam_y"),
                "valid_mask_cam": artifacts.get("valid_mask_cam"),
                "decode_manifest": os.path.join(artifacts.get("decode_dir", ""), "decode_manifest.json") if artifacts.get("decode_dir") else None,
            },
        }

    def _build_review_state(self, decode_result: Dict) -> Dict:
        coverage_ratio = decode_result.get("metrics", {}).get("coverage_ratio")
        message = "Review coverage and projector correspondence previews before export."
        if isinstance(coverage_ratio, (int, float)) and coverage_ratio < 0.45:
            message = "Coverage is low. Recapture is recommended before export."
        return {
            "status": "pending",
            "message": message,
            "notes": "",
            "reviewed_by": "",
            "accepted_at": None,
            "updated_at": _utcnow_iso(),
        }


_service = StructuredLightingService()


def get_structured_lighting_service() -> StructuredLightingService:
    return _service
