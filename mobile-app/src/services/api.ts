import {
  createHttpClient,
  DEFAULT_HTTP_BASE_URL,
  normalizeApiBaseUrl,
  type HttpClient,
  type HttpRequestOptions,
  type QueryRecord,
} from './httpClient.ts';
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
  OverlayCastSessionSummary,
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
  StreamingHealthResponse,
  StreamingSessionSummary,
  VideoSummary,
} from '../types/api.ts';

export { normalizeApiBaseUrl } from './httpClient.ts';

export const DEFAULT_API_BASE_URL = DEFAULT_HTTP_BASE_URL;

type UploadRequestOptions = Omit<HttpRequestOptions, 'body' | 'parseAs' | 'query'>;

const defaultSettings = {
  autoDiscoverDevices: true,
  defaultVideoDirectory: '/tmp/nanodlna/uploads',
  enableLogging: true,
  logLevel: 'info',
  serverPort: 8000,
  enableSubtitles: true,
};

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

function normalizeVideoId(value: number | string): number | string {
  if (typeof value === 'number') {
    return value;
  }

  const trimmed = value.trim();
  return /^\d+$/.test(trimmed) ? Number(trimmed) : value;
}

function requestUpload<T>(
  client: HttpClient,
  path: string,
  formData: FormData,
  options: UploadRequestOptions = {},
): Promise<T> {
  return client.post<T>(path, {
    ...options,
    body: formData,
  });
}

export class NanoDlnaApiClient {
  readonly apiBaseUrl: string;
  readonly rootBaseUrl: string;
  private readonly apiHttp: HttpClient;
  private readonly rootHttp: HttpClient;

  constructor(apiBaseUrl: string) {
    this.apiBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
    this.rootBaseUrl = this.apiBaseUrl.replace(/\/api$/, '');
    this.apiHttp = createHttpClient({ baseURL: this.apiBaseUrl, normalizeApiBase: false });
    this.rootHttp = createHttpClient({ baseURL: this.rootBaseUrl, normalizeApiBase: false });
  }

  buildApiUrl(path: string, query?: QueryRecord): string {
    return this.apiHttp.buildUrl(path, query);
  }

  buildRootUrl(path: string, query?: QueryRecord): string {
    return this.rootHttp.buildUrl(path, query);
  }

  private requestJson<T>(path: string, options: HttpRequestOptions = {}): Promise<T> {
    return this.apiHttp.request<T>(path, options);
  }

  private requestRootJson<T>(path: string, options: HttpRequestOptions = {}): Promise<T> {
    return this.rootHttp.request<T>(path, options);
  }

  async getHealth(): Promise<HealthResponse> {
    return this.requestRootJson<HealthResponse>('/health');
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
    return this.requestJson<JsonRecord>('/devices/discover', {
      method: 'POST',
      query: {
        timeout: timeoutSeconds,
      },
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
    return this.requestJson<DeviceActionResponse>(`/devices/${deviceId}/control/manual`, {
      method: 'POST',
      query: {
        reason: options?.reason ?? 'mobile_manual',
        expires_in: options?.expiresIn,
      },
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
    return this.requestJson<DeviceActionResponse>(`/devices/${deviceId}/play`, {
      method: 'POST',
      query: {
        sync_overlays: options?.syncOverlays ?? false,
      },
      body: {
        video_id: normalizeVideoId(videoId),
        loop: options?.loop ?? false,
      },
    });
  }

  async listVideos(): Promise<VideoSummary[]> {
    const payload = await this.requestJson<unknown>('/videos');
    if (Array.isArray(payload)) {
      return payload as VideoSummary[];
    }
    const record = asRecord(payload);
    return record ? asArray<VideoSummary>(record.videos) : [];
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

  async listPhotoLists(): Promise<JsonRecord[]> {
    const payload = await this.requestJson<unknown>('/photo-lists/');
    return asArray<JsonRecord>(payload);
  }

  async createMediaList(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/media-library/lists', {
      method: 'POST',
      body: payload,
    });
  }

  async createMediaChannel(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/media-library/channels', {
      method: 'POST',
      body: payload,
    });
  }

  async deleteMediaList(listId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/media-library/lists/${listId}`, {
      method: 'DELETE',
    });
  }

  async deleteMediaChannel(channelId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/media-library/channels/${channelId}`, {
      method: 'DELETE',
    });
  }

