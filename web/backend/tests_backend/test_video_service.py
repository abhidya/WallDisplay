from types import SimpleNamespace

from web.backend.services.video_service import VideoService


class _FakeStreamingService:
    def __init__(self):
        self.calls = []

    def get_serve_ip(self):
        return "10.0.0.63"

    def start_server(self, files, serve_ip, port=None, device_name=None):
        self.calls.append(
            {
                "files": dict(files),
                "serve_ip": serve_ip,
                "port": port,
                "device_name": device_name,
            }
        )
        return {"file_video": f"http://{serve_ip}:{port}/file_video"}, object()


def test_stream_video_uses_twisted_start_server_port_kw(monkeypatch, tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"fake mp4")

    streaming_service = _FakeStreamingService()
    service = VideoService(db=None, streaming_service=streaming_service)
    monkeypatch.setattr(
        service,
        "get_video_by_id",
        lambda _video_id: SimpleNamespace(
            id=123,
            path=str(video_path),
            name="Sample Video",
            has_subtitle=False,
            subtitle_path=None,
        ),
    )

    result = service.stream_video(123)

    assert result == "http://10.0.0.63:8001/file_video"
    assert streaming_service.calls == [
        {
            "files": {"file_video": str(video_path)},
            "serve_ip": "10.0.0.63",
            "port": 8001,
            "device_name": "Sample Video",
        }
    ]


def test_stream_video_ignores_missing_subtitle_file(monkeypatch, tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"fake mp4")
    missing_subtitle = tmp_path / "missing.srt"

    streaming_service = _FakeStreamingService()
    service = VideoService(db=None, streaming_service=streaming_service)
    monkeypatch.setattr(
        service,
        "get_video_by_id",
        lambda _video_id: SimpleNamespace(
            id=456,
            path=str(video_path),
            name="Sample Video",
            has_subtitle=True,
            subtitle_path=str(missing_subtitle),
        ),
    )

    result = service.stream_video(456)

    assert result == "http://10.0.0.63:8001/file_video"
    assert streaming_service.calls[0]["files"] == {"file_video": str(video_path)}
