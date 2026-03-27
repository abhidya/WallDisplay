import asyncio
from asyncio import Queue
from typing import Iterable, Set


class OverlayEventManager:
    def __init__(self):
        self.connections: Set[Queue] = set()

    async def connect(self) -> Queue:
        queue = Queue()
        self.connections.add(queue)
        return queue

    def disconnect(self, queue: Queue):
        self.connections.discard(queue)

    async def broadcast(self, event_type: str, data: dict):
        disconnected = set()
        for queue in self.connections:
            try:
                queue.put_nowait({"type": event_type, "data": data})
            except asyncio.QueueFull:
                disconnected.add(queue)

        for queue in disconnected:
            self.disconnect(queue)


overlay_events = OverlayEventManager()


def broadcast_overlay_event(event_type: str, data: dict) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(overlay_events.broadcast(event_type, data))


def notify_overlay_config_update(config_ids: Iterable[int], reason: str) -> None:
    normalized_ids = sorted({int(config_id) for config_id in config_ids if config_id is not None})
    if not normalized_ids:
        return
    broadcast_overlay_event(
        "config_updated",
        {
            "config_ids": normalized_ids,
            "reason": reason,
        },
    )
