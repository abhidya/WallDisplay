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
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional
from urllib.parse import urlparse

from PIL import Image
from core.streaming_service import get_streaming_service
from discovery.base import CastingMethod, Device, DeviceCapability
from services.app_runtime import get_app_runtime


WORKER_TIMEOUT_SECONDS = 15


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
        now = datetime.utcnow()
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
        settle_seconds: float = 0.8,
        flush_count: int = 20,
        pump_ms: int = 250,
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
            now = datetime.utcnow().isoformat()
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
                "process_exited_at": datetime.utcnow().isoformat(),
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
            session["status"] = "waiting_for_worker" if not self._worker_is_connected() else "ready"
            session["current_step_index"] = 0
            session["captured_frames"] = 0
            session["last_capture_at"] = None
            session["captured_step_indices"] = []
            session["decode"] = self._default_decode_state()
            session["calibration"] = self._default_calibration_state()
            session["review"] = self._default_review_state()
            session["updated_at"] = datetime.utcnow().isoformat()
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
                    session["updated_at"] = datetime.utcnow().isoformat()
                    self._persist_session(session)
                    continue
                step = plan["steps"][current_step_index]
                if session["presentation_mode"] == "dlna_step":
                    self._present_step_via_dlna(session, step)
                session["status"] = "capturing"
                session["updated_at"] = datetime.utcnow().isoformat()
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
                "captured_at": datetime.utcnow().isoformat(),
            }
            session["captures"] = captures

            captured_steps = list(session.get("captured_step_indices", []))
            if step_index not in captured_steps:
                captured_steps.append(step_index)
                captured_steps.sort()
            session["captured_step_indices"] = captured_steps
            session["captured_frames"] = len(captured_steps)
            session["last_capture_at"] = datetime.utcnow().isoformat()
            session["current_step_index"] = step_index + 1
            session["status"] = "ready" if session["captured_frames"] < session["pattern_frame_count"] else "completed"
            session["decode"] = self._default_decode_state()
            session["calibration"] = self._default_calibration_state()
            session["review"] = self._default_review_state()
            session["updated_at"] = datetime.utcnow().isoformat()
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
        return {
            "session_id": session_id,
            "captures": captures,
            "captured_frames": session.get("captured_frames", 0),
            "expected_frames": session["pattern_frame_count"],
        }

    def decode_session(self, session_id: str, sample_step: int = 1) -> Optional[Dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            self._clear_derived_outputs(session_id)
            session["decode"] = {
                **self._default_decode_state(),
                "status": "running",
                "started_at": datetime.utcnow().isoformat(),
            }
            session["calibration"] = self._default_calibration_state()
            session["review"] = self._default_review_state()
            session["updated_at"] = datetime.utcnow().isoformat()
            self._persist_session(session)

        try:
            result = self._decode_graycode_session(session_id, sample_step=max(1, sample_step))
        except Exception as exc:
            with self._lock:
                session = self._sessions.get(session_id)
                if session:
                    session["decode"] = {
                        **self._default_decode_state(),
                        "status": "failed",
                        "started_at": session.get("decode", {}).get("started_at"),
                        "finished_at": datetime.utcnow().isoformat(),
                        "message": str(exc),
                    }
                    session["updated_at"] = datetime.utcnow().isoformat()
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
            session["updated_at"] = datetime.utcnow().isoformat()
            self._persist_session(session)
            return dict(session)

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
            review["updated_at"] = datetime.utcnow().isoformat()
            review["accepted_at"] = review["updated_at"] if verdict == "accepted" else None
            review["message"] = (
                "Session accepted for export." if verdict == "accepted"
                else "Session marked for recapture."
            )
            session["review"] = review
            session["updated_at"] = datetime.utcnow().isoformat()
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
                for entry in sorted(os.listdir(decode_dir)):
                    full_path = os.path.join(decode_dir, entry)
                    if os.path.isfile(full_path):
                        archive.write(full_path, arcname=f"decode/{entry}")

            capture_dir = os.path.join(bundle_dir, "captures")
            if os.path.isdir(capture_dir):
                for entry in sorted(os.listdir(capture_dir)):
                    full_path = os.path.join(capture_dir, entry)
                    if os.path.isfile(full_path):
                        archive.write(full_path, arcname=f"captures/{entry}")

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
            session["updated_at"] = datetime.utcnow().isoformat()
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
        now = datetime.utcnow().isoformat()
        bit_planes_x = max(1, math.ceil(math.log2(max(2, projector_width))))
        bit_planes_y = max(1, math.ceil(math.log2(max(2, projector_height))))
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
            "pattern_frame_count": 2 + (bit_planes_x + bit_planes_y) * 2,
            "current_step_index": 0,
            "captured_frames": 0,
            "captured_step_indices": [],
            "captures": {},
            "decode": self._default_decode_state(),
            "calibration": self._default_calibration_state(),
            "review": self._default_review_state(),
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

        step_index = 2
        for axis, plane_count in (("x", session["bit_planes_x"]), ("y", session["bit_planes_y"])):
            for bit in range(plane_count):
                for polarity in ("normal", "inverse"):
                    steps.append(
                        {
                            "index": step_index,
                            "kind": "graycode",
                            "axis": axis,
                            "bit": bit,
                            "polarity": polarity,
                            "label": f"{axis.upper()} bit {bit} ({polarity})",
                            "hold_ms": session["hold_ms"],
                            "capture_required": True,
                        }
                    )
                    step_index += 1

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

        session = plan["session"]
        width = session["projector_width"]
        height = session["projector_height"]
        step = steps[step_index]

        image = Image.new("L", (width, height), color=0)
        pixels = image.load()

        if step["kind"] == "reference_white":
            for y in range(height):
                for x in range(width):
                    pixels[x, y] = 255
        elif step["kind"] == "reference_black":
            pass
        elif step["kind"] == "graycode":
            axis = step["axis"]
            bit = step["bit"]
            inverse = step["polarity"] == "inverse"
            if axis == "x":
                for x in range(width):
                    gray = x ^ (x >> 1)
                    bit_value = (gray >> bit) & 1
                    value = 255 if bit_value else 0
                    if inverse:
                        value = 255 - value
                    for y in range(height):
                        pixels[x, y] = value
            else:
                for y in range(height):
                    gray = y ^ (y >> 1)
                    bit_value = (gray >> bit) & 1
                    value = 255 if bit_value else 0
                    if inverse:
                        value = 255 - value
                    for x in range(width):
                        pixels[x, y] = value

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

    def _decode_graycode_session(self, session_id: str, sample_step: int) -> Dict:
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
            pattern_images.append(image)

        white_img = cv2.imread(white_path, cv2.IMREAD_GRAYSCALE)
        black_img = cv2.imread(black_path, cv2.IMREAD_GRAYSCALE)
        if white_img is None or black_img is None:
            raise RuntimeError("Failed to read reference captures.")

        if hasattr(cv2, "structured_light_GrayCodePattern"):
            graycode = cv2.structured_light_GrayCodePattern.create(session["projector_width"], session["projector_height"])
        elif hasattr(cv2, "structured_light") and hasattr(cv2.structured_light, "GrayCodePattern_create"):
            graycode = cv2.structured_light.GrayCodePattern_create(session["projector_width"], session["projector_height"])
        else:
            raise RuntimeError("OpenCV structured light module is unavailable.")

        graycode.setWhiteThreshold(5)
        graycode.setBlackThreshold(40)

        imgs = pattern_images
        h, w = imgs[0].shape
        cam2proj = np.full((h, w, 2), -1, dtype=np.int32)
        valid = 0

        for y in range(0, h, sample_step):
            for x in range(0, w, sample_step):
                ok, p = graycode.getProjPixel(imgs, x, y)
                if ok:
                    cam2proj[y, x, 0] = int(p[0])
                    cam2proj[y, x, 1] = int(p[1])
                    valid += 1

        if sample_step > 1:
            cam2proj_u = cv2.resize(cam2proj.astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST).astype(np.int32)
        else:
            cam2proj_u = cam2proj

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

        white_delta = float(white_img.mean() - black_img.mean())
        coverage = float(valid_mask_cam.sum()) / float(valid_mask_cam.size) if valid_mask_cam.size else 0.0
        manifest = {
            "status": "completed",
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "message": "Gray-code decode completed.",
            "metrics": {
                "camera_width": int(w),
                "camera_height": int(h),
                "valid_camera_pixels": int(valid_mask_cam.sum()),
                "valid_projector_samples": int(np.isfinite(proj2cam_x).sum()),
                "coverage_ratio": round(coverage, 4),
                "white_black_mean_delta": round(white_delta, 2),
                "sample_step": sample_step,
            },
            "artifacts": {
                "decode_dir": decode_dir,
                "cam2proj": os.path.join(decode_dir, "cam2proj.npy"),
                "valid_mask_cam": os.path.join(decode_dir, "valid_mask_cam.npy"),
                "proj2cam_x": os.path.join(decode_dir, "proj2cam_x.npy"),
                "proj2cam_y": os.path.join(decode_dir, "proj2cam_y.npy"),
            },
        }
        with open(os.path.join(decode_dir, "decode_manifest.json"), "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
        return manifest

    def _worker_is_connected(self) -> bool:
        last_seen = self._worker.get("last_seen_at")
        if not last_seen:
            return False
        try:
            last_seen_dt = datetime.fromisoformat(last_seen)
        except ValueError:
            return False
        return (datetime.utcnow() - last_seen_dt).total_seconds() <= WORKER_TIMEOUT_SECONDS

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
        self._worker["process_exited_at"] = datetime.utcnow().isoformat()
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

    def _session_dir(self, session_id: str) -> str:
        path = os.path.join(self._upload_root, session_id)
        os.makedirs(path, exist_ok=True)
        return path

    def _ensure_capture_dir(self, session_id: str) -> str:
        capture_dir = os.path.join(self._session_dir(session_id), "captures")
        os.makedirs(capture_dir, exist_ok=True)
        return capture_dir

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
            "generated_at": datetime.utcnow().isoformat(),
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
            "updated_at": datetime.utcnow().isoformat(),
        }


_service = StructuredLightingService()


def get_structured_lighting_service() -> StructuredLightingService:
    return _service
