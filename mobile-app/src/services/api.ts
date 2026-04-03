import type {
  DiscoveryBackendSummary,
  DiscoveryCapabilities,
  DeviceActionResponse,
  DeviceControlMode,
  DeviceDetail,
  DiscoveryStatus,
  DiscoverySystemStatus,
  DeviceSummary,
  HealthResponse,
  JsonRecord,
  MappingSceneSummary,
  MediaChannelSummary,
  MediaDirectorySummary,
  MediaListSummary,
  OverlayConfigSummary,
  OverlayStatusResponse,
  OverlaySyncResponse,
  PhotoSummary,
  ProjectionConfigSummary,
  ProjectionSessionSummary,
  RendererActionResponse,
  RendererInstanceSummary,
  RendererProjectorSummary,
  RendererSceneSummary,
  SceneControlPresetSummary,
  SceneRankSummary,
  StreamingAnalytics,
  StreamingSessionSummary,
  VideoSummary,
} from '../types/api';

const rawDefaultBaseUrl =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000/api';

export const DEFAULT_API_BASE_URL = normalizeApiBaseUrl(rawDefaultBaseUrl);

function ensureApiSuffix(pathname: string): string {
  const trimmed = pathname.replace(/\/+$/, '');
  if (trimmed.endsWith('/api')) {
    return trimmed;
  }
  return `${trimmed}/api`;
}

export function normalizeApiBaseUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return DEFAULT_API_BASE_URL;
  }

  if (/^https?:\/\//i.test(trimmed)) {
    const url = new URL(trimmed);
    url.pathname = ensureApiSuffix(url.pathname || '');
    url.search = '';
    url.hash = '';
    return url.toString().replace(/\/+$/, '');
  }

  if (trimmed.startsWith('/')) {
    return ensureApiSuffix(trimmed);
  }

  return normalizeApiBaseUrl(`http://${trimmed}`);
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text.trim()) {
    return {} as T;
  }

  return JSON.parse(text) as T;
}

function asArray<T>(value: unknown): T[] {
  if (Array.isArray(value)) {
    return value as T[];
  }
  return [];
}

function asRecord(value: unknown): JsonRecord | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as JsonRecord;
  }
  return null;
}

function extractArray<T>(payload: unknown, keys: string[] = []): T[] {
  if (Array.isArray(payload)) {
    return payload as T[];
  }

  const record = asRecord(payload);
  if (!record) {
    return [];
  }

  for (const key of keys) {
    if (Array.isArray(record[key])) {
      return record[key] as T[];
    }
  }

  const data = asRecord(record.data);
  if (!data) {
    return [];
  }

  for (const key of keys) {
    if (Array.isArray(data[key])) {
      return data[key] as T[];
    }
  }

  return [];
}

function appendQuery(
  path: string,
  query: Record<string, string | number | boolean | null | undefined>,
): string {
  const entries = Object.entries(query).filter(([, value]) => value !== undefined && value !== null);
  if (entries.length === 0) {
    return path;
  }

  const search = entries
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&');
  return `${path}?${search}`;
}

export class NanoDlnaApiClient {
  readonly apiBaseUrl: string;
  readonly rootBaseUrl: string;

  constructor(apiBaseUrl: string) {
    this.apiBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
    this.rootBaseUrl = this.apiBaseUrl.replace(/\/api$/, '');
  }

