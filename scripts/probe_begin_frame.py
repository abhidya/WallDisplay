#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import json
from pathlib import Path

from playwright.async_api import async_playwright


DEFAULT_SHELL = (
    "/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/"
    "chrome-headless-shell/mac-147.0.7727.24/chrome-headless-shell-mac-x64/chrome-headless-shell"
)


async def run_probe(args: argparse.Namespace) -> dict:
    result: dict = {
        "executable_path": args.executable_path,
        "url": args.url,
        "frames_requested": args.frames,
        "frame_interval_ms": args.interval_ms,
        "jpeg_quality": args.quality,
        "launch_args": args.launch_arg,
        "frames": [],
        "error": None,
    }
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            executable_path=args.executable_path,
            args=args.launch_arg,
        )
        page = await browser.new_page(viewport={"width": args.width, "height": args.height})
        console_tail: list[dict[str, str]] = []
        page_errors: list[str] = []
        page.on("console", lambda msg: console_tail.append({"type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        try:
            await page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            if args.settle_ms > 0:
                await page.wait_for_timeout(args.settle_ms)
            cdp = await page.context.new_cdp_session(page)
            for index in range(args.frames):
                payload = {
                    "interval": float(args.interval_ms),
                    "screenshot": {
                        "format": "jpeg",
                        "quality": args.quality,
                    },
                }
                if args.no_display_updates:
                    payload["noDisplayUpdates"] = True
                response = await cdp.send("HeadlessExperimental.beginFrame", payload)
                screenshot_data = response.get("screenshotData")
                frame_info = {
                    "index": index,
                    "hasDamage": response.get("hasDamage"),
                    "hasScreenshotData": bool(screenshot_data),
                    "screenshotBytes": len(base64.b64decode(screenshot_data)) if screenshot_data else 0,
                }
                result["frames"].append(frame_info)
                if args.interval_ms > 0:
                    await page.wait_for_timeout(args.interval_ms)
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            result["console_tail"] = console_tail[-20:]
            result["page_errors"] = page_errors[-20:]
            await browser.close()
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe HeadlessExperimental.beginFrame.")
    parser.add_argument("--url", default="about:blank")
    parser.add_argument("--executable-path", default=DEFAULT_SHELL)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--frames", type=int, default=3)
    parser.add_argument("--interval-ms", type=int, default=333)
    parser.add_argument("--quality", type=int, default=22)
    parser.add_argument("--settle-ms", type=int, default=1000)
    parser.add_argument("--timeout-ms", type=int, default=20000)
    parser.add_argument("--no-display-updates", action="store_true")
    parser.add_argument("--launch-arg", action="append", default=[])
    parser.add_argument("--output-json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = asyncio.run(run_probe(args))
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output_json:
        Path(args.output_json).write_text(text)
    print(text)
    return 0 if result["error"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
