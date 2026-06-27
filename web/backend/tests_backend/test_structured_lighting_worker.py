import numpy as np

from web.backend import structured_lighting_worker as worker


def test_hdmi_step_capture_waits_for_renderer_presented_pattern(monkeypatch):
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    sleeps = []

    monkeypatch.setattr(worker, "flush_and_read", lambda cap, flush_count: frame)
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: sleeps.append(seconds))

    captured, gray = worker.capture_step(
        cap=object(),
        projector_window=None,
        pattern_image_path=None,
        presentation_mode="hdmi_step",
        settle_seconds=0.25,
        flush_count=0,
        pump_ms=1,
        previous_gray=None,
    )

    assert captured is frame
    assert gray.shape == (4, 4)
    assert sleeps == [0.25]
