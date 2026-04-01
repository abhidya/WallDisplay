import asyncio
import threading

from web.backend.services.overlay_event_bus import notify_overlay_config_update, overlay_events


def test_notify_overlay_config_update_broadcasts_from_sync_thread():
    ready = threading.Event()
    stop = threading.Event()
    result = {}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def connect_and_wait():
            queue = await overlay_events.connect()
            result["loop"] = loop
            result["queue"] = queue
            ready.set()
            while not stop.is_set():
                await asyncio.sleep(0.01)
            overlay_events.disconnect(queue)

        loop.run_until_complete(connect_and_wait())
        loop.close()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()

    try:
        assert ready.wait(timeout=2), "Timed out waiting for overlay event loop setup"

        notify_overlay_config_update([7], "mapping_scene_updated")

        event = asyncio.run_coroutine_threadsafe(result["queue"].get(), result["loop"]).result(timeout=2)
        assert event == {
            "type": "config_updated",
            "data": {
                "config_ids": [7],
                "reason": "mapping_scene_updated",
            },
        }
    finally:
        stop.set()
        thread.join(timeout=2)
