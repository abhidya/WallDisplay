import threading
import time
from types import SimpleNamespace

from web.backend.services.mask_preprocessing_service import MaskPreprocessingService
from web.backend.services.video_preprocessing_service import VideoPreprocessingService


class _ConcurrencyTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def enter(self):
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)

    def exit(self):
        with self._lock:
            self.active -= 1


def test_video_and_mask_preprocessing_share_single_optimization_slot(monkeypatch):
    tracker = _ConcurrencyTracker()
    video_service = VideoPreprocessingService(poll_interval_seconds=0.01)
    mask_service = MaskPreprocessingService(poll_interval_seconds=0.01)

    class _FakeDB:
        def close(self):
            return None

    monkeypatch.setattr("web.backend.services.video_preprocessing_service.SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr("web.backend.services.mask_preprocessing_service.SessionLocal", lambda: _FakeDB())

    def fake_video_optimization(_db, _video_id):
        tracker.enter()
        try:
            time.sleep(0.15)
            return SimpleNamespace(preprocessing_status="ready", overlay_optimized=True)
        finally:
            tracker.exit()

    def fake_mask_optimization(_db, _scene_id, _mask_id):
        tracker.enter()
        try:
            time.sleep(0.15)
        finally:
            tracker.exit()

    monkeypatch.setattr(video_service, "_run_video_optimization", fake_video_optimization)
    monkeypatch.setattr(mask_service, "_run_mask_optimization", fake_mask_optimization)

    video_thread = threading.Thread(target=video_service._process_video, args=(101,), daemon=True)
    mask_thread = threading.Thread(target=mask_service._process_mask, args=(7, "mask-1"), daemon=True)

    video_thread.start()
    mask_thread.start()
    video_thread.join(timeout=1)
    mask_thread.join(timeout=1)

    assert tracker.max_active == 1