  private async requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.apiBaseUrl}${path}`, {
      headers: {
        Accept: 'application/json',
        ...(init?.headers ?? {}),
      },
      ...init,
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(
        `${response.status} ${response.statusText}${body ? ` - ${body}` : ''}`.trim(),
      );
    }

    return parseJson<T>(response);
  }

  async getHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.rootBaseUrl}/health`, {
      headers: { Accept: 'application/json' },
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(
        `${response.status} ${response.statusText}${body ? ` - ${body}` : ''}`.trim(),
      );
    }

    return parseJson<HealthResponse>(response);
  }

  async listDevices(): Promise<DeviceSummary[]> {
    const payload = await this.requestJson<unknown>('/devices');
    if (Array.isArray(payload)) {
      return payload as DeviceSummary[];
    }
    if (payload && typeof payload === 'object') {
      const record = payload as JsonRecord;
      return asArray<DeviceSummary>(record.devices);
    }
    return [];
  }

  async getDevice(deviceId: number | string): Promise<DeviceDetail> {
    return this.requestJson<DeviceDetail>(`/devices/${deviceId}`);
  }

  async getDiscoveryStatus(): Promise<DiscoveryStatus> {
    return this.requestJson<DiscoveryStatus>('/devices/discovery/status');
  }

  async getUnifiedDiscoveryStatus(): Promise<DiscoverySystemStatus> {
    return this.requestJson<DiscoverySystemStatus>('/v2/discovery/status');
  }

  async getUnifiedDiscoveryCapabilities(): Promise<DiscoveryCapabilities> {
    return this.requestJson<DiscoveryCapabilities>('/v2/discovery/capabilities');
  }

  async listDiscoveryBackends(): Promise<DiscoveryBackendSummary[]> {
    const payload = await this.requestJson<unknown>('/v2/discovery/backends');
    const record = asRecord(payload);
    if (!record) {
      return [];
    }
    return Object.entries(record).map(([name, value]) => ({
      name,
      ...(asRecord(value) ?? {}),
    }));
  }

  async enableDiscoveryBackend(backendName: string): Promise<DeviceActionResponse> {
    return this.requestJson<DeviceActionResponse>(`/v2/discovery/backends/${backendName}/enable`, {
      method: 'POST',
    });
  }

  async disableDiscoveryBackend(backendName: string): Promise<DeviceActionResponse> {
    return this.requestJson<DeviceActionResponse>(`/v2/discovery/backends/${backendName}/disable`, {
      method: 'POST',
    });
  }

  async pauseDiscovery(): Promise<DeviceActionResponse> {
    return this.requestJson<DeviceActionResponse>('/devices/discovery/pause', {
      method: 'POST',
    });
  }

  async resumeDiscovery(): Promise<DeviceActionResponse> {
    return this.requestJson<DeviceActionResponse>('/devices/discovery/resume', {
      method: 'POST',
    });
  }

  async discoverDevices(timeoutSeconds = 5): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/devices/discover?timeout=${timeoutSeconds}`, {
      method: 'POST',
    });
  }

  async getDeviceControlMode(deviceId: number | string): Promise<DeviceControlMode> {
    return this.requestJson<DeviceControlMode>(`/devices/${deviceId}/control`);
  }

  async enableAutoMode(deviceId: number | string): Promise<DeviceActionResponse> {
    return this.requestJson<DeviceActionResponse>(`/devices/${deviceId}/control/auto`, {
      method: 'POST',
    });
  }

  async enableManualMode(
    deviceId: number | string,
    options?: { reason?: string; expiresIn?: number },
  ): Promise<DeviceActionResponse> {
    const path = appendQuery(`/devices/${deviceId}/control/manual`, {
      reason: options?.reason ?? 'mobile_manual',
      expires_in: options?.expiresIn,
    });
    return this.requestJson<DeviceActionResponse>(path, {
      method: 'POST',
    });
  }

  async pauseDevicePlayback(deviceId: number | string): Promise<DeviceActionResponse> {
    return this.requestJson<DeviceActionResponse>(`/devices/${deviceId}/pause`, {
      method: 'POST',
    });
  }

  async stopDevicePlayback(deviceId: number | string): Promise<DeviceActionResponse> {
    return this.requestJson<DeviceActionResponse>(`/devices/${deviceId}/stop`, {
      method: 'POST',
    });
  }

  async playVideoOnDevice(
    deviceId: number | string,
    videoId: number | string,
    options?: { loop?: boolean; syncOverlays?: boolean },
  ): Promise<DeviceActionResponse> {
    const path = appendQuery(`/devices/${deviceId}/play`, {
      sync_overlays: options?.syncOverlays ?? false,
    });
    return this.requestJson<DeviceActionResponse>(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        video_id: Number(videoId),
        loop: options?.loop ?? false,
      }),
    });
  }

  async listVideos(): Promise<VideoSummary[]> {
    const payload = await this.requestJson<unknown>('/videos');
    if (Array.isArray(payload)) {
      return payload as VideoSummary[];
    }
    if (payload && typeof payload === 'object') {
      const record = payload as JsonRecord;
      return asArray<VideoSummary>(record.videos);
    }
    return [];
  }

  async listPhotos(): Promise<PhotoSummary[]> {
    const payload = await this.requestJson<unknown>('/photos');
    if (Array.isArray(payload)) {
      return payload as PhotoSummary[];
    }
    const record = asRecord(payload);
    return record ? asArray<PhotoSummary>(record.photos) : [];
  }

  async listMediaDirectories(): Promise<MediaDirectorySummary[]> {
    const payload = await this.requestJson<unknown>('/media-library/directories');
    return asArray<MediaDirectorySummary>(payload);
  }

  async scanMediaDirectory(directoryId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/media-library/directories/${directoryId}/scan`, {
      method: 'POST',
    });
  }

  async listMediaLists(): Promise<MediaListSummary[]> {
    const payload = await this.requestJson<unknown>('/media-library/lists');
    return asArray<MediaListSummary>(payload);
  }

  async listMediaChannels(): Promise<MediaChannelSummary[]> {
    const payload = await this.requestJson<unknown>('/media-library/channels');
    return asArray<MediaChannelSummary>(payload);
  }

  async advanceMediaChannel(channelId: number | string): Promise<MediaChannelSummary> {
    return this.requestJson<MediaChannelSummary>(`/media-library/channels/${channelId}/advance`, {
      method: 'POST',
    });
  }

  async getStreamingAnalytics(): Promise<StreamingAnalytics> {
    return this.requestJson<StreamingAnalytics>('/streaming/analytics');
  }

  async listStreamingSessions(): Promise<StreamingSessionSummary[]> {
    const payload = await this.requestJson<unknown>('/streaming/sessions');
    return asArray<StreamingSessionSummary>(payload);
  }

  async completeStreamingSession(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/streaming/sessions/${sessionId}/complete`, {
      method: 'POST',
    });
  }

  async resetStreamingSession(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/streaming/sessions/${sessionId}/reset`, {
      method: 'POST',
    });
  }

  async stopStreamingSession(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/streaming/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  }

  async listRenderers(): Promise<RendererInstanceSummary[]> {
    const payload = await this.requestJson<unknown>('/renderer/list');
    if (Array.isArray(payload)) {
      return payload as RendererInstanceSummary[];
    }
    const record = asRecord(payload);
    const data = asRecord(record?.data);
    return data ? asArray<RendererInstanceSummary>(data.renderers) : [];
  }

  async listProjectors(): Promise<RendererProjectorSummary[]> {
    const payload = await this.requestJson<unknown>('/renderer/projectors');
    if (Array.isArray(payload)) {
      return payload as RendererProjectorSummary[];
    }
    const record = asRecord(payload);
    const data = asRecord(record?.data);
    return data ? asArray<RendererProjectorSummary>(data.projectors) : [];
  }

  async listOverlayConfigs(): Promise<OverlayConfigSummary[]> {
    const payload = await this.requestJson<unknown>('/overlay/configs');
    return asArray<OverlayConfigSummary>(payload);
  }

  async listRendererScenes(): Promise<RendererSceneSummary[]> {
    const payload = await this.requestJson<unknown>('/renderer/scenes');
    return extractArray<RendererSceneSummary>(payload, ['scenes']);
  }

  async startRenderer(
    projector: string,
    scene: string,
  ): Promise<RendererActionResponse> {
    return this.requestJson<RendererActionResponse>('/renderer/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        projector,
        scene,
      }),
    });
  }

  async startProjector(projectorId: string): Promise<RendererActionResponse> {
    return this.requestJson<RendererActionResponse>(
      appendQuery('/renderer/start_projector', { projector_id: projectorId }),
      {
        method: 'POST',
      },
    );
  }

  async pauseRenderer(projectorId: string): Promise<RendererActionResponse> {
    return this.requestJson<RendererActionResponse>(`/renderer/pause/${projectorId}`, {
      method: 'POST',
    });
  }

  async resumeRenderer(projectorId: string): Promise<RendererActionResponse> {
    return this.requestJson<RendererActionResponse>(`/renderer/resume/${projectorId}`, {
      method: 'POST',
    });
  }

  async stopRenderer(projectorId: string): Promise<RendererActionResponse> {
    return this.requestJson<RendererActionResponse>('/renderer/stop', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        projector: projectorId,
      }),
    });
  }

  async getOverlayStatus(): Promise<OverlayStatusResponse> {
    return this.requestJson<OverlayStatusResponse>('/overlay/status');
  }

  async triggerOverlaySync(
    options?: { triggeredBy?: string; videoName?: string },
  ): Promise<OverlaySyncResponse> {
    return this.requestJson<OverlaySyncResponse>(
      appendQuery('/overlay/sync', {
        triggered_by: options?.triggeredBy ?? 'mobile_app',
        video_name: options?.videoName,
      }),
      {
        method: 'POST',
      },
    );
  }

  async listMappingScenes(): Promise<MappingSceneSummary[]> {
    const payload = await this.requestJson<unknown>('/mappings/scenes');
    return asArray<MappingSceneSummary>(payload);
  }

  async listSceneRanks(): Promise<SceneRankSummary[]> {
    const payload = await this.requestJson<unknown>('/mappings/ranks');
    return asArray<SceneRankSummary>(payload);
  }

  async listSceneControlPresets(): Promise<SceneControlPresetSummary[]> {
    const payload = await this.requestJson<unknown>('/mappings/scene-control-presets');
    return asArray<SceneControlPresetSummary>(payload);
  }

  async listProjectionConfigs(): Promise<ProjectionConfigSummary[]> {
    const payload = await this.requestJson<unknown>('/projection/configs');
    return asArray<ProjectionConfigSummary>(payload);
  }

  async launchProjectionConfig(
    configId: number | string,
  ): Promise<ProjectionSessionSummary> {
    return this.requestJson<ProjectionSessionSummary>(`/projection/configs/${configId}/launch`, {
      method: 'POST',
    });
  }

  async getProjectionSession(sessionId: string): Promise<ProjectionSessionSummary> {
    return this.requestJson<ProjectionSessionSummary>(`/projection/sessions/${sessionId}`);
  }
}
