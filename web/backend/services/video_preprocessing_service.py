import logging
import threading
import time
from typing import Optional

from database.database import SessionLocal
from models.video import VideoModel
from core.twisted_streaming import get_instance as get_twisted_streaming
from services.video_service import VideoService

logger = logging.getLogger(__name__)


class VideoPreprocessingService:
    def __init__(self, poll_interval_seconds: float = 5.0):
        self.poll_interval_seconds = poll_interval_seconds
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._claim_lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="video-preprocessing",
            daemon=True,
        )
        self._thread.start()
        logger.info("Video preprocessing worker started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            processed = False
            try:
                video_id = self._claim_next_video_id()
                if video_id is not None:
                    processed = True
                    self._process_video(video_id)
            except Exception as exc:
                logger.error("Video preprocessing worker loop error: %s", exc, exc_info=True)

            if not processed:
                self._stop_event.wait(self.poll_interval_seconds)

    def _claim_next_video_id(self) -> Optional[int]:
        with self._claim_lock:
            db = SessionLocal()
            try:
                video = (
                    db.query(VideoModel)
                    .filter(VideoModel.preprocessing_status == "pending")
                    .order_by(VideoModel.created_at.asc(), VideoModel.id.asc())
                    .first()
                )
                if not video:
                    return None

                video.preprocessing_status = "processing"
                video.preprocessing_error = None
                db.commit()
                return video.id
            finally:
                db.close()

    def _process_video(self, video_id: int) -> None:
        db = SessionLocal()
        try:
            service = VideoService(db, get_twisted_streaming())
            result = service.process_video_for_overlay(video_id)
            if result is None:
                logger.warning("Queued video %s disappeared before preprocessing", video_id)
                return
            logger.info(
                "Video %s preprocessing completed with status=%s optimized=%s",
                video_id,
                result.preprocessing_status,
                result.overlay_optimized,
            )
        finally:
            db.close()


_service_instance: Optional[VideoPreprocessingService] = None
_service_lock = threading.Lock()


def get_video_preprocessing_service() -> VideoPreprocessingService:
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = VideoPreprocessingService()
    return _service_instance
