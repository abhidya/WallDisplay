import argparse
import socket
import time
import uuid
from pathlib import Path
from typing import Optional

import requests
import numpy as np

try:
    import cv2
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise SystemExit("OpenCV is required for structured-lighting capture worker.") from exc


def get_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown-host"


def heartbeat(
    base_url: str,
    worker_id: str,
    hostname: str,
    camera_index: int,
    state: str = "idle",
    message: Optional[str] = None,
):
    response = requests.post(
        f"{base_url}/api/structured-lighting/worker/heartbeat",
        json={
            "worker_id": worker_id,
            "hostname": hostname,
            "camera_indices": [camera_index],
            "state": state,
            "message": message or "Structured-lighting worker online.",
        },
        timeout=5,
    )
    response.raise_for_status()


def claim_next_step(base_url: str, worker_id: str):
    response = requests.get(
        f"{base_url}/api/structured-lighting/worker/{worker_id}/next-step",
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("step")


def get_worker_control(base_url: str, worker_id: str):
    response = requests.get(
        f"{base_url}/api/structured-lighting/worker/{worker_id}/control",
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def upload_capture(base_url: str, session_id: str, step_index: int, frame, ext: str = ".png"):
    ok, encoded = cv2.imencode(ext, frame)
    if not ok:
        raise RuntimeError("Failed to encode camera frame for upload.")

    response = requests.post(
        f"{base_url}/api/structured-lighting/sessions/{session_id}/captures",
        data={"step_index": step_index},
        files={"capture": (f"step_{step_index:03d}{ext}", encoded.tobytes(), "image/png")},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def download_step_image(base_url: str, step_image_url: str, session_id: str, step_index: int) -> Path:
    response = requests.get(f"{base_url}{step_image_url}", timeout=15)
    response.raise_for_status()
    preview_dir = Path("/tmp/structured_lighting_patterns") / session_id
    preview_dir.mkdir(parents=True, exist_ok=True)
    output_path = preview_dir / f"step_{step_index:03d}.png"
    output_path.write_bytes(response.content)
    return output_path


def open_camera(camera_index: int):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Camera {camera_index} failed to open.")
    return cap


def wait_for_operator_confirmation(base_url: str, worker_id: str, hostname: str, camera_index: int, cap, preview_window: str):
    cv2.namedWindow(preview_window, cv2.WINDOW_NORMAL)
    print("Camera preview is live.")
    print("Confirm camera framing from the web UI to arm capture.")
    print("Press ESC to abort.")

    last_heartbeat_at = 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        cv2.imshow(preview_window, frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            raise SystemExit("Capture worker aborted by operator.")

        now = time.time()
        if now - last_heartbeat_at >= 1.0:
            heartbeat(
                base_url,
                worker_id,
                hostname,
                camera_index,
                state="awaiting_operator",
                message="Camera preview is live. Confirm framing in the web UI.",
            )
            last_heartbeat_at = now

        control = get_worker_control(base_url, worker_id)
        if control.get("operator_ready"):
            return


def create_projector_window(name: str, screen_x: int, screen_y: int, width: int, height: int):
    cv2.namedWindow(name, cv2.WINDOW_NORMAL)
    cv2.moveWindow(name, screen_x, screen_y)
    cv2.imshow(name, np.zeros((height, width), dtype=np.uint8))
    cv2.waitKey(50)
    cv2.setWindowProperty(name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    for _ in range(10):
        cv2.waitKey(50)


def show_projector_frame(window_name: str, frame, pump_ms: int = 200):
    cv2.imshow(window_name, frame)
    cv2.waitKey(max(pump_ms, 1))


def flush_and_read(cap, flush_count: int):
    for _ in range(max(flush_count, 0)):
        cap.grab()
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError("Failed to capture frame from camera.")
    return frame


def capture_step(
    cap,
    projector_window: Optional[str],
    pattern_image_path: Optional[Path],
    presentation_mode: str,
    settle_seconds: float,
    flush_count: int,
    pump_ms: int,
):
    if presentation_mode == "dlna_step":
        time.sleep(max(settle_seconds, 0.0))
        return flush_and_read(cap, flush_count=flush_count)

    if not projector_window or not pattern_image_path:
        raise RuntimeError("Local projector presentation requires a projector window and pattern image.")

    pattern = cv2.imread(str(pattern_image_path), cv2.IMREAD_GRAYSCALE)
    if pattern is None:
        raise RuntimeError(f"Failed to load projected pattern {pattern_image_path}")

    show_projector_frame(projector_window, pattern, pump_ms=pump_ms)
    time.sleep(max(settle_seconds, 0.0))
    return flush_and_read(cap, flush_count=flush_count)


def main():
    parser = argparse.ArgumentParser(description="Structured-lighting host worker")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--worker-id", default="")
    parser.add_argument("--camera-index", type=int, default=1)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--projector-screen-x", type=int, default=1280)
    parser.add_argument("--projector-screen-y", type=int, default=0)
    parser.add_argument("--projector-width", type=int, default=1280)
    parser.add_argument("--projector-height", type=int, default=720)
    parser.add_argument("--preview-window", default="STRUCTURED_LIGHT_CAMERA")
    parser.add_argument("--projector-window", default="STRUCTURED_LIGHT_PROJECTOR")
    parser.add_argument("--settle-seconds", type=float, default=0.8)
    parser.add_argument("--flush-count", type=int, default=20)
    parser.add_argument("--pump-ms", type=int, default=250)
    args = parser.parse_args()

    worker_id = args.worker_id or str(uuid.uuid4())
    hostname = get_hostname()

    print(f"worker_id={worker_id}")
    print(f"hostname={hostname}")
    print(f"camera_index={args.camera_index}")

    cap = open_camera(args.camera_index)
    try:
        heartbeat(
            args.base_url,
            worker_id,
            hostname,
            args.camera_index,
            state="starting",
            message="Structured-lighting worker started. Opening camera preview.",
        )
        wait_for_operator_confirmation(
            args.base_url,
            worker_id,
            hostname,
            args.camera_index,
            cap,
            args.preview_window,
        )
        while True:
            try:
                heartbeat(
                    args.base_url,
                    worker_id,
                    hostname,
                    args.camera_index,
                    state="idle",
                    message="Worker ready for next structured-lighting step.",
                )
                step = claim_next_step(args.base_url, worker_id)
                if not step:
                    time.sleep(args.poll_seconds)
                    continue

                step_index = step["step"]["index"]
                session_id = step["session_id"]
                label = step["step"]["label"]
                heartbeat(
                    args.base_url,
                    worker_id,
                    hostname,
                    args.camera_index,
                    state="capturing",
                    message=f"Capturing step {step_index}: {label}",
                )

                print(f"claimed session={session_id} step={step_index} label={label}")
                presentation_mode = step.get("presentation_mode", "dlna_step")
                pattern_path = None
                projector_window = None
                if presentation_mode != "dlna_step":
                    create_projector_window(
                        args.projector_window,
                        args.projector_screen_x,
                        args.projector_screen_y,
                        args.projector_width,
                        args.projector_height,
                    )
                    projector_window = args.projector_window
                    pattern_path = download_step_image(
                        args.base_url,
                        step["step_image_url"],
                        session_id,
                        step_index,
                    )
                frame = capture_step(
                    cap,
                    projector_window,
                    pattern_path,
                    presentation_mode,
                    settle_seconds=args.settle_seconds,
                    flush_count=args.flush_count,
                    pump_ms=args.pump_ms,
                )
                upload_capture(args.base_url, session_id, step_index, frame)
                print(f"captured and uploaded step {step_index} for session {session_id}")
            except Exception as exc:
                print(f"structured-lighting step failed: {exc}")
                try:
                    heartbeat(
                        args.base_url,
                        worker_id,
                        hostname,
                        args.camera_index,
                        state="error",
                        message=f"Structured-lighting step failed: {exc}",
                    )
                except Exception:
                    pass
                time.sleep(args.poll_seconds)
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