  async createVideo(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/videos/', {
      method: 'POST',
      body: payload,
    });
  }

  async deleteVideo(videoId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/videos/${videoId}`, {
      method: 'DELETE',
    });
  }

  async uploadVideo(formData: FormData): Promise<JsonRecord> {
    return requestUpload<JsonRecord>(this.apiHttp, '/videos/upload', formData);
  }

  async createPhoto(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/photos/', {
      method: 'POST',
      body: payload,
    });
  }

  async deletePhoto(photoId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/photos/${photoId}`, {
      method: 'DELETE',
    });
  }

  async uploadPhoto(formData: FormData): Promise<JsonRecord> {
    return requestUpload<JsonRecord>(this.apiHttp, '/photos/upload', formData);
  }

  async createMediaDirectory(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/media-library/directories', {
      method: 'POST',
      body: payload,
    });
  }

  async deleteMediaDirectory(directoryId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/media-library/directories/${directoryId}`, {
      method: 'DELETE',
    });
  }

  async createPhotoList(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/photo-lists/', {
      method: 'POST',
      body: payload,
    });
  }

  async deletePhotoList(listId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/photo-lists/${listId}`, {
      method: 'DELETE',
    });
  }

  async getGlobalApiConfigs(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/global-api-configs');
  }

  async updateGlobalApiConfigs(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/global-api-configs', {
      method: 'PUT',
      body: payload,
    });
  }

  async getProjectorRedirectConfig(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/projector-redirect');
  }

  async updateProjectorRedirectConfig(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/projector-redirect', {
      method: 'PUT',
      body: payload,
    });
  }

  async getRecentProjectorRedirectRequests(limit = 50): Promise<JsonRecord[]> {
    const payload = await this.requestJson<unknown>('/overlay/projector-redirect/recent', {
      query: { limit },
    });
    return asArray<JsonRecord>(payload);
  }

  async getServiceDiagnostics(params: QueryRecord = {}): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/diagnostics/service', {
      query: params,
    });
  }

  async getIncidentDetail(incidentId: string, params: QueryRecord = {}): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/diagnostics/incidents/${incidentId}`, {
      query: params,
    });
  }

  async getLogs(params: QueryRecord = {}): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/logs', {
      query: params,
    });
  }

  async getLogSources(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/logs/sources');
  }

  async getLogLevels(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/logs/levels');
  }

  async getLogStats(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/logs/stats');
  }

  async tailLogSource(source: string, lines = 100): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/logs/tail/${encodeURIComponent(source)}`, {
      query: { lines },
    });
  }

  async exportLogs(format: string, params: QueryRecord = {}): Promise<Blob> {
    return this.requestJson<Blob>('/logs/export', {
      query: { format, ...params },
      parseAs: 'blob',
    });
  }

  async getStreamingAnalytics(): Promise<StreamingAnalytics> {
    return this.requestJson<StreamingAnalytics>('/streaming/analytics');
  }

  async listStreamingSessions(): Promise<StreamingSessionSummary[]> {
    const payload = await this.requestJson<unknown>('/streaming/sessions');
    return asArray<StreamingSessionSummary>(payload);
  }

  async getStreamingHealth(): Promise<StreamingHealthResponse> {
    return this.requestJson<StreamingHealthResponse>('/streaming/health');
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

  async listOverlayCastSessions(): Promise<OverlayCastSessionSummary[]> {
    const payload = await this.requestJson<unknown>('/overlay/cast/sessions');
    return asArray<OverlayCastSessionSummary>(payload);
  }

  async stopOverlayCastSession(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/overlay/cast/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  }

  async createOverlayConfig(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/configs', {
      method: 'POST',
      body: payload,
    });
  }

  async deleteOverlayConfig(configId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/overlay/configs/${configId}`, {
      method: 'DELETE',
    });
  }

  async duplicateOverlayConfig(configId: number | string): Promise<OverlayConfigSummary> {
    return this.requestJson<OverlayConfigSummary>(`/overlay/configs/${configId}/duplicate`, {
      method: 'POST',
    });
  }

  async createOverlayStream(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/stream', {
      method: 'POST',
      body: payload,
    });
  }

  async getOverlayWindowInit(projectorId?: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/window-init', {
      query: projectorId ? { projector_id: projectorId } : {},
    });
  }

  async getOverlayWindowRefreshState(projectorId?: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/window-refresh-state', {
      query: projectorId ? { projector_id: projectorId } : {},
    });
  }

  async getOverlayWidgetData(projectorId?: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/widget-data', {
      query: projectorId ? { projector_id: projectorId } : {},
    });
  }

  async heartbeatProjectorClient(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/projector-clients/heartbeat', {
      method: 'POST',
      body: payload,
    });
  }

  async getOverlayPlaybackSync(projectorId?: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/playback-sync', {
      query: projectorId ? { projector_id: projectorId } : {},
    });
  }

  async getBrightnessStatus(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/brightness/status');
  }

  getOverlayEventsUrl(): string {
    return this.buildApiUrl('/overlay/events');
  }

  async getOverlayBrightness(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/brightness');
  }

  async setOverlayBrightness(brightness: number): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/brightness', {
      method: 'POST',
      query: { brightness },
    });
  }

  async exportOverlayMp4(payload: JsonRecord): Promise<Blob> {
    return this.requestJson<Blob>('/overlay/export', {
      method: 'POST',
      body: payload,
      parseAs: 'blob',
      timeout: 0,
    });
  }

  async startOverlayCast(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/overlay/cast', {
      method: 'POST',
      body: payload,
    });
  }

  async listRendererScenes(): Promise<RendererSceneSummary[]> {
    const payload = await this.requestJson<unknown>('/renderer/scenes');
    return extractArray<RendererSceneSummary>(payload, ['scenes']);
  }

  async getRendererStatus(projectorId: string): Promise<JsonRecord> {
    const payload = await this.requestJson<unknown>(`/renderer/status/${projectorId}`);
    const record = asRecord(payload);
    return asRecord(record?.data) ?? record ?? {};
  }

  async startRenderer(projector: string, scene: string): Promise<RendererActionResponse> {
    return this.requestJson<RendererActionResponse>('/renderer/start', {
      method: 'POST',
      body: {
        projector,
        scene,
      },
    });
  }

  async startProjector(projectorId: string): Promise<RendererActionResponse> {
    return this.requestJson<RendererActionResponse>('/renderer/start_projector', {
      method: 'POST',
      query: {
        projector_id: projectorId,
      },
    });
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
      body: {
        projector: projectorId,
      },
    });
  }

  async getOverlayStatus(): Promise<OverlayStatusResponse> {
    return this.requestJson<OverlayStatusResponse>('/overlay/status');
  }

  async discoverAirPlayDevices(): Promise<JsonRecord> {
    const payload = await this.requestJson<unknown>('/renderer/airplay/discover');
    return (asRecord(payload)?.data as JsonRecord) ?? asRecord(payload) ?? {};
  }

  async listAirPlayDevices(): Promise<JsonRecord> {
    const payload = await this.requestJson<unknown>('/renderer/airplay/list');
    return (asRecord(payload)?.data as JsonRecord) ?? asRecord(payload) ?? {};
  }

  async getAllAirPlayDevices(): Promise<JsonRecord> {
    const payload = await this.requestJson<unknown>('/renderer/airplay/devices');
    return (asRecord(payload)?.data as JsonRecord) ?? asRecord(payload) ?? {};
  }

  async triggerOverlaySync(
    options?: { triggeredBy?: string; videoName?: string },
  ): Promise<OverlaySyncResponse> {
    return this.requestJson<OverlaySyncResponse>('/overlay/sync', {
      method: 'POST',
      query: {
        triggered_by: options?.triggeredBy ?? 'mobile_app',
        video_name: options?.videoName,
      },
    });
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

  async createProjectionConfig(payload: JsonRecord): Promise<ProjectionConfigSummary> {
    return this.requestJson<ProjectionConfigSummary>('/projection/configs', {
      method: 'POST',
      body: payload,
    });
  }

  async getProjectionConfig(configId: number | string): Promise<ProjectionConfigSummary> {
    return this.requestJson<ProjectionConfigSummary>(`/projection/configs/${configId}`);
  }

  async updateProjectionConfig(configId: number | string, payload: JsonRecord): Promise<ProjectionConfigSummary> {
    return this.requestJson<ProjectionConfigSummary>(`/projection/configs/${configId}`, {
      method: 'PUT',
      body: payload,
    });
  }

  async deleteProjectionConfig(configId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/projection/configs/${configId}`, {
      method: 'DELETE',
    });
  }

  async duplicateProjectionConfig(configId: number | string): Promise<ProjectionConfigSummary> {
    return this.requestJson<ProjectionConfigSummary>(`/projection/configs/${configId}/duplicate`, {
      method: 'POST',
    });
  }

  async createProjectionSession(payload: JsonRecord): Promise<ProjectionSessionSummary> {
    return this.requestJson<ProjectionSessionSummary>('/projection/sessions/create', {
      method: 'POST',
      body: payload,
    });
  }

  async deleteProjectionSession(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/projection/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  }

  async uploadProjectionMask(formData: FormData): Promise<JsonRecord> {
    return requestUpload<JsonRecord>(this.apiHttp, '/projection/mask', formData);
  }

  async getProjectionMask(maskId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/projection/masks/${maskId}`);
  }

  getProjectionMaskImageUrl(sessionId: string): string {
    return this.buildApiUrl(`/projection/masks/${sessionId}/image`);
  }

  async importCodepenAnimation(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/projection/animations/import', {
      method: 'POST',
      body: payload,
    });
  }

  async listProjectionConfigs(): Promise<ProjectionConfigSummary[]> {
    const payload = await this.requestJson<unknown>('/projection/configs');
    return asArray<ProjectionConfigSummary>(payload);
  }

  async launchProjectionConfig(configId: number | string): Promise<ProjectionSessionSummary> {
    return this.requestJson<ProjectionSessionSummary>(`/projection/configs/${configId}/launch`, {
      method: 'POST',
    });
  }

  async getProjectionSession(sessionId: string): Promise<ProjectionSessionSummary> {
    return this.requestJson<ProjectionSessionSummary>(`/projection/sessions/${sessionId}`);
  }

  async listProjectionAnimations(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/projection/animations');
  }

  async listProjectionAnimationLists(): Promise<JsonRecord[]> {
    return this.requestJson<JsonRecord[]>('/projection/animation-lists');
  }

  async getProjectionAnimationList(id: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/projection/animation-lists/${id}`);
  }

  async createProjectionAnimationList(data: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/projection/animation-lists', {
      method: 'POST',
      body: data,
    });
  }

  async updateProjectionAnimationList(id: number | string, data: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/projection/animation-lists/${id}`, {
      method: 'PUT',
      body: data,
    });
  }

  async deleteProjectionAnimationList(id: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/projection/animation-lists/${id}`, {
      method: 'DELETE',
    });
  }

  async startStructuredLightingWorker(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/structured-lighting/worker/start', {
      method: 'POST',
      body: payload,
    });
  }

  async stopStructuredLightingWorker(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/structured-lighting/worker/stop', {
      method: 'POST',
    });
  }

  async confirmStructuredLightingWorkerReady(workerId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/worker/${workerId}/confirm-ready`, {
      method: 'POST',
    });
  }

  async decodeStructuredLightingSession(sessionId: string, payload: JsonRecord = {}): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/decode`, {
      method: 'POST',
      body: payload,
    });
  }

  async runStructuredLightingPreviewTuning(sessionId: string, payload: JsonRecord = {}): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/preview-tuning`, {
      method: 'POST',
      body: payload,
    });
  }

  async getStructuredLightingPreviewTuning(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/preview-tuning`);
  }

  async runStructuredLightingTuningSearch(sessionId: string, payload: JsonRecord = {}): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/tuning-search`, {
      method: 'POST',
      body: payload,
    });
  }

  async getStructuredLightingTuningSearch(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/tuning-search`);
  }

  async getStructuredLightingCalibration(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/calibration`);
  }

  async getStructuredLightingArtifactReview(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/artifacts/review`);
  }

  async updateStructuredLightingReview(sessionId: string, payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/review`, {
      method: 'POST',
      body: payload,
    });
  }

  async publishStructuredLightingMappingScene(sessionId: string, payload: JsonRecord = {}): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/publish-mapping-scene`, {
      method: 'POST',
      body: payload,
    });
  }

  getStructuredLightingStepImageUrl(sessionId: string, stepIndex: number | string): string {
    return this.buildApiUrl(`/structured-lighting/sessions/${sessionId}/steps/${stepIndex}/image`);
  }

  getStructuredLightingCaptureImageUrl(sessionId: string, stepIndex: number | string): string {
    return this.buildApiUrl(`/structured-lighting/sessions/${sessionId}/captures/${stepIndex}/image`);
  }

  getStructuredLightingArtifactPreviewUrl(sessionId: string, previewId: string): string {
    return this.buildApiUrl(`/structured-lighting/sessions/${sessionId}/artifacts/previews/${previewId}`);
  }

  getStructuredLightingPreviewTuningPreviewUrl(sessionId: string, candidateId: string, previewName: string): string {
    return this.buildApiUrl(`/structured-lighting/sessions/${sessionId}/preview-tuning/${candidateId}/previews/${previewName}`);
  }

  getStructuredLightingTuningSearchPreviewUrl(sessionId: string, candidateId: string, previewName: string): string {
    return this.buildApiUrl(`/structured-lighting/sessions/${sessionId}/tuning-search/${candidateId}/previews/${previewName}`);
  }

  getStructuredLightingExportUrl(sessionId: string): string {
    return this.buildApiUrl(`/structured-lighting/sessions/${sessionId}/export`);
  }

  async uploadStructuredLightingCapture(sessionId: string, formData: FormData): Promise<JsonRecord> {
    return requestUpload<JsonRecord>(this.apiHttp, `/structured-lighting/sessions/${sessionId}/captures`, formData);
  }

  async getStructuredLightingCapabilities(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/structured-lighting/capabilities');
  }

  async getStructuredLightingStatus(): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/structured-lighting/status');
  }

  async listStructuredLightingSessions(): Promise<JsonRecord[]> {
    return this.requestJson<JsonRecord[]>('/structured-lighting/sessions');
  }

  async createStructuredLightingSession(payload: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/structured-lighting/sessions', {
      method: 'POST',
      body: payload,
    });
  }

  async deleteStructuredLightingSession(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  }

  async getStructuredLightingRuntime(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/runtime`);
  }

  async listStructuredLightingCaptures(sessionId: string): Promise<JsonRecord[]> {
    return this.requestJson<JsonRecord[]>(`/structured-lighting/sessions/${sessionId}/captures`);
  }

  async startStructuredLightingSession(sessionId: string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/structured-lighting/sessions/${sessionId}/start`, {
      method: 'POST',
    });
  }

  async uploadDepthMap(formData: FormData): Promise<JsonRecord> {
    return requestUpload<JsonRecord>(this.apiHttp, '/depth/upload', formData);
  }

  getDepthPreviewUrl(depthId: number | string): string {
    return this.buildApiUrl(`/depth/preview/${depthId}`);
  }

  async segmentDepthMap(depthId: number | string, segmentationParams: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/depth/segment/${depthId}`, {
      method: 'POST',
      body: segmentationParams,
    });
  }

  getDepthSegmentationPreviewUrl(depthId: number | string, alpha = 0.5): string {
    return this.buildApiUrl(`/depth/segmentation_preview/${depthId}`, { alpha });
  }

  async exportDepthMasks(
    depthId: number | string,
    segmentIds: Array<number | string>,
    cleanMask = true,
    minArea = 100,
    kernelSize = 3,
  ): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/depth/export_masks/${depthId}`, {
      method: 'POST',
      body: {
        segment_ids: segmentIds,
        clean_mask: cleanMask,
        min_area: minArea,
        kernel_size: kernelSize,
      },
    });
  }

  async deleteDepthMap(depthId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/depth/${depthId}`, {
      method: 'DELETE',
    });
  }

  getDepthMaskUrl(
    depthId: number | string,
    segmentId: number | string,
    clean = true,
    minArea = 100,
    kernelSize = 3,
  ): string {
    return this.buildApiUrl(`/depth/mask/${depthId}/${segmentId}`, {
      clean,
      min_area: minArea,
      kernel_size: kernelSize,
    });
  }

  async createDepthProjection(config: JsonRecord): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>('/depth/projection/create', {
      method: 'POST',
      body: config,
    });
  }

  getDepthProjectionUrl(configId: number | string): string {
    return this.buildApiUrl(`/depth/projection/${configId}`);
  }

  async deleteDepthProjection(configId: number | string): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/depth/projection/${configId}`, {
      method: 'DELETE',
    });
  }
}

