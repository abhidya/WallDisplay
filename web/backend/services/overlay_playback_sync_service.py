import hashlib
import threading
import time
from typing import Any, Dict, List, Optional


DEFAULT_IMAGE_INTERVAL_MS = 10_000
DEFAULT_ANIMATION_INTERVAL_MS = 12_000
DEFAULT_VIDEO_INTERVAL_MS = 15_000
MIN_ITEM_DURATION_MS = 3_000


def _stable_seed(value: str) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return int(digest, 16)


def _mulberry32(seed: int):
    state = seed & 0xFFFFFFFF

    def _next() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        value = state
        value = (value ^ (value >> 15)) * (value | 1)
        value &= 0xFFFFFFFF
        value ^= value + (((value ^ (value >> 7)) * (value | 61)) & 0xFFFFFFFF)
        value &= 0xFFFFFFFF
        return ((value ^ (value >> 14)) & 0xFFFFFFFF) / 4294967296

    return _next


def _deterministic_shuffle_indices(length: int, seed: int) -> List[int]:
    indices = list(range(max(0, int(length))))
    if len(indices) <= 1:
        return indices
    rand = _mulberry32(seed)
    for idx in range(len(indices) - 1, 0, -1):
        swap_idx = int(rand() * (idx + 1))
        indices[idx], indices[swap_idx] = indices[swap_idx], indices[idx]
    return indices


