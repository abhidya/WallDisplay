from datetime import datetime
from typing import Any, Dict, Optional


class PlaybackIntentService:
    """
    Own assignment, scheduling, and retry bookkeeping for renderer playback intent.

    This service is intentionally stateful but transport-agnostic. DeviceManager still
    controls execution and locking during the first extraction phase.
    """

    def __init__(self):
        self._assigned_videos: Dict[str, str] = {}
        self._video_assignment_priority: Dict[str, int] = {}
        self._video_assignment_retries: Dict[str, int] = {}
        self._scheduled_assignments: Dict[str, Dict[str, Any]] = {}
        self._device_assignment_queue: Dict[str, Dict[str, Any]] = {}

    @property
    def assigned_videos(self) -> Dict[str, str]:
        return self._assigned_videos

    @property
    def video_assignment_priority(self) -> Dict[str, int]:
        return self._video_assignment_priority

    @property
    def video_assignment_retries(self) -> Dict[str, int]:
        return self._video_assignment_retries

    @property
    def scheduled_assignments(self) -> Dict[str, Dict[str, Any]]:
        return self._scheduled_assignments

    @property
    def device_assignment_queue(self) -> Dict[str, Dict[str, Any]]:
        return self._device_assignment_queue

    def get_assigned_video(self, device_name: str) -> Optional[str]:
        return self._assigned_videos.get(device_name)

    def set_assigned_video(self, device_name: str, video_path: str) -> None:
        self._assigned_videos[device_name] = video_path

    def clear_assigned_video(self, device_name: str) -> None:
        self._assigned_videos.pop(device_name, None)

    def get_priority(self, device_name: str, default: int = 0) -> int:
        return self._video_assignment_priority.get(device_name, default)

    def set_priority(self, device_name: str, priority: int) -> None:
        self._video_assignment_priority[device_name] = priority

    def clear_priority(self, device_name: str) -> None:
        self._video_assignment_priority.pop(device_name, None)

    def get_retry_count(self, device_name: str, default: int = 0) -> int:
        return self._video_assignment_retries.get(device_name, default)

    def reset_retries(self, device_name: str) -> None:
        self._video_assignment_retries[device_name] = 0

    def increment_retries(self, device_name: str) -> int:
        retry_count = self.get_retry_count(device_name, 0) + 1
        self._video_assignment_retries[device_name] = retry_count
        return retry_count

    def clear_retries(self, device_name: str) -> None:
        self._video_assignment_retries.pop(device_name, None)

    def schedule_assignment(
        self,
        device_name: str,
        video_path: str,
        priority: int,
        schedule_time: datetime,
    ) -> None:
        self._scheduled_assignments[device_name] = {
            "video_path": video_path,
            "priority": priority,
            "scheduled_time": schedule_time,
        }

    def get_due_scheduled_video(self, device_name: str, now: datetime) -> Optional[str]:
        assignment = self._scheduled_assignments.get(device_name)
        if not assignment:
            return None

        scheduled_time = assignment.get("scheduled_time")
        if not scheduled_time or now < scheduled_time:
            return None

        video_path = assignment.get("video_path")
        self._scheduled_assignments.pop(device_name, None)
        return video_path

    def get_scheduled_assignments_copy(self) -> Dict[str, Dict[str, Any]]:
        return {key: value.copy() for key, value in self._scheduled_assignments.items()}

    def clear_scheduled_assignment(self, device_name: str) -> None:
        self._scheduled_assignments.pop(device_name, None)

    def clear_assignment_queue(self, device_name: str) -> None:
        self._device_assignment_queue.pop(device_name, None)

    def clear_device(self, device_name: str) -> None:
        self.clear_assigned_video(device_name)
        self.clear_priority(device_name)
        self.clear_retries(device_name)
        self.clear_scheduled_assignment(device_name)
        self.clear_assignment_queue(device_name)
