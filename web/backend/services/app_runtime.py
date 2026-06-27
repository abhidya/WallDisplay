import logging
import os
import socket
import asyncio
import time
import threading
import requests
from dataclasses import dataclass
from typing import Optional

from web.backend.core.config_service import ConfigService
from web.backend.core.device_manager import DeviceManager, get_device_manager
from web.backend.core.streaming_registry import StreamingSessionRegistry
from web.backend.discovery.discovery_manager import DiscoveryManager
from web.backend.services.device_inventory_service import DeviceInventoryService
from web.backend.services.device_runtime import DeviceRuntimeModule
from web.backend.services.device_lifecycle_service import DeviceLifecycleService
from web.backend.services.playback_intent_service import PlaybackIntentService
from web.backend.services.runtime_playback_service import RuntimePlaybackService
from web.backend.services.runtime_registry_service import RuntimeRegistryService
from web.backend.services.unified_discovery_lifecycle_service import UnifiedDiscoveryLifecycleService

logger = logging.getLogger(__name__)


def _device_runtime(runtime) -> DeviceRuntimeModule:
    device_runtime = getattr(runtime, "device_runtime", None)
    if device_runtime is None:
        device_runtime = DeviceRuntimeModule(runtime)
        try:
            runtime.device_runtime = device_runtime
        except Exception:
            pass
    return device_runtime


def _start_discovery_migration(runtime: "AppRuntime"):
    from web.backend.discovery.migration import start_discovery_migration

    return start_discovery_migration(runtime)


def _rebind_streaming_health_handler(runtime: "AppRuntime") -> None:
    registry = getattr(runtime, "streaming_registry", None)
    legacy_handler = getattr(runtime, "legacy_streaming_issue_handler", None)
    if registry is None:
        return

    unregister = getattr(registry, "unregister_health_check_handler", None)
    if unregister is not None and legacy_handler is not None:
        try:
            unregister(legacy_handler)
        except Exception:
            logger.debug("Could not unregister legacy DeviceManager health handler", exc_info=True)

    register = getattr(registry, "register_health_check_handler", None)
    if register is not None:
        register(runtime.handle_streaming_issue)


