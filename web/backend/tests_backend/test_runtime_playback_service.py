from types import SimpleNamespace

from web.backend.services.runtime_playback_service import RuntimePlaybackService


def test_runtime_playback_service_uses_runtime_device_service_path():
    calls = []
    runtime = SimpleNamespace(
        play_runtime_device_video=lambda device_name, video_path, loop=False: calls.append(
            ("play_runtime_device_video", device_name, video_path, loop)
        )
        or True,
        update_device_status=lambda **kwargs: calls.append(("update_device_status", kwargs)),
    )
    device = SimpleNamespace(name="Device A", is_playing=False)

    service = RuntimePlaybackService(runtime)

    assert service.auto_play_video(device, "/tmp/a.mp4", loop=True) is True
    assert calls == [("play_runtime_device_video", "Device A", "/tmp/a.mp4", True)]


def test_runtime_playback_service_falls_back_to_direct_streaming(monkeypatch, tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.write_text("x")

    calls = []
    device = SimpleNamespace(
        name="Device A",
        is_playing=False,
        update_streaming_info=lambda url, port: calls.append(("streaming_info", url, port)),
        play=lambda url, loop: calls.append(("play", url, loop)) or True,
    )

    registry = SimpleNamespace(
        register_session=lambda **kwargs: SimpleNamespace(session_id="session-1")
    )
    streaming_server = SimpleNamespace(
        start_server=lambda **kwargs: (
            {"video.mp4": "http://192.168.1.50:9001/video.mp4"},
            SimpleNamespace(),
        )
    )

    runtime = SimpleNamespace(
        play_runtime_device_video=lambda device_name, video_path, loop=False: None,
        get_serve_ip=lambda: "192.168.1.50",
        update_device_status=lambda **kwargs: calls.append(("status", kwargs)),
        trigger_overlay_sync=lambda video_name: calls.append(("overlay_sync", video_name)),
        start_playback_health_check=lambda device_name, path: calls.append(
            ("health_check", device_name, path)
        ),
    )

    monkeypatch.setattr(
        "core.twisted_streaming.TwistedStreamingServer.get_instance",
        lambda: streaming_server,
    )
    monkeypatch.setattr(
        "core.streaming_registry.StreamingSessionRegistry.get_instance",
        lambda: registry,
    )

    service = RuntimePlaybackService(runtime)

    assert service.auto_play_video(device, str(video_path), loop=True, config={"enable_overlay_sync": True}) is True
    assert calls == [
        ("streaming_info", "http://192.168.1.50:9001/video.mp4", 9001),
        ("play", "http://192.168.1.50:9001/video.mp4", True),
        (
            "status",
            {
                "device_name": "Device A",
                "status": "connected",
                "is_playing": True,
                "current_video": str(video_path),
            },
        ),
        ("health_check", "Device A", str(video_path)),
        ("overlay_sync", "video.mp4"),
    ]


def test_runtime_playback_service_plays_remote_url_directly():
    calls = []
    runtime = SimpleNamespace(
        play_runtime_device_video=lambda *args, **kwargs: None,
        update_device_status=lambda **kwargs: calls.append(("update_status", kwargs)),
        start_playback_health_check=lambda device_name, video_path: calls.append(
            ("start_health_check", device_name, video_path)
        ),
        trigger_overlay_sync=lambda video_name: calls.append(("trigger_overlay_sync", video_name)),
    )
    device = SimpleNamespace(
        name="Device Remote",
        is_playing=False,
        play=lambda video_url, loop=True: calls.append(("play", video_url, loop)) or True,
        current_video_path=None,
    )

    service = RuntimePlaybackService(runtime)

    assert service.auto_play_video(
        device,
        "http://localhost:8000/overlay",
        loop=True,
        config={"enable_overlay_sync": True, "sync_video_name": "overlay"},
    ) is True
    assert device.current_video_path == "http://localhost:8000/overlay"
    assert calls == [
        ("play", "http://localhost:8000/overlay", True),
        (
            "update_status",
            {
                "device_name": "Device Remote",
                "status": "connected",
                "is_playing": True,
                "current_video": "http://localhost:8000/overlay",
            },
        ),
        ("start_health_check", "Device Remote", "http://localhost:8000/overlay"),
        ("trigger_overlay_sync", "overlay"),
    ]
