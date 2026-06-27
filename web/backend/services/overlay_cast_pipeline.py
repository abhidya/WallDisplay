class OverlayCastPipelineModule:
    """Deep interface for overlay cast pipeline operations."""

    def __init__(self, service):
        self.service = service

    async def export_mp4(self, **payload):
        return await self.service.export_mp4(**payload)

    async def start_cast(self, **payload):
        return await self.service.start_cast(**payload)

    async def stop_cast(self, session_id: str) -> bool:
        return await self.service.stop_cast(session_id)

    async def stop_all(self):
        return await self.service.stop_all()

    def list_sessions(self) -> list[dict]:
        return self.service.list_sessions()

    def get_session_for_device(self, device_id: str):
        return self.service.get_session_for_device(device_id)
