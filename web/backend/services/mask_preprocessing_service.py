import logging
import os
import tempfile
import threading
from typing import Optional, Tuple

from PIL import Image

from database.database import SessionLocal
from models.mapping_scene import MappingScene
from services.optimization_limiter import OPTIMIZATION_SEMAPHORE

logger = logging.getLogger(__name__)


class MaskPreprocessingService:
    def __init__(self, poll_interval_seconds: float = 5.0):
        self.poll_interval_seconds = poll_interval_seconds
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._claim_lock = threading.Lock()
        self._backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="mask-preprocessing",
            daemon=True,
        )
        self._thread.start()
        logger.info("Mask preprocessing worker started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            processed = False
            try:
                claim = self._claim_next_mask()
                if claim is not None:
                    processed = True
                    self._process_mask(*claim)
            except Exception as exc:
                logger.error("Mask preprocessing worker loop error: %s", exc, exc_info=True)

            if not processed:
                self._stop_event.wait(self.poll_interval_seconds)

    def _claim_next_mask(self) -> Optional[Tuple[int, str]]:
        with self._claim_lock:
            db = SessionLocal()
            try:
                scenes = db.query(MappingScene).order_by(MappingScene.updated_at.asc(), MappingScene.id.asc()).all()
                for scene in scenes:
                    masks = list(scene.masks or [])
                    for index, mask in enumerate(masks):
                        status = (mask or {}).get("preprocessing_status") or "pending"
                        stored_path = (mask or {}).get("stored_path")
                        if status == "completed" or not stored_path:
                            continue

                        masks[index] = {
                            **mask,
                            "preprocessing_status": "processing",
                            "preprocessing_error": None,
                        }
                        scene.masks = masks
                        db.commit()
                        return scene.id, str(mask.get("id"))
                return None
            finally:
                db.close()

    def _process_mask(self, scene_id: int, mask_id: str) -> None:
        db = SessionLocal()
        try:
            try:
                with OPTIMIZATION_SEMAPHORE:
                    self._run_mask_optimization(db, scene_id, mask_id)
            except Exception as exc:
                logger.error("Mask %s/%s preprocessing failed: %s", scene_id, mask_id, exc, exc_info=True)
                self._mark_mask_failed(db, scene_id, mask_id, str(exc))
        finally:
            db.close()

    def _run_mask_optimization(self, db, scene_id: int, mask_id: str) -> None:
        scene = db.query(MappingScene).filter(MappingScene.id == scene_id).first()
        if not scene:
            logger.warning("Queued mask %s/%s disappeared before preprocessing", scene_id, mask_id)
            return

        masks = list(scene.masks or [])
        mask_index = next((i for i, item in enumerate(masks) if str((item or {}).get("id")) == mask_id), None)
        if mask_index is None:
            logger.warning("Queued mask %s/%s no longer exists", scene_id, mask_id)
            return

        mask = dict(masks[mask_index] or {})
        stored_path = mask.get("stored_path")
        if not stored_path:
            return
        absolute_path = os.path.join(self._backend_root, stored_path)
        if not os.path.exists(absolute_path):
            raise FileNotFoundError(f"Mask file missing: {absolute_path}")

        original_size = os.path.getsize(absolute_path)
        optimized_size = self._optimize_mask_file(absolute_path)
        with Image.open(absolute_path) as image:
            mask["width"] = image.width
            mask["height"] = image.height
        mask["preprocessing_status"] = "completed"
        mask["preprocessing_error"] = None
        mask["original_file_size"] = original_size
        mask["optimized_file_size"] = optimized_size
        masks[mask_index] = mask
        scene.masks = masks
        db.commit()
        logger.info(
            "Mask %s/%s preprocessing completed size=%s->%s",
            scene_id,
            mask_id,
            original_size,
            optimized_size,
        )

    def _mark_mask_failed(self, db, scene_id: int, mask_id: str, error: str) -> None:
        scene = db.query(MappingScene).filter(MappingScene.id == scene_id).first()
        if not scene:
            return
        masks = list(scene.masks or [])
        for index, mask in enumerate(masks):
            if str((mask or {}).get("id")) != mask_id:
                continue
            masks[index] = {
                **mask,
                "preprocessing_status": "failed",
                "preprocessing_error": error[:500],
            }
            break
        scene.masks = masks
        db.commit()

    def _optimize_mask_file(self, absolute_path: str) -> int:
        with Image.open(absolute_path) as image:
            grayscale = image.convert("L")
            binary = grayscale.point(lambda pixel: 255 if pixel >= 128 else 0, mode="1")
            with tempfile.NamedTemporaryFile(
                suffix=".png",
                delete=False,
                dir=os.path.dirname(absolute_path),
            ) as temp_file:
                temp_path = temp_file.name
            try:
                binary.save(temp_path, format="PNG", optimize=True, compress_level=9)
                os.replace(temp_path, absolute_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        return os.path.getsize(absolute_path)


_service_instance: Optional[MaskPreprocessingService] = None
_service_lock = threading.Lock()


def get_mask_preprocessing_service() -> MaskPreprocessingService:
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = MaskPreprocessingService()
    return _service_instance
