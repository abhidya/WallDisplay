import math
import os
import threading
import uuid
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Optional

from PIL import Image


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
        }
        self._upload_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "uploads",
            "structured_lighting",
        )

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
            self._worker = {
                "worker_id": worker_id,
                "state": state,
                "connected": True,
                "last_seen_at": now.isoformat(),
                "camera_indices": camera_indices,
                "hostname": hostname,
                "message": message or "Host capture worker connected.",
            }
        return self._get_worker_status()

    def start_session(self, session_id: str) -> Optional[Dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            session["status"] = "waiting_for_worker" if not self._worker_is_connected() else "ready"
            session["current_step_index"] = 0
            session["captured_frames"] = 0
            session["last_capture_at"] = None
            session["captured_step_indices"] = []
            session["updated_at"] = datetime.utcnow().isoformat()
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
                    continue
                session["status"] = "capturing"
                session["updated_at"] = datetime.utcnow().isoformat()
                return {
                    "session_id": session["session_id"],
                    "session_name": session["name"],
                    "step": plan["steps"][current_step_index],
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
            capture_dir = self._ensure_capture_dir(session_id)
            extension = os.path.splitext(original_filename or "")[1].lower() or ".png"
            stored_name = f"step_{step_index:03d}{extension}"
            stored_path = os.path.join(capture_dir, stored_name)
            with open(stored_path, "wb") as handle:
                handle.write(file_bytes)

            captured_steps = list(session.get("captured_step_indices", []))
            if step_index not in captured_steps:
                captured_steps.append(step_index)
                captured_steps.sort()
            session["captured_step_indices"] = captured_steps
            session["captured_frames"] = len(captured_steps)
            session["last_capture_at"] = datetime.utcnow().isoformat()
            session["current_step_index"] = step_index + 1
            session["status"] = "ready" if session["captured_frames"] < session["pattern_frame_count"] else "completed"
            session["updated_at"] = datetime.utcnow().isoformat()
            return dict(session)

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
        worker = dict(self._worker)
        if not self._worker_is_connected():
            worker["connected"] = False
            worker["state"] = "unavailable"
            worker["message"] = "Host capture worker not connected yet."
        return worker

    def _ensure_capture_dir(self, session_id: str) -> str:
        capture_dir = os.path.join(self._upload_root, session_id, "captures")
        os.makedirs(capture_dir, exist_ok=True)
        return capture_dir

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
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._sessions[session["session_id"]] = session
        return dict(session)

    def get_session(self, session_id: str) -> Optional[Dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            return dict(session) if session else None

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

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


_service = StructuredLightingService()


def get_structured_lighting_service() -> StructuredLightingService:
    return _service
