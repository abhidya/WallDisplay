from typing import Dict, List, Optional


class StructuredLightingSessionModule:
    """Deep interface for the structured-lighting session workflow."""

    def __init__(self, service):
        self.service = service

    def get_status(self) -> Dict:
        return self.service.get_status()

    def list_sessions(self) -> List[Dict]:
        return self.service.list_sessions()

    def create_session(self, **payload) -> Dict:
        return self.service.create_session(**payload)

    def get_session(self, session_id: str) -> Optional[Dict]:
        return self.service.get_session(session_id)

    def start_session(self, session_id: str) -> Optional[Dict]:
        return self.service.start_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self.service.delete_session(session_id)

    def get_capture_plan(self, session_id: str) -> Optional[Dict]:
        return self.service.get_capture_plan(session_id)

    def get_runtime(self, session_id: str) -> Optional[Dict]:
        return self.service.get_runtime(session_id)

    def claim_next_step(self, worker_id: str) -> Optional[Dict]:
        return self.service.claim_next_step(worker_id)

    def record_capture(self, session_id: str, step_index: int, file_bytes: bytes, filename: str) -> Optional[Dict]:
        return self.service.record_capture(session_id, step_index, file_bytes, filename)

    def list_captures(self, session_id: str) -> Optional[Dict]:
        return self.service.list_captures(session_id)

    def render_capture_image(self, session_id: str, step_index: int) -> Optional[bytes]:
        return self.service.render_capture_image(session_id, step_index)

    def render_step_image(self, session_id: str, step_index: int) -> Optional[bytes]:
        return self.service.render_step_image(session_id, step_index)

    def decode_session(self, session_id: str, *, sample_step: int, tuning_params=None) -> Optional[Dict]:
        return self.service.decode_session(session_id, sample_step=sample_step, tuning_params=tuning_params)

    def run_tuning_search(self, session_id: str, **payload) -> Optional[Dict]:
        return self.service.run_tuning_search(session_id, **payload)

    def run_preview_tuning(self, session_id: str, **payload) -> Optional[Dict]:
        return self.service.run_preview_tuning(session_id, **payload)

    def get_tuning_search(self, session_id: str) -> Optional[Dict]:
        return self.service.get_tuning_search(session_id)

    def get_preview_tuning(self, session_id: str) -> Optional[Dict]:
        return self.service.get_preview_tuning(session_id)

    def get_calibration(self, session_id: str) -> Optional[Dict]:
        return self.service.get_calibration(session_id)

    def get_artifact_review(self, session_id: str) -> Optional[Dict]:
        return self.service.get_artifact_review(session_id)

    def render_artifact_preview(self, session_id: str, preview_id: str) -> Optional[bytes]:
        return self.service.render_artifact_preview(session_id, preview_id)

    def render_tuning_search_preview(self, session_id: str, candidate_id: str, preview_name: str) -> Optional[bytes]:
        return self.service.render_tuning_search_preview(session_id, candidate_id, preview_name)

    def render_preview_tuning_preview(self, session_id: str, candidate_id: str, preview_name: str) -> Optional[bytes]:
        return self.service.render_preview_tuning_preview(session_id, candidate_id, preview_name)

    def update_review(self, session_id: str, **payload) -> Optional[Dict]:
        return self.service.update_review(session_id, **payload)

    def export_session_bundle(self, session_id: str):
        return self.service.export_session_bundle(session_id)

    def publish_mapping_scene(self, session_id: str, scene_name: Optional[str] = None) -> Optional[Dict]:
        return self.service.publish_mapping_scene(session_id, scene_name=scene_name)