@dataclass
class AppRuntime:
    config_service: ConfigService
    streaming_registry: StreamingSessionRegistry
    discovery_manager: DiscoveryManager
    unified_discovery_lifecycle_service: UnifiedDiscoveryLifecycleService
    device_inventory_service: DeviceInventoryService
    runtime_registry_service: RuntimeRegistryService
    playback_intent_service: PlaybackIntentService
    device_manager: Optional[DeviceManager]
    device_lifecycle_service: Optional[object] = None
    runtime_playback_service: Optional[object] = None
    playback_monitoring_service: Optional[object] = None
    playback_orchestrator: Optional[object] = None
    device_state_lock_ref: Optional[object] = None
    connectivity_timeout_seconds: Optional[int] = None
    device_lock_timeout_seconds: Optional[float] = None
    discovery_coordinator: Optional[object] = None
    migration_adapter: Optional[object] = None
    legacy_streaming_issue_handler: Optional[object] = None
    airplay_projection_automation_service: Optional[object] = None
    device_runtime: Optional[DeviceRuntimeModule] = None

    def __post_init__(self):
        if self.device_runtime is None:
            self.device_runtime = DeviceRuntimeModule(self)

    @property
    def discovery_authority(self) -> str:
        return _device_runtime(self).discovery_authority

    @property
    def uses_unified_discovery_authority(self) -> bool:
        return _device_runtime(self).uses_unified_discovery_authority

    @property
    def device_state_lock(self):
        if self.device_state_lock_ref is not None:
            return self.device_state_lock_ref
        self.device_state_lock_ref = threading.RLock()
        return self.device_state_lock_ref

    @property
    def device_status(self):
        return self.runtime_registry_service.device_status

    @property
    def connectivity_timeout(self) -> int:
        if self.connectivity_timeout_seconds is not None:
            return self.connectivity_timeout_seconds
        self.connectivity_timeout_seconds = 30
        return self.connectivity_timeout_seconds

    @property
    def device_lock_timeout(self) -> float:
        if self.device_lock_timeout_seconds is not None:
            return self.device_lock_timeout_seconds
        self.device_lock_timeout_seconds = 5.0
        return self.device_lock_timeout_seconds

    def _get_discovery_controller(self):
        return _device_runtime(self)._get_discovery_controller()

    def _get_active_discovery_controller(self):
        return _device_runtime(self)._get_active_discovery_controller()

    def start_background_services(self) -> None:
        logger.info("Starting device discovery")
        self.discovery_manager.register_enabled_backends()
        try:
            if self.airplay_projection_automation_service is None:
                from services.airplay_projection_automation_service import AirPlayProjectionAutomationService

                self.airplay_projection_automation_service = AirPlayProjectionAutomationService(
                    self.discovery_manager
                )
            self.airplay_projection_automation_service.start()
        except Exception as exc:
            logger.error(f"Failed to start AirPlay projection automation service: {exc}")
        if self.uses_unified_discovery_authority:
            self.unified_discovery_lifecycle_service.start()
            logger.info("Unified discovery authority enabled; skipping legacy discovery loop startup")
        else:
            discovery_controller = AppRuntime._get_discovery_controller(self)
            discovery_controller.start()

        if self.migration_adapter is None:
            try:
                self.migration_adapter = _start_discovery_migration(self)
                logger.info("Started discovery system migration adapter")
            except Exception as exc:
                logger.error(f"Failed to start discovery migration: {exc}")

    def stop_background_services(self) -> None:
        if self.airplay_projection_automation_service is not None:
            try:
                self.airplay_projection_automation_service.stop()
            except Exception as exc:
                logger.error(f"Error stopping AirPlay projection automation service: {exc}")
        if not self.uses_unified_discovery_authority:
            discovery_controller = AppRuntime._get_discovery_controller(self)
            discovery_controller.stop()

        if self.migration_adapter is not None:
            try:
                self.migration_adapter.stop_migration()
                logger.info("Discovery migration adapter stopped")
            except Exception as exc:
                logger.error(f"Error stopping migration adapter: {exc}")
            finally:
                self.migration_adapter = None

        self.unified_discovery_lifecycle_service.stop()

    def start_discovery(self) -> None:
        _device_runtime(self).start_discovery()

    def stop_discovery(self) -> None:
        _device_runtime(self).stop_discovery()

    def pause_discovery(self) -> None:
        _device_runtime(self).pause_discovery()

    def resume_discovery(self) -> None:
        _device_runtime(self).resume_discovery()

    def set_discovery_interval(self, seconds: int) -> int:
        return _device_runtime(self).set_discovery_interval(seconds)

    def get_discovery_status(self) -> dict:
        return _device_runtime(self).get_discovery_status()

    def build_device_service(self, db):
        from services.device_service import DeviceService

        return DeviceService(db, runtime=self)

    def get_db_device_by_name(self, device_name: str):
        from database.database import get_db

        db_generator = get_db()
        db = next(db_generator)
        try:
            device_service = self.build_device_service(db)
            return device_service.get_device_by_name(device_name)
        finally:
            try:
                db_generator.close()
            except Exception:
                pass

    def recover_runtime_device(self, device_name: str):
        from database.database import get_db

        db_generator = get_db()
        db = next(db_generator)
        try:
            device_service = self.build_device_service(db)
            db_device = device_service.get_device_by_name(device_name)
            if not db_device:
                return None

            device_info = {
                "device_name": db_device.name,
                "type": db_device.type,
                "hostname": db_device.hostname,
                "action_url": db_device.action_url,
                "friendly_name": db_device.friendly_name,
                "manufacturer": db_device.manufacturer,
                "location": db_device.location,
            }
            device = self.register_device(device_info)
            if (
                device
                and hasattr(db_device, "streaming_url")
                and getattr(db_device, "streaming_url", None)
                and getattr(db_device, "streaming_port", None)
            ):
                device.update_streaming_info(db_device.streaming_url, db_device.streaming_port)
            return device
        finally:
            try:
                db_generator.close()
            except Exception:
                pass

    def play_runtime_device_video(self, device_name: str, video_path: str, loop: bool = False) -> Optional[bool]:
        from database.database import get_db

        db_generator = get_db()
        db = next(db_generator)
        try:
            device_service = self.build_device_service(db)
            db_device = device_service.get_device_by_name(device_name)
            if not db_device:
                return None
            return device_service.play_video(db_device.id, video_path, loop)
        finally:
            try:
                db_generator.close()
            except Exception:
                pass

    def persist_runtime_playback_progress(
        self,
        device_name: str,
        position: str,
        duration: str,
        progress: int,
    ) -> bool:
        from database.database import get_db

        db_generator = get_db()
        db = next(db_generator)
        try:
            device_service = self.build_device_service(db)
            db_device = device_service.get_device_by_name(device_name)
            if not db_device:
                return False
            db_device.playback_position = position
            db_device.playback_duration = duration
            db_device.playback_progress = progress
            commit_db = getattr(device_service, "db", db)
            commit_db.commit()
            return True
        finally:
            try:
                db_generator.close()
            except Exception:
                pass

    def get_devices(self):
        return _device_runtime(self).get_devices()

    def get_device_items(self):
        return _device_runtime(self).get_device_items()

    def get_device_count(self) -> int:
        return _device_runtime(self).get_device_count()

    def get_playing_device_count(self) -> int:
        return _device_runtime(self).get_playing_device_count()

    def get_device(self, device_name: str):
        return _device_runtime(self).get_device(device_name)

    def register_device(self, device_info: dict):
        return _device_runtime(self).register_device(device_info)

    def unregister_device(self, device_name: str) -> bool:
        return _device_runtime(self).unregister_device(device_name)

    def update_device_status(
        self,
        *,
        device_name: str,
        status: str,
        is_playing=None,
        current_video=None,
        error=None,
    ) -> None:
        _device_runtime(self).update_device_status(
            device_name=device_name,
            status=status,
            is_playing=is_playing,
            current_video=current_video,
            error=error,
        )

    def auto_play_video(self, device, video_path: str, loop: bool = True, config=None) -> bool:
        playback_service = getattr(self, "runtime_playback_service", None)
        if playback_service is None:
            playback_service = RuntimePlaybackService(self)
            self.runtime_playback_service = playback_service
        return playback_service.auto_play_video(
            device,
            video_path,
            loop=loop,
            config=config,
        )

    def start_playback_health_check(self, device_name: str, video_path: str) -> None:
        _device_runtime(self).start_playback_health_check(device_name, video_path)

    def stop_playback_health_check(self, device_name: str) -> None:
        _device_runtime(self).stop_playback_health_check(device_name)

    def track_playback_result(self, device_name: str, video_path: str, success: bool) -> None:
        _device_runtime(self).track_playback_result(device_name, video_path, success)

    def get_device_playback_stats(self, device_name: str) -> dict:
        return _device_runtime(self).get_device_playback_stats(device_name)

    def handle_streaming_issue(self, session) -> None:
        device_name = getattr(session, "device_name", None)
        if not device_name:
            logger.warning("Streaming issue received without device_name: %s", getattr(session, "session_id", None))
            return

        try:
            if getattr(session, "stream_type", None) in {"projection_stream", "overlay_mapping_stream"} or device_name in {
                "overlay",
                "overlay-mapping",
            }:
                logger.info(
                    "Streaming issue for internal overlay session %s, skipping device-specific handling",
                    getattr(session, "session_id", None),
                )
                return

            device = self.get_device(device_name)
            if not device:
                logger.warning(
                    "Device %s not found for streaming issue handling - attempting recovery",
                    device_name,
                )
                logger.debug("Current devices in runtime: %s", [name for name, _device in self.get_device_items()])
                with self.device_state_lock:
                    last_seen_time = self.runtime_registry_service.last_seen.get(device_name, 0)
                    time_since_seen = time.time() - last_seen_time if last_seen_time else float("inf")
                    logger.debug("Device %s last seen %.1fs ago", device_name, time_since_seen)

                logger.info("Attempting to recover device %s from database", device_name)
                device = self.recover_runtime_device(device_name)
                if not device:
                    logger.warning("Device %s not found in database - may have been removed", device_name)
                    return
                logger.info("Successfully recovered device %s from database", device_name)

            if session.status == "stalled" and session.is_stalled(inactivity_threshold=30.0):
                playback_orchestrator = getattr(self, "playback_orchestrator", None)
                if playback_orchestrator is not None:
                    playback_orchestrator.handle_stalled_streaming_session(session, device)
        except Exception as exc:
            logger.error("Error handling streaming issue for %s: %s", device_name, exc)
            self.update_device_status(device_name=device_name, status="error", error=str(exc))

    def process_airplay_casting(self, device_name: str, config: dict) -> None:
        try:
            airplay_url = config.get("airplay_url")
            if not airplay_url:
                logger.error(
                    "Device %s configured for airplay but no airplay_url provided",
                    device_name,
                )
                return

            device = self.get_device(device_name)
            if not device:
                logger.error("Device %s not found", device_name)
                return

            logger.info("Starting overlay display on %s via DLNA: %s", device_name, airplay_url)

            success = self.auto_play_video(device, airplay_url, loop=True)
            if success:
                logger.info("Successfully started overlay display on %s", device_name)
                self.update_device_status(
                    device_name=device_name,
                    status="connected",
                    is_playing=True,
                    current_video=airplay_url,
                )
                return

            logger.warning("Direct URL playback failed, trying fallback video")
            fallback_video = config.get("video_file")
            if fallback_video and os.path.exists(fallback_video):
                success = self.auto_play_video(device, fallback_video, loop=True)
                if success:
                    logger.info("Started fallback video on %s", device_name)
                    self.update_device_status(
                        device_name=device_name,
                        status="connected",
                        is_playing=True,
                        current_video=fallback_video,
                    )
                    return
                logger.error("Failed to play fallback video on %s", device_name)
                self.update_device_status(
                    device_name=device_name,
                    status="error",
                    error="Failed to start playback",
                )
                return

            logger.error("No fallback video available for %s", device_name)
            self.update_device_status(
                device_name=device_name,
                status="error",
                error="Failed to display overlay",
            )
        except Exception as exc:
            logger.error("Error processing airplay casting for %s: %s", device_name, exc)
            self.update_device_status(
                device_name=device_name,
                status="error",
                error=str(exc),
            )

    def cleanup_device_state(self, device_name: str) -> None:
        _device_runtime(self).cleanup_device_state(device_name)

    def get_assigned_video(self, device_name: str):
        return _device_runtime(self).get_assigned_video(device_name)

    def discover_dlna_devices(self, timeout: float):
        return _device_runtime(self).discover_dlna_devices(timeout)

    def _discover_dlna_devices_via_unified(self, timeout: float):
        async def _run():
            devices = await self.discovery_manager.discover_devices(
                backend_name="dlna",
                timeout=max(int(timeout), 1),
            )
            return [
                {
                    "device_name": device.friendly_name or device.name,
                    "name": device.name,
                    "type": "dlna",
                    "friendly_name": device.friendly_name or device.name,
                    "hostname": device.hostname,
                    "action_url": device.action_url,
                    "manufacturer": device.manufacturer,
                    "location": device.location,
                }
                for device in devices
            ]

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_run())

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()

    def save_devices_to_config(self, config_file: str) -> bool:
        return _device_runtime(self).save_devices_to_config(config_file)

    def get_serve_ip(self) -> str:
        env_ip = os.environ.get("STREAMING_SERVE_IP")
        if env_ip:
            logger.info("Using STREAMING_SERVE_IP from environment: %s", env_ip)
            if env_ip.startswith("127.") or env_ip == "localhost":
                raise RuntimeError("STREAMING_SERVE_IP must be a LAN IP, not localhost/127.0.0.1")
            return env_ip

        probe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe_socket.connect(("8.8.8.8", 80))
            ip_address = probe_socket.getsockname()[0]
            if ip_address.startswith("127."):
                raise RuntimeError("Auto-detected IP is localhost, not valid for DLNA streaming.")
            logger.info("Auto-detected LAN IP for streaming: %s", ip_address)
            return ip_address
        except Exception as exc:
            logger.error(f"Could not auto-detect LAN IP for streaming: {exc}")
            raise RuntimeError(
                "Could not determine LAN IP for streaming. Set STREAMING_SERVE_IP env variable."
            ) from exc
        finally:
            probe_socket.close()

    def trigger_overlay_sync(self, video_name: str) -> None:
        try:
            response = requests.post(
                "http://localhost:8000/api/overlay/sync",
                params={
                    "triggered_by": "dlna_auto_play",
                    "video_name": video_name,
                },
                timeout=2,
            )
            if response.status_code == 200:
                logger.info("Triggered overlay sync for video: %s", video_name)
            else:
                logger.warning("Failed to trigger overlay sync: %s", response.status_code)
        except Exception as exc:
            logger.error("Failed to sync overlays: %s", exc)

    def update_runtime_playback_progress(
        self,
        device_name: str,
        position: str,
        duration: str,
        progress: int,
    ) -> None:
        _device_runtime(self).update_runtime_playback_progress(device_name, position, duration, progress)

    def update_device_playback_progress(
        self,
        device_name: str,
        position: str,
        duration: str,
        progress: int,
    ) -> None:
        _device_runtime(self).update_device_playback_progress(device_name, position, duration, progress)

    def hydrate_database_devices(self, db_devices: list[dict]) -> None:
        for device_dict in db_devices:
            device_name = device_dict.get("name")
            if not device_name:
                continue

            device_info = {
                "device_name": device_name,
                "type": device_dict.get("type", "dlna"),
                "hostname": device_dict.get("hostname", ""),
                "action_url": device_dict.get("action_url", ""),
                "friendly_name": device_dict.get("friendly_name", device_name),
                "manufacturer": device_dict.get("manufacturer", ""),
                "location": device_dict.get("location", ""),
            }

            if device_dict.get("config"):
                device_info.update(device_dict["config"])

            registered_device = self.register_device(device_info)
            if registered_device:
                logger.info("Initialized device %s from database", device_name)
                self.update_device_status(
                    device_name=device_name,
                    status="disconnected",
                    is_playing=device_dict.get("is_playing", False),
                    current_video=device_dict.get("current_video"),
                )
            else:
                logger.warning("Failed to initialize device %s from database", device_name)