export function createServiceModules(apiBaseUrl: string = DEFAULT_API_BASE_URL) {
  const client = new NanoDlnaApiClient(apiBaseUrl);
  const api = createHttpClient({ baseURL: client.apiBaseUrl, normalizeApiBase: false });

  const buildApiUrl = (path: string, query?: QueryRecord) => client.buildApiUrl(path, query);

  const deviceApi = {
    getDevices: async (params: QueryRecord = {}) => {
      if (Object.keys(params).length === 0) {
        return client.listDevices();
      }
      return api.get<unknown>('/devices/', { query: params });
    },
    getDevice: (id: number | string) => client.getDevice(id),
    createDevice: (data: JsonRecord) => api.post<JsonRecord>('/devices/', { body: data }),
    updateDevice: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/devices/${id}`, { body: data }),
    deleteDevice: (id: number | string) => api.delete<JsonRecord>(`/devices/${id}`),
    discoverDevices: () => api.get<JsonRecord>('/devices/discover'),
    playVideo: (
      deviceId: number | string,
      videoId: number | string,
      loop = false,
      syncOverlays = false,
    ) => client.playVideoOnDevice(deviceId, videoId, { loop, syncOverlays }),
    stopVideo: (deviceId: number | string) => client.stopDevicePlayback(deviceId),
    pauseVideo: (deviceId: number | string) => client.pauseDevicePlayback(deviceId),
    seekVideo: (deviceId: number | string, position: number) => api.post<DeviceActionResponse>(`/devices/${deviceId}/seek`, {
      query: { position },
    }),
    loadConfig: (configFile: string) => api.post<JsonRecord>('/devices/load-config', {
      query: { config_file: configFile },
    }),
    saveConfig: (configFile: string) => api.post<DeviceActionResponse>('/devices/save-config', {
      query: { config_file: configFile },
    }),
    pauseDiscovery: () => client.pauseDiscovery(),
    resumeDiscovery: () => client.resumeDiscovery(),
    setDiscoveryInterval: (seconds: number) => api.post<DeviceActionResponse>('/devices/discovery/interval', {
      query: { seconds },
    }),
    getDiscoveryStatus: () => client.getDiscoveryStatus(),
    enableAutoMode: (deviceId: number | string) => client.enableAutoMode(deviceId),
    enableManualMode: (deviceId: number | string, reason?: string, expiresIn?: number) =>
      client.enableManualMode(deviceId, { reason, expiresIn }),
    getControlMode: (deviceId: number | string) => client.getDeviceControlMode(deviceId),
  };

  const discoveryV2Api = {
    getDevices: (params: QueryRecord = {}) => api.get<JsonRecord[]>('/v2/discovery/devices', { query: params }),
    getDevice: (deviceId: string) => api.get<JsonRecord>(`/v2/discovery/devices/${deviceId}`),
    triggerDiscovery: (backend: string | null = null, timeout = 30) => api.post<JsonRecord>('/v2/discovery/discover', {
      query: { backend, timeout },
    }),
    getDeviceConfigs: () => api.get<JsonRecord[]>('/v2/discovery/config/devices'),
    getDeviceConfig: (deviceName: string) => api.get<JsonRecord>(`/v2/discovery/config/devices/${deviceName}`),
    updateDeviceConfig: (deviceName: string, config: JsonRecord) =>
      api.put<JsonRecord>(`/v2/discovery/config/devices/${deviceName}`, { body: config }),
    deleteDeviceConfig: (deviceName: string) => api.delete<JsonRecord>(`/v2/discovery/config/devices/${deviceName}`),
    getGlobalConfig: () => api.get<JsonRecord>('/v2/discovery/config/global'),
    updateGlobalConfig: (config: JsonRecord) => api.put<JsonRecord>('/v2/discovery/config/global', { body: config }),
    getBackends: () => client.listDiscoveryBackends(),
    enableBackend: (backendName: string) => client.enableDiscoveryBackend(backendName),
    disableBackend: (backendName: string) => client.disableDiscoveryBackend(backendName),
    startCast: (deviceId: string, contentUrl: string, options: JsonRecord = {}) => api.post<JsonRecord>('/v2/discovery/cast', {
      body: {
        device_id: deviceId,
        content_url: contentUrl,
        content_type: options.content_type ?? 'video/mp4',
        metadata: options.metadata ?? null,
      },
    }),
    stopCast: (sessionId: string) => api.post<JsonRecord>(`/v2/discovery/stop/${sessionId}`),
    pauseCast: (sessionId: string) => api.post<JsonRecord>(`/v2/discovery/pause/${sessionId}`),
    resumeCast: (sessionId: string) => api.post<JsonRecord>(`/v2/discovery/resume/${sessionId}`),
    getActiveSessions: () => api.get<JsonRecord[]>('/v2/discovery/sessions'),
    getSystemStatus: () => client.getUnifiedDiscoveryStatus(),
  };

  const overlayApi = {
    listConfigs: (params: QueryRecord = {}) => {
      if (Object.keys(params).length === 0) {
        return client.listOverlayConfigs();
      }
      return api.get<JsonRecord[]>('/overlay/configs', { query: params });
    },
    getConfig: (configId: number | string) => api.get<JsonRecord>(`/overlay/configs/${configId}`),
    createConfig: (payload: JsonRecord) => client.createOverlayConfig(payload),
    updateConfig: (configId: number | string, payload: JsonRecord) =>
      api.put<JsonRecord>(`/overlay/configs/${configId}`, { body: payload }),
    deleteConfig: (configId: number | string) => client.deleteOverlayConfig(configId),
    duplicateConfig: (configId: number | string) => client.duplicateOverlayConfig(configId),
    getGlobalApiConfigs: () => client.getGlobalApiConfigs(),
    updateGlobalApiConfigs: (payload: JsonRecord) => client.updateGlobalApiConfigs(payload),
    getProjectorRedirectConfig: () => client.getProjectorRedirectConfig(),
    updateProjectorRedirectConfig: (payload: JsonRecord) => client.updateProjectorRedirectConfig(payload),
    getRecentProjectorRedirectRequests: (limit = 50) => client.getRecentProjectorRedirectRequests(limit),
    listTemplates: () => api.get<JsonRecord[]>('/overlay/templates'),
    createConfigFromTemplate: (
      templateId: number | string,
      videoId: number | string,
      name?: string,
    ) =>
      api.post<JsonRecord>(`/overlay/configs/from-template/${templateId}`, {
        query: { video_id: videoId, name },
      }),
    getBrightness: () => client.getOverlayBrightness(),
    setBrightness: (brightness: number) => client.setOverlayBrightness(brightness),
    exportMp4: (payload: JsonRecord) => client.exportOverlayMp4(payload),
    startCast: (payload: JsonRecord) => client.startOverlayCast(payload),
    listCastSessions: () => client.listOverlayCastSessions(),
    stopCastSession: (sessionId: string) => client.stopOverlayCastSession(sessionId),
    createStream: (payload: JsonRecord) => client.createOverlayStream(payload),
    getWindowInit: (projectorId?: string) => client.getOverlayWindowInit(projectorId),
    getWindowRefreshState: (projectorId?: string) => client.getOverlayWindowRefreshState(projectorId),
    getWidgetData: (projectorId?: string) => client.getOverlayWidgetData(projectorId),
    heartbeatProjectorClient: (payload: JsonRecord) => client.heartbeatProjectorClient(payload),
    getPlaybackSync: (projectorId?: string) => client.getOverlayPlaybackSync(projectorId),
    getBrightnessStatus: () => client.getBrightnessStatus(),
    getEventsUrl: () => client.getOverlayEventsUrl(),
  };

  const structuredLightingApi = {
    getCapabilities: () => client.getStructuredLightingCapabilities(),
    getStatus: () => client.getStructuredLightingStatus(),
    startWorker: (payload: JsonRecord) => client.startStructuredLightingWorker(payload),
    stopWorker: () => client.stopStructuredLightingWorker(),
    confirmWorkerReady: (workerId: string) => client.confirmStructuredLightingWorkerReady(workerId),
    listSessions: () => client.listStructuredLightingSessions(),
    createSession: (payload: JsonRecord) => client.createStructuredLightingSession(payload),
    deleteSession: (sessionId: string) => client.deleteStructuredLightingSession(sessionId),
    getCapturePlan: (sessionId: string) => api.get<JsonRecord>(`/structured-lighting/sessions/${sessionId}/capture-plan`),
    getRuntime: (sessionId: string) => client.getStructuredLightingRuntime(sessionId),
    listCaptures: (sessionId: string) => client.listStructuredLightingCaptures(sessionId),
    decodeSession: (sessionId: string, payload: JsonRecord = {}) => client.decodeStructuredLightingSession(sessionId, payload),
    runPreviewTuning: (sessionId: string, payload: JsonRecord = {}) => client.runStructuredLightingPreviewTuning(sessionId, payload),
    getPreviewTuning: (sessionId: string) => client.getStructuredLightingPreviewTuning(sessionId),
    runTuningSearch: (sessionId: string, payload: JsonRecord = {}) => client.runStructuredLightingTuningSearch(sessionId, payload),
    getTuningSearch: (sessionId: string) => client.getStructuredLightingTuningSearch(sessionId),
    getCalibration: (sessionId: string) => client.getStructuredLightingCalibration(sessionId),
    getArtifactReview: (sessionId: string) => client.getStructuredLightingArtifactReview(sessionId),
    updateReview: (sessionId: string, payload: JsonRecord) => client.updateStructuredLightingReview(sessionId, payload),
    startSession: (sessionId: string) => client.startStructuredLightingSession(sessionId),
    publishMappingScene: (sessionId: string, payload: JsonRecord = {}) => client.publishStructuredLightingMappingScene(sessionId, payload),
    getStepImageUrl: (sessionId: string, stepIndex: number | string) => client.getStructuredLightingStepImageUrl(sessionId, stepIndex),
    getCaptureImageUrl: (sessionId: string, stepIndex: number | string) => client.getStructuredLightingCaptureImageUrl(sessionId, stepIndex),
    getArtifactPreviewUrl: (sessionId: string, previewId: string) => client.getStructuredLightingArtifactPreviewUrl(sessionId, previewId),
    getPreviewTuningPreviewUrl: (sessionId: string, candidateId: string, previewName: string) => client.getStructuredLightingPreviewTuningPreviewUrl(sessionId, candidateId, previewName),
    getTuningSearchPreviewUrl: (sessionId: string, candidateId: string, previewName: string) => client.getStructuredLightingTuningSearchPreviewUrl(sessionId, candidateId, previewName),
    getExportUrl: (sessionId: string) => client.getStructuredLightingExportUrl(sessionId),
    uploadCapture: (sessionId: string, formData: FormData) => client.uploadStructuredLightingCapture(sessionId, formData),
  };

  const videoApi = {
    getVideos: (params: QueryRecord = {}) => {
      if (Object.keys(params).length === 0) {
        return client.listVideos();
      }
      return api.get<JsonRecord[]>('/videos/', { query: params });
    },
    getVideo: (id: number | string) => api.get<JsonRecord>(`/videos/${id}`),
    createVideo: (data: JsonRecord) => api.post<JsonRecord>('/videos/', { body: data }),
    updateVideo: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/videos/${id}`, { body: data }),
    deleteVideo: (id: number | string) => api.delete<JsonRecord>(`/videos/${id}`),
    uploadVideo: (formData: FormData, options: UploadRequestOptions = {}) => requestUpload<JsonRecord>(api, '/videos/upload', formData, options),
    streamVideo: (id: number | string, serveIp: string) => api.post<JsonRecord>(`/videos/${id}/stream`, {
      query: { serve_ip: serveIp },
    }),
    scanDirectory: (directory: string, category = 'background', sourceDirectoryId: number | string | null = null) =>
      api.post<JsonRecord>('/videos/scan-directory', {
        query: {
          directory,
          category,
          source_directory_id: sourceDirectoryId,
        },
      }),
  };

  const photoApi = {
    getPhotos: (params: QueryRecord = {}) => {
      if (Object.keys(params).length === 0) {
        return client.listPhotos();
      }
      return api.get<JsonRecord[]>('/photos/', { query: params });
    },
    getPhoto: (id: number | string) => api.get<JsonRecord>(`/photos/${id}`),
    createPhoto: (data: JsonRecord) => api.post<JsonRecord>('/photos/', { body: data }),
    updatePhoto: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/photos/${id}`, { body: data }),
    deletePhoto: (id: number | string) => api.delete<JsonRecord>(`/photos/${id}`),
    uploadPhoto: (formData: FormData, options: UploadRequestOptions = {}) => requestUpload<JsonRecord>(api, '/photos/upload', formData, options),
    scanDirectory: (directory: string, category = 'background', sourceDirectoryId: number | string | null = null) =>
      api.post<JsonRecord>('/photos/scan-directory', {
        query: {
          directory,
          category,
          source_directory_id: sourceDirectoryId,
        },
      }),
  };

  const mappingsApi = {
    listScenes: () => client.listMappingScenes(),
    getScene: (id: number | string) => api.get<JsonRecord>(`/mappings/scenes/${id}`),
    createScene: (data: JsonRecord) => api.post<JsonRecord>('/mappings/scenes', { body: data }),
    updateScene: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/mappings/scenes/${id}`, { body: data }),
    deleteScene: (id: number | string) => api.delete<JsonRecord>(`/mappings/scenes/${id}`),
    listRanks: () => client.listSceneRanks(),
    getRank: (id: number | string) => api.get<JsonRecord>(`/mappings/ranks/${id}`),
    createRank: (data: JsonRecord) => api.post<JsonRecord>('/mappings/ranks', { body: data }),
    updateRank: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/mappings/ranks/${id}`, { body: data }),
    deleteRank: (id: number | string) => api.delete<JsonRecord>(`/mappings/ranks/${id}`),
    listSceneControlPresets: () => client.listSceneControlPresets(),
    getSceneControlPreset: (id: number | string) => api.get<JsonRecord>(`/mappings/scene-control-presets/${id}`),
    createSceneControlPreset: (data: JsonRecord) => api.post<JsonRecord>('/mappings/scene-control-presets', { body: data }),
    updateSceneControlPreset: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/mappings/scene-control-presets/${id}`, { body: data }),
    deleteSceneControlPreset: (id: number | string) => api.delete<JsonRecord>(`/mappings/scene-control-presets/${id}`),
    importScene: (formData: FormData, options: UploadRequestOptions = {}) => requestUpload<JsonRecord>(api, '/mappings/scenes/import', formData, options),
    getExportUrl: (id: number | string) => buildApiUrl(`/mappings/scenes/${id}/export`),
    createPolygonMask: (id: number | string, data: JsonRecord) => api.post<JsonRecord>(`/mappings/scenes/${id}/masks/polygon`, { body: data }),
    uploadMasks: (id: number | string, formData: FormData, options: UploadRequestOptions = {}) => requestUpload<JsonRecord>(api, `/mappings/scenes/${id}/masks/upload`, formData, options),
    deleteMask: (sceneId: number | string, maskId: number | string) => api.delete<JsonRecord>(`/mappings/scenes/${sceneId}/masks/${maskId}`),
  };

  const mediaLibraryApi = {
    listDirectories: () => client.listMediaDirectories(),
    browseDirectories: (path: string | null = null) => api.get<JsonRecord[]>('/media-library/directories/browse', { query: { path } }),
    createDirectory: (data: JsonRecord) => api.post<JsonRecord>('/media-library/directories', { body: data }),
    updateDirectory: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/media-library/directories/${id}`, { body: data }),
    deleteDirectory: (id: number | string) => api.delete<JsonRecord>(`/media-library/directories/${id}`),
    scanDirectory: (id: number | string) => client.scanMediaDirectory(id),
    listMediaLists: () => client.listMediaLists(),
    createMediaList: (data: JsonRecord) => api.post<JsonRecord>('/media-library/lists', { body: data }),
    updateMediaList: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/media-library/lists/${id}`, { body: data }),
    deleteMediaList: (id: number | string) => api.delete<JsonRecord>(`/media-library/lists/${id}`),
    listMediaChannels: () => client.listMediaChannels(),
    createMediaChannel: (data: JsonRecord) => api.post<JsonRecord>('/media-library/channels', { body: data }),
    updateMediaChannel: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/media-library/channels/${id}`, { body: data }),
    advanceMediaChannel: (id: number | string) => client.advanceMediaChannel(id),
    deleteMediaChannel: (id: number | string) => api.delete<JsonRecord>(`/media-library/channels/${id}`),
  };

  const photoListApi = {
    listPhotoLists: () => api.get<JsonRecord[]>('/photo-lists/'),
    createPhotoList: (data: JsonRecord) => api.post<JsonRecord>('/photo-lists/', { body: data }),
    updatePhotoList: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/photo-lists/${id}`, { body: data }),
    deletePhotoList: (id: number | string) => api.delete<JsonRecord>(`/photo-lists/${id}`),
  };

  const projectionApi = {
    listConfigs: () => client.listProjectionConfigs(),
    getConfig: (id: number | string) => client.getProjectionConfig(id),
    createConfig: (data: JsonRecord) => client.createProjectionConfig(data),
    updateConfig: (id: number | string, data: JsonRecord) => client.updateProjectionConfig(id, data),
    deleteConfig: (id: number | string) => client.deleteProjectionConfig(id),
    duplicateConfig: (id: number | string) => client.duplicateProjectionConfig(id),
    launchConfig: (id: number | string) => client.launchProjectionConfig(id),
    createSession: (data: JsonRecord) => client.createProjectionSession(data),
    getSession: (id: string) => client.getProjectionSession(id),
    deleteSession: (id: string) => client.deleteProjectionSession(id),
    uploadMask: (formData: FormData) => client.uploadProjectionMask(formData),
    getMask: (maskId: string) => client.getProjectionMask(maskId),
    getMaskImageUrl: (sessionId: string) => client.getProjectionMaskImageUrl(sessionId),
    listAnimations: () => api.get<JsonRecord>('/projection/animations'),
    importCodepenAnimation: (data: JsonRecord) => client.importCodepenAnimation(data),
    listAnimationLists: () => api.get<JsonRecord[]>('/projection/animation-lists'),
    getAnimationList: (id: number | string) => api.get<JsonRecord>(`/projection/animation-lists/${id}`),
    createAnimationList: (data: JsonRecord) => api.post<JsonRecord>('/projection/animation-lists', { body: data }),
    updateAnimationList: (id: number | string, data: JsonRecord) => api.put<JsonRecord>(`/projection/animation-lists/${id}`, { body: data }),
    deleteAnimationList: (id: number | string) => api.delete<JsonRecord>(`/projection/animation-lists/${id}`),
  };

  const rendererApi = {
    startRenderer: (scene: string, projector: string, options: JsonRecord = {}) => api.post<RendererActionResponse>('/renderer/start', {
      body: { scene, projector, options },
    }),
    stopRenderer: (projector: string) => api.post<RendererActionResponse>('/renderer/stop', {
      body: { projector },
    }),
    pauseRenderer: (projectorId: string) => client.pauseRenderer(projectorId),
    resumeRenderer: (projectorId: string) => client.resumeRenderer(projectorId),
    getRendererStatus: (projectorId: string) => api.get<JsonRecord>(`/renderer/status/${projectorId}`),
    listRenderers: () => client.listRenderers(),
    listProjectors: () => client.listProjectors(),
    listScenes: () => client.listRendererScenes(),
    startProjector: (projectorId: string) => client.startProjector(projectorId),
    discoverAirPlayDevices: () => api.get<JsonRecord>('/renderer/airplay/discover'),
    listAirPlayDevices: () => api.get<JsonRecord>('/renderer/airplay/list'),
    getAllAirPlayDevices: () => api.get<JsonRecord>('/renderer/airplay/devices'),
  };

  const depthApi = {
    uploadDepthMap: (formData: FormData, options: UploadRequestOptions = {}) => requestUpload<JsonRecord>(api, '/depth/upload', formData, options),
    previewDepthMap: (depthId: number | string) => buildApiUrl(`/depth/preview/${depthId}`),
    segmentDepthMap: (depthId: number | string, segmentationParams: JsonRecord) => api.post<JsonRecord>(`/depth/segment/${depthId}`, { body: segmentationParams }),
    previewSegmentation: (depthId: number | string, alpha = 0.5) => buildApiUrl(`/depth/segmentation_preview/${depthId}`, { alpha }),
    exportMasks: (depthId: number | string, segmentIds: Array<number | string>, cleanMask = true, minArea = 100, kernelSize = 3) => api.post<JsonRecord>(`/depth/export_masks/${depthId}`, {
      body: {
        segment_ids: segmentIds,
        clean_mask: cleanMask,
        min_area: minArea,
        kernel_size: kernelSize,
      },
    }),
    deleteDepthMap: (depthId: number | string) => api.delete<JsonRecord>(`/depth/${depthId}`),
    getMask: (depthId: number | string, segmentId: number | string, clean = true, minArea = 100, kernelSize = 3) => buildApiUrl(`/depth/mask/${depthId}/${segmentId}`, {
      clean,
      min_area: minArea,
      kernel_size: kernelSize,
    }),
    createProjection: (config: JsonRecord) => api.post<JsonRecord>('/depth/projection/create', { body: config }),
    getProjection: (configId: number | string) => buildApiUrl(`/depth/projection/${configId}`),
    deleteProjection: (configId: number | string) => api.delete<JsonRecord>(`/depth/projection/${configId}`),
  };

  const streamingApi = {
    getStreamingStats: () => api.get<JsonRecord>('/streaming/'),
    startStreaming: (deviceId: number | string, videoPath: string) => api.post<JsonRecord>('/streaming/start', {
      body: { device_id: deviceId, video_path: videoPath },
    }),
    getSessions: () => client.listStreamingSessions(),
    getSession: (sessionId: string) => api.get<JsonRecord>(`/streaming/sessions/${sessionId}`),
    deleteSession: (sessionId: string) => client.stopStreamingSession(sessionId),
    getSessionsForDevice: (deviceName: string) => api.get<JsonRecord[]>(`/streaming/device/${deviceName}`),
    completeSession: (sessionId: string) => client.completeStreamingSession(sessionId),
    resetSession: (sessionId: string) => client.resetStreamingSession(sessionId),
    getStreamingAnalytics: () => client.getStreamingAnalytics(),
    getStreamingHealth: () => api.get<JsonRecord>('/streaming/health'),
  };

  const diagnosticsApi = {
    getServiceDiagnostics: (params: QueryRecord = {}) => api.get<JsonRecord>('/diagnostics/service', { query: params }),
    getIncidentDetail: (incidentId: string, params: QueryRecord = {}) => api.get<JsonRecord>(`/diagnostics/incidents/${incidentId}`, { query: params }),
  };

  const logsApi = {
    getLogs: (params: QueryRecord = {}) => api.get<JsonRecord>('/logs', { query: params }),
    getSources: () => api.get<JsonRecord>('/logs/sources'),
    getLevels: () => api.get<JsonRecord>('/logs/levels'),
    getStats: () => api.get<JsonRecord>('/logs/stats'),
    tailSource: (source: string, lines = 100) =>
      api.get<JsonRecord>(`/logs/tail/${encodeURIComponent(source)}`, { query: { lines } }),
    exportLogs: (format: string, params: QueryRecord = {}) =>
      api.get<Blob>('/logs/export', { query: { format, ...params }, parseAs: 'blob' }),
  };

  const settingsApi = {
    getSettings: async () => ({ ...defaultSettings }),
    updateSettings: async (settings: JsonRecord) => ({ ...defaultSettings, ...settings }),
  };

  return {
    api,
    client,
    deviceApi,
    discoveryV2Api,
    overlayApi,
    structuredLightingApi,
    videoApi,
    photoApi,
    mappingsApi,
    mediaLibraryApi,
    photoListApi,
    projectionApi,
    rendererApi,
    depthApi,
    streamingApi,
    diagnosticsApi,
    logsApi,
    settingsApi,
  };
}

const defaultServices = createServiceModules(DEFAULT_API_BASE_URL);

export const api = defaultServices.api;
export const deviceApi = defaultServices.deviceApi;
export const discoveryV2Api = defaultServices.discoveryV2Api;
export const overlayApi = defaultServices.overlayApi;
export const structuredLightingApi = defaultServices.structuredLightingApi;
export const videoApi = defaultServices.videoApi;
export const photoApi = defaultServices.photoApi;
export const mappingsApi = defaultServices.mappingsApi;
export const mediaLibraryApi = defaultServices.mediaLibraryApi;
export const photoListApi = defaultServices.photoListApi;
export const projectionApi = defaultServices.projectionApi;
export const rendererApi = defaultServices.rendererApi;
export const depthApi = defaultServices.depthApi;
export const streamingApi = defaultServices.streamingApi;
export const diagnosticsApi = defaultServices.diagnosticsApi;
export const logsApi = defaultServices.logsApi;
export const settingsApi = defaultServices.settingsApi;
export const serviceModules = defaultServices;
