export type JsonRecord = Record<string, unknown>;

export interface DeviceSummary extends JsonRecord {
  id?: number | string;
  name?: string;
  friendly_name?: string;
  device_name?: string;
  type?: string;
  hostname?: string;
  status?: string;
  availability?: string;
  derived_status?: string;
  playback_state?: string;
  is_playing?: boolean;
  current_video?: string;
  current_media_title?: string;
  playback_position?: string;
  playback_duration?: string;
  playback_progress?: number;
  manufacturer?: string;
  location?: string;
  streaming_url?: string;
  active_overlay_cast?: boolean;
  seconds_since_seen?: number;
}

export interface DeviceDetail extends DeviceSummary {
  action_url?: string;
  config?: JsonRecord | null;
  streaming_port?: number;
  updated_at?: string;
  playback_started_at?: string;
  overlay_cast_status?: string;
  overlay_cast_session_id?: string;
}

export interface DeviceControlMode extends JsonRecord {
  mode?: string;
  reason?: string;
  expires_at?: string | null;
}

export interface DeviceActionResponse extends JsonRecord {
  success?: boolean;
  message?: string;
}

export interface DiscoveryStatus extends JsonRecord {
  running?: boolean;
  paused?: boolean;
  interval_seconds?: number;
  authority?: string;
  unified_running?: boolean;
}

export interface DiscoveryBackendSummary extends JsonRecord {
  name?: string;
  active?: boolean;
  enabled?: boolean;
  healthy?: boolean;
  last_seen?: string;
}

export interface DiscoverySystemStatus extends JsonRecord {
  discovery_running?: boolean;
  total_devices?: number;
  online_devices?: number;
  active_sessions?: number;
  backends?: Record<string, DiscoveryBackendSummary>;
}

export interface DiscoveryCapabilities extends JsonRecord {
  casting_methods?: string[];
  device_capabilities?: string[];
  content_types?: string[];
}

export interface VideoSummary extends JsonRecord {
  id?: number | string;
  title?: string;
  name?: string;
  file_path?: string;
  path?: string;
  duration?: number | string;
  mime_type?: string;
}

export interface PhotoSummary extends JsonRecord {
  id?: number | string;
  name?: string;
  file_name?: string;
  path?: string;
  resolution?: string;
  format?: string;
  category?: string;
}

export interface MediaDirectorySummary extends JsonRecord {
  id?: number | string;
  name?: string;
  path?: string;
  category?: string;
  enabled?: boolean;
  scan_mode?: string;
}

export interface MediaListSummary extends JsonRecord {
  id?: number | string;
  name?: string;
  category?: string;
  playback_mode?: string;
}

export interface MediaChannelSummary extends JsonRecord {
  id?: number | string;
  name?: string;
  media_list_id?: number | string;
  current_video_id?: number | string | null;
  current_index?: number;
}

export interface HealthResponse extends JsonRecord {
  status?: string;
  message?: string;
}

export interface StreamingAnalytics extends JsonRecord {
  active_sessions?: number;
  session_count?: number;
  overlay_sessions?: number;
  total_bandwidth_mbps?: number;
}

export interface StreamingSessionSummary extends JsonRecord {
  session_id?: string;
  device_name?: string;
  consumer_id?: string;
  stream_type?: string;
  status?: string;
}

export interface RendererActionResponse extends JsonRecord {
  success?: boolean;
  message?: string;
  data?: JsonRecord | null;
}

export interface RendererProjectorSummary extends JsonRecord {
  id?: string;
  name?: string;
  host?: string;
  type?: string;
  scene?: string;
}

export interface RendererInstanceSummary extends JsonRecord {
  projector?: string;
  scene?: string;
  status?: string;
}

export interface RendererSceneSummary extends JsonRecord {
  id?: string;
  name?: string;
  description?: string;
  thumbnail?: string;
  dataInputs?: unknown[];
}

export interface OverlayConfigSummary extends JsonRecord {
  id?: number | string;
  name?: string;
  background_type?: string;
  video_id?: number | null;
  mapping_scene_id?: number | null;
  updated_at?: string;
}

export interface OverlayStatusResponse extends JsonRecord {
  brightness?: number;
  sync?: JsonRecord | null;
  server_time?: string;
}

export interface OverlaySyncResponse extends JsonRecord {
  status?: string;
  event_id?: string;
  affected_overlays?: string;
  synced_devices?: string[];
  failed_devices?: string[];
  device_count?: number;
}

export interface MappingSceneSummary extends JsonRecord {
  id?: number | string;
  name?: string;
  canvas_width?: number;
  canvas_height?: number;
  mask_mode?: string;
  masks?: JsonRecord[];
  groups?: JsonRecord[];
  updated_at?: string;
  created_at?: string;
}

export interface SceneRankSummary extends JsonRecord {
  id?: number | string;
  name?: string;
  orientation?: string;
  scene_ids?: Array<number | string>;
  gap_px?: number;
  updated_at?: string;
  created_at?: string;
}

export interface SceneControlPresetSummary extends JsonRecord {
  id?: number | string;
  name?: string;
  scene_ids?: Array<number | string>;
  rank_id?: number | string | null;
  group_assignments?: JsonRecord;
  row_edits?: JsonRecord;
  updated_at?: string;
  created_at?: string;
}

export interface ProjectionConfigSummary extends JsonRecord {
  id?: number | string;
  name?: string;
  mask_data?: JsonRecord | null;
  zones?: JsonRecord[];
  api_configs?: JsonRecord | null;
  updated_at?: string;
  created_at?: string;
}

export interface ProjectionSessionSummary extends JsonRecord {
  id?: string;
  status?: string;
  config_id?: number | string;
  maskId?: string;
  created_at?: string;
  zones?: JsonRecord[];
}
