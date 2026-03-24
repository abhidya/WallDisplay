import argparse
import io
import socket
import time
import uuid
from pathlib import Path

import requests


def get_hostname():
    try:
        return socket.gethostname()
    except Exception:
        return "unknown-host"


def heartbeat(base_url, worker_id, hostname, camera_index):
    response = requests.post(
        f"{base_url}/api/structured-lighting/worker/heartbeat",
        json={
            "worker_id": worker_id,
            "hostname": hostname,
            "camera_indices": [camera_index],
            "state": "idle",
            "message": "Structured-lighting worker online.",
        },
        timeout=5,
    )
    response.raise_for_status()


def claim_next_step(base_url, worker_id):
    response = requests.get(
        f"{base_url}/api/structured-lighting/worker/{worker_id}/next-step",
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("step")


def upload_placeholder_capture(base_url, session_id, step_index):
    content = io.BytesIO()
    content.write(b"\x89PNG\r\n\x1a\n")
    content.seek(0)
    response = requests.post(
        f"{base_url}/api/structured-lighting/sessions/{session_id}/captures",
        data={"step_index": step_index},
        files={"capture": (f"step_{step_index:03d}.png", content.getvalue(), "image/png")},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def download_step_image(base_url, step_image_url, session_id, step_index):
    response = requests.get(f"{base_url}{step_image_url}", timeout=15)
    response.raise_for_status()
    preview_dir = Path("/tmp/structured_lighting_patterns") / session_id
    preview_dir.mkdir(parents=True, exist_ok=True)
    output_path = preview_dir / f"step_{step_index:03d}.png"
    output_path.write_bytes(response.content)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Structured-lighting host worker")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--camera-index", type=int, default=1)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()

    worker_id = str(uuid.uuid4())
    hostname = get_hostname()

    print(f"worker_id={worker_id}")
    print(f"hostname={hostname}")
    print(f"camera_index={args.camera_index}")

    while True:
        heartbeat(args.base_url, worker_id, hostname, args.camera_index)
        step = claim_next_step(args.base_url, worker_id)
        if step:
            print(f"claimed session={step['session_id']} step={step['step']['index']} label={step['step']['label']}")
            pattern_path = download_step_image(
                args.base_url,
                step["step_image_url"],
                step["session_id"],
                step["step"]["index"],
            )
            print(f"downloaded pattern preview to {pattern_path}")
            upload_placeholder_capture(args.base_url, step["session_id"], step["step"]["index"])
            print("uploaded placeholder capture")
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
