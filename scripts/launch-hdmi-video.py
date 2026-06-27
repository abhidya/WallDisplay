#!/usr/bin/env python3
"""Launch a video URL through WallDisplay's controlled HDMI renderer API."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8088")
    parser.add_argument("--projector-id", default="proj-hdmi-local")
    parser.add_argument("--video-url")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    video_url = args.video_url or f"{base_url}/backend-static/generated/hdmi_test.mp4"
    page_url = (
        f"{base_url}/backend-static/hdmi_video_player.html"
        f"?projector_id={urllib.parse.quote(args.projector_id)}"
        f"&src={urllib.parse.quote(video_url, safe='')}"
    )
    payload = json.dumps(
        {
            "content_url": page_url,
            "content_mode": "video",
            "options": {"source": "launch-hdmi-video"},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/renderer/projectors/{urllib.parse.quote(args.projector_id)}/url",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
