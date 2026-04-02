export type JsonRecord = Record<string, unknown>;

export interface DeviceSummary extends JsonRecord {
  id?: number | string;
  name?: string;
  friendly_name?: string;
  device_name?: string;
  playback_state?: string;
  current_video?: string;
  current_media_title?: string;
  location?: string;
  streaming_url?: string;
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