_app_runtime_instance: Optional[AppRuntime] = None


def get_app_runtime() -> AppRuntime:
    global _app_runtime_instance

    if _app_runtime_instance is None:
        config_service = ConfigService.get_instance()
        streaming_registry = StreamingSessionRegistry.get_instance()
        discovery_manager = DiscoveryManager.get_instance()
        device_inventory_service = DeviceInventoryService()
        runtime_registry_service = RuntimeRegistryService()
        playback_intent_service = PlaybackIntentService()

        device_manager = get_device_manager(
            config_service=config_service,
            streaming_registry=streaming_registry,
            device_inventory=device_inventory_service,
            runtime_registry=runtime_registry_service,
            playback_intent_service=playback_intent_service,
        )

        _app_runtime_instance = AppRuntime(
            config_service=config_service,
            streaming_registry=streaming_registry,
            discovery_manager=discovery_manager,
            unified_discovery_lifecycle_service=UnifiedDiscoveryLifecycleService(discovery_manager),
            device_inventory_service=device_inventory_service,
            runtime_registry_service=runtime_registry_service,
            playback_intent_service=playback_intent_service,
            device_manager=device_manager,
            device_lifecycle_service=device_manager.device_lifecycle_service,
            playback_monitoring_service=device_manager.playback_monitoring_service,
            playback_orchestrator=getattr(device_manager, "playback_orchestrator", None),
            device_state_lock_ref=device_manager.device_state_lock,
            connectivity_timeout_seconds=device_manager.connectivity_timeout,
            device_lock_timeout_seconds=device_manager.device_lock_timeout,
            discovery_coordinator=device_manager.discovery_coordinator,
            legacy_streaming_issue_handler=device_manager._handle_streaming_issue,
        )
        runtime_device_lifecycle_service = DeviceLifecycleService(
            owner=_app_runtime_instance,
            device_inventory=device_inventory_service,
            runtime_registry=runtime_registry_service,
            playback_intent_service=playback_intent_service,
            playback_monitoring_service=device_manager.playback_monitoring_service,
            device_state_lock=device_manager.device_state_lock,
            assignment_lock=device_manager.assignment_lock,
            acquire_device_lock=device_manager._acquire_device_lock,
            release_device_lock=device_manager._release_device_lock,
        )
        _app_runtime_instance.device_lifecycle_service = runtime_device_lifecycle_service
        device_manager.device_lifecycle_service = runtime_device_lifecycle_service
        _app_runtime_instance.runtime_playback_service = RuntimePlaybackService(_app_runtime_instance)
        _rebind_streaming_health_handler(_app_runtime_instance)

    return _app_runtime_instance


def get_device_runtime() -> DeviceRuntimeModule:
    return get_app_runtime().device_runtime