class OverlayPlaybackSyncService:
    def __init__(self):
        self._lock = threading.RLock()
        self._states: Dict[str, Dict[str, Any]] = {}

    def get_scene_snapshot(self, scene_id: int, groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        sources: Dict[str, Dict[str, Any]] = {}

        with self._lock:
            for group in groups or []:
                descriptor = self._build_descriptor(group)
                if not descriptor:
                    continue
                state = self._get_or_create_state(descriptor, now_ms)
                sources[descriptor["source_key"]] = self._build_snapshot(descriptor, state, now_ms)

        return {
            "scene_id": scene_id,
            "server_now_ms": now_ms,
            "sources": sources,
        }

    def _build_descriptor(self, group: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        source_key = group.get("playback_sync_key")
        if not source_key:
            return None

        binding_type = str(group.get("media_binding_type") or "").lower()
        media_items = list(group.get("media_items") or [])
        animation_list = group.get("animation_list_payload") or {}
        shuffle_enabled = bool(
            animation_list.get("shuffle")
            if binding_type == "animation_list"
            else group.get("shuffle")
        )

        if binding_type == "animation_list":
            animation_ids = [
                animation_id
                for animation_id in (animation_list.get("animation_ids") or [])
                if isinstance(animation_id, str) and animation_id
            ]
            if not animation_ids:
                return None
            interval_ms = max(
                MIN_ITEM_DURATION_MS,
                int(animation_list.get("auto_advance_seconds") or 12) * 1000,
            )
            signature = hashlib.sha1(
                "|".join(animation_ids).encode("utf-8")
            ).hexdigest()
            return {
                "source_key": source_key,
                "binding_type": binding_type,
                "shuffle_enabled": shuffle_enabled,
                "list_length": len(animation_ids),
                "schedule_mode": "fixed_interval",
                "advance_interval_ms": interval_ms,
                "item_durations_ms": [interval_ms] * len(animation_ids),
                "signature": f"{signature}:{interval_ms}:{int(shuffle_enabled)}",
            }

        if not media_items:
            return None

        durations_ms = [
            max(MIN_ITEM_DURATION_MS, int(item.get("duration_ms") or DEFAULT_VIDEO_INTERVAL_MS))
            if item.get("kind") == "video"
            else max(MIN_ITEM_DURATION_MS, int(item.get("duration_ms") or DEFAULT_IMAGE_INTERVAL_MS))
            for item in media_items
        ]
        has_video = any(item.get("kind") == "video" for item in media_items)
        signature_bits = [
            f"{item.get('url','')}:{item.get('kind','unknown')}:{durations_ms[idx]}"
            for idx, item in enumerate(media_items)
        ]
        return {
            "source_key": source_key,
            "binding_type": binding_type,
            "shuffle_enabled": shuffle_enabled,
            "list_length": len(media_items),
            "schedule_mode": "duration_list" if has_video else "fixed_interval",
            "advance_interval_ms": max(MIN_ITEM_DURATION_MS, durations_ms[0] if durations_ms else DEFAULT_IMAGE_INTERVAL_MS),
            "item_durations_ms": durations_ms,
            "signature": hashlib.sha1("|".join(signature_bits).encode("utf-8")).hexdigest() + f":{int(shuffle_enabled)}",
        }

    def _get_or_create_state(self, descriptor: Dict[str, Any], now_ms: int) -> Dict[str, Any]:
        source_key = descriptor["source_key"]
        existing = self._states.get(source_key)
        if existing and existing.get("signature") == descriptor["signature"]:
            return existing

        state = {
            "shared_seed": _stable_seed(source_key),
            "started_at_ms": now_ms,
            "signature": descriptor["signature"],
            "generation": (existing or {}).get("generation", 0) + 1,
        }
        self._states[source_key] = state
        return state

    def _build_snapshot(self, descriptor: Dict[str, Any], state: Dict[str, Any], now_ms: int) -> Dict[str, Any]:
        list_length = max(1, int(descriptor["list_length"]))
        shuffled_order = (
            _deterministic_shuffle_indices(list_length, state["shared_seed"])
            if descriptor["shuffle_enabled"]
            else list(range(list_length))
        )

        global_counter = 0
        current_index = 0
        item_started_at_ms = state["started_at_ms"]
        next_transition_at_ms = now_ms + descriptor["advance_interval_ms"]

        if descriptor["schedule_mode"] == "fixed_interval":
            interval_ms = max(MIN_ITEM_DURATION_MS, int(descriptor["advance_interval_ms"]))
            elapsed_ms = max(0, now_ms - state["started_at_ms"])
            global_counter = elapsed_ms // interval_ms
            current_index = int(global_counter % list_length)
            item_started_at_ms = state["started_at_ms"] + (global_counter * interval_ms)
            next_transition_at_ms = item_started_at_ms + interval_ms
        else:
            ordered_durations = [descriptor["item_durations_ms"][idx] for idx in shuffled_order]
            cycle_ms = max(1, sum(ordered_durations))
            elapsed_ms = max(0, now_ms - state["started_at_ms"])
            completed_cycles = elapsed_ms // cycle_ms
            cycle_offset_ms = elapsed_ms % cycle_ms
            running_ms = 0
            current_index = 0
            for idx, duration_ms in enumerate(ordered_durations):
                next_running_ms = running_ms + duration_ms
                if cycle_offset_ms < next_running_ms:
                    current_index = idx
                    item_started_at_ms = now_ms - (cycle_offset_ms - running_ms)
                    next_transition_at_ms = item_started_at_ms + duration_ms
                    break
                running_ms = next_running_ms
            global_counter = (completed_cycles * list_length) + current_index

        next_index = (current_index + 1) % list_length
        return {
            "source_key": descriptor["source_key"],
            "shared_seed": state["shared_seed"],
            "started_at_ms": state["started_at_ms"],
            "server_now_ms": now_ms,
            "global_counter": int(global_counter),
            "current_index": int(current_index),
            "next_index": int(next_index),
            "item_started_at_ms": int(item_started_at_ms),
            "next_transition_at_ms": int(next_transition_at_ms),
            "schedule_mode": descriptor["schedule_mode"],
            "advance_interval_ms": int(descriptor["advance_interval_ms"]),
            "item_durations_ms": list(descriptor["item_durations_ms"]),
            "shuffle_enabled": bool(descriptor["shuffle_enabled"]),
            "list_length": list_length,
            "generation": int(state["generation"]),
        }


_overlay_playback_sync_service: Optional[OverlayPlaybackSyncService] = None


def get_overlay_playback_sync_service() -> OverlayPlaybackSyncService:
    global _overlay_playback_sync_service
    if _overlay_playback_sync_service is None:
        _overlay_playback_sync_service = OverlayPlaybackSyncService()
    return _overlay_playback_sync_service
