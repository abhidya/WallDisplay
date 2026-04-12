import { NanoDlnaApiClient, normalizeApiBaseUrl } from '../services/api.ts';
import type { QueryRecord } from '../services/httpClient.ts';
import type {
  ActionHistoryEntry,
  DeviceActionResponse,
  DeviceControlMode,
  DeviceDetail,
  DeviceSummary,
  DiscoveryBackendSummary,
  DiscoveryCapabilities,
  DiscoveryStatus,
  DiscoverySystemStatus,
  HealthResponse,
  JsonRecord,
  LocalCapabilitySummary,
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
  DeferredFeatureSummary,
} from '../types/api.ts';
import {
  classifyDiscoveryService,
  DEFAULT_DISCOVERY_SERVICE_TYPES,
  discoverNativeServices,
} from './nativeDiscovery.ts';
import {
  appendActionHistory,
  type AppMode,
  DEFAULT_REMOTE_API_BASE_URL,
  loadLocalControlPlaneState,
  makeDeferredResult,
  summarizeDevice,
  updateLocalControlPlaneState,
} from './localState.ts';

export interface ControlPlaneClient {
  readonly mode: AppMode;
  readonly apiBaseUrl: string;
  readonly rootBaseUrl: string;
  getHealth(): Promise<HealthResponse>;
  listDevices(): Promise<DeviceSummary[]>;
  getDevice(deviceId: number | string): Promise<DeviceDetail>;
  getDiscoveryStatus(): Promise<DiscoveryStatus>;
  getUnifiedDiscoveryStatus(): Promise<DiscoverySystemStatus>;
  getUnifiedDiscoveryCapabilities(): Promise<DiscoveryCapabilities>;
  listDiscoveryBackends(): Promise<DiscoveryBackendSummary[]>;
  enableDiscoveryBackend(backendName: string): Promise<DeviceActionResponse>;
  disableDiscoveryBackend(backendName: string): Promise<DeviceActionResponse>;
  pauseDiscovery(): Promise<DeviceActionResponse>;
  resumeDiscovery(): Promise<DeviceActionResponse>;
  discoverDevices(timeoutSeconds?: number): Promise<JsonRecord>;
  getDeviceControlMode(deviceId: number | string): Promise<DeviceControlMode>;
  enableAutoMode(deviceId: number | string): Promise<DeviceActionResponse>;
  enableManualMode(
    deviceId: number | string,
    options?: { reason?: string; expiresIn?: number },
  ): Promise<DeviceActionResponse>;
  pauseDevicePlayback(deviceId: number | string): Promise<DeviceActionResponse>;
  stopDevicePlayback(deviceId: number | string): Promise<DeviceActionResponse>;
  playVideoOnDevice(
    deviceId: number | string,
    videoId: number | string,
    options?: { loop?: boolean; syncOverlays?: boolean },
  ): Promise<DeviceActionResponse>;
  listVideos(): Promise<VideoSummary[]>;
  listPhotos(): Promise<PhotoSummary[]>;
  listMediaDirectories(): Promise<MediaDirectorySummary[]>;
  scanMediaDirectory(directoryId: number | string): Promise<JsonRecord>;
  listMediaLists(): Promise<MediaListSummary[]>;
  listMediaChannels(): Promise<MediaChannelSummary[]>;
  advanceMediaChannel(channelId: number | string): Promise<MediaChannelSummary>;
  listPhotoLists(): Promise<JsonRecord[]>;
  createMediaList(payload: JsonRecord): Promise<JsonRecord>;
  createMediaChannel(payload: JsonRecord): Promise<JsonRecord>;
  deleteMediaList(listId: number | string): Promise<JsonRecord>;
  deleteMediaChannel(channelId: number | string): Promise<JsonRecord>;
  createVideo(payload: JsonRecord): Promise<JsonRecord>;
  deleteVideo(videoId: number | string): Promise<JsonRecord>;
  uploadVideo(formData: FormData): Promise<JsonRecord>;
  createPhoto(payload: JsonRecord): Promise<JsonRecord>;
  deletePhoto(photoId: number | string): Promise<JsonRecord>;
  uploadPhoto(formData: FormData): Promise<JsonRecord>;
  createMediaDirectory(payload: JsonRecord): Promise<JsonRecord>;
  deleteMediaDirectory(directoryId: number | string): Promise<JsonRecord>;
  createPhotoList(payload: JsonRecord): Promise<JsonRecord>;
  deletePhotoList(listId: number | string): Promise<JsonRecord>;
  getGlobalApiConfigs(): Promise<JsonRecord>;
  updateGlobalApiConfigs(payload: JsonRecord): Promise<JsonRecord>;
  getProjectorRedirectConfig(): Promise<JsonRecord>;
  updateProjectorRedirectConfig(payload: JsonRecord): Promise<JsonRecord>;
  getRecentProjectorRedirectRequests(limit?: number): Promise<JsonRecord[]>;
  getServiceDiagnostics(params?: QueryRecord): Promise<JsonRecord>;
  getIncidentDetail(incidentId: string, params?: QueryRecord): Promise<JsonRecord>;
  getLogs(params?: QueryRecord): Promise<JsonRecord>;
  getLogSources(): Promise<JsonRecord>;
  getLogLevels(): Promise<JsonRecord>;
  getLogStats(): Promise<JsonRecord>;
  tailLogSource(source: string, lines?: number): Promise<JsonRecord>;
  exportLogs(format: string, params?: QueryRecord): Promise<Blob>;
  getStreamingAnalytics(): Promise<StreamingAnalytics>;
  listStreamingSessions(): Promise<StreamingSessionSummary[]>;
  getStreamingHealth(): Promise<StreamingHealthResponse>;
  completeStreamingSession(sessionId: string): Promise<JsonRecord>;
  resetStreamingSession(sessionId: string): Promise<JsonRecord>;
  stopStreamingSession(sessionId: string): Promise<JsonRecord>;
  listOverlayCastSessions(): Promise<OverlayCastSessionSummary[]>;
  stopOverlayCastSession(sessionId: string): Promise<JsonRecord>;
  listRenderers(): Promise<RendererInstanceSummary[]>;
  listProjectors(): Promise<RendererProjectorSummary[]>;
  getRendererStatus(projectorId: string): Promise<JsonRecord>;
  discoverAirPlayDevices(): Promise<JsonRecord>;
  listAirPlayDevices(): Promise<JsonRecord>;
  getAllAirPlayDevices(): Promise<JsonRecord>;
  listOverlayConfigs(): Promise<OverlayConfigSummary[]>;
  createOverlayConfig(payload: JsonRecord): Promise<JsonRecord>;
  deleteOverlayConfig(configId: number | string): Promise<JsonRecord>;
  getOverlayBrightness(): Promise<JsonRecord>;
  setOverlayBrightness(brightness: number): Promise<JsonRecord>;
  exportOverlayMp4(payload: JsonRecord): Promise<Blob>;
  startOverlayCast(payload: JsonRecord): Promise<JsonRecord>;
  listRendererScenes(): Promise<RendererSceneSummary[]>;
  startRenderer(projector: string, scene: string): Promise<RendererActionResponse>;
  startProjector(projectorId: string): Promise<RendererActionResponse>;
  pauseRenderer(projectorId: string): Promise<RendererActionResponse>;
  resumeRenderer(projectorId: string): Promise<RendererActionResponse>;
  stopRenderer(projectorId: string): Promise<RendererActionResponse>;
  getOverlayStatus(): Promise<OverlayStatusResponse>;
  triggerOverlaySync(
    options?: { triggeredBy?: string; videoName?: string },
  ): Promise<OverlaySyncResponse>;
  listMappingScenes(): Promise<MappingSceneSummary[]>;
  listSceneRanks(): Promise<SceneRankSummary[]>;
  listSceneControlPresets(): Promise<SceneControlPresetSummary[]>;
  listProjectionConfigs(): Promise<ProjectionConfigSummary[]>;
  launchProjectionConfig(configId: number | string): Promise<ProjectionSessionSummary>;
  getProjectionSession(sessionId: string): Promise<ProjectionSessionSummary>;
  listProjectionAnimations(): Promise<JsonRecord>;
  listProjectionAnimationLists(): Promise<JsonRecord[]>;
  getProjectionAnimationList(id: number | string): Promise<JsonRecord>;
  createProjectionAnimationList(data: JsonRecord): Promise<JsonRecord>;
  updateProjectionAnimationList(id: number | string, data: JsonRecord): Promise<JsonRecord>;
  deleteProjectionAnimationList(id: number | string): Promise<JsonRecord>;
  getStructuredLightingCapabilities(): Promise<JsonRecord>;
  getStructuredLightingStatus(): Promise<JsonRecord>;
  listStructuredLightingSessions(): Promise<JsonRecord[]>;
  createStructuredLightingSession(payload: JsonRecord): Promise<JsonRecord>;
  deleteStructuredLightingSession(sessionId: string): Promise<JsonRecord>;
  getStructuredLightingRuntime(sessionId: string): Promise<JsonRecord>;
  listStructuredLightingCaptures(sessionId: string): Promise<JsonRecord[]>;
  startStructuredLightingSession(sessionId: string): Promise<JsonRecord>;
  uploadDepthMap(formData: FormData): Promise<JsonRecord>;
  getDepthPreviewUrl(depthId: number | string): string;
  segmentDepthMap(depthId: number | string, segmentationParams: JsonRecord): Promise<JsonRecord>;
  getDepthSegmentationPreviewUrl(depthId: number | string, alpha?: number): string;
  exportDepthMasks(
    depthId: number | string,
    segmentIds: Array<number | string>,
    cleanMask?: boolean,
    minArea?: number,
    kernelSize?: number,
  ): Promise<JsonRecord>;
  deleteDepthMap(depthId: number | string): Promise<JsonRecord>;
  getDepthMaskUrl(
    depthId: number | string,
    segmentId: number | string,
    clean?: boolean,
    minArea?: number,
    kernelSize?: number,
  ): string;
  createDepthProjection(config: JsonRecord): Promise<JsonRecord>;
  getDepthProjectionUrl(configId: number | string): string;
  deleteDepthProjection(configId: number | string): Promise<JsonRecord>;
  listActionHistory(): Promise<ActionHistoryEntry[]>;
  listCapabilities(): Promise<LocalCapabilitySummary[]>;
  listDeferredFeatures(): Promise<DeferredFeatureSummary[]>;

  duplicateOverlayConfig(configId: number | string): Promise<OverlayConfigSummary>;
  createOverlayStream(payload: JsonRecord): Promise<JsonRecord>;
  getOverlayWindowInit(projectorId?: string): Promise<JsonRecord>;
  getOverlayWindowRefreshState(projectorId?: string): Promise<JsonRecord>;
  getOverlayWidgetData(projectorId?: string): Promise<JsonRecord>;
  heartbeatProjectorClient(payload: JsonRecord): Promise<JsonRecord>;
  getOverlayPlaybackSync(projectorId?: string): Promise<JsonRecord>;
  getBrightnessStatus(): Promise<JsonRecord>;
  getOverlayEventsUrl(): string;
  createProjectionSession(payload: JsonRecord): Promise<ProjectionSessionSummary>;
  deleteProjectionSession(sessionId: string): Promise<JsonRecord>;
  uploadProjectionMask(formData: FormData): Promise<JsonRecord>;
  getProjectionMask(maskId: string): Promise<JsonRecord>;
  getProjectionMaskImageUrl(sessionId: string): string;
  importCodepenAnimation(payload: JsonRecord): Promise<JsonRecord>;
  startStructuredLightingWorker(payload: JsonRecord): Promise<JsonRecord>;
  stopStructuredLightingWorker(): Promise<JsonRecord>;
  confirmStructuredLightingWorkerReady(workerId: string): Promise<JsonRecord>;
  decodeStructuredLightingSession(sessionId: string, payload?: JsonRecord): Promise<JsonRecord>;
  runStructuredLightingPreviewTuning(sessionId: string, payload?: JsonRecord): Promise<JsonRecord>;
  getStructuredLightingPreviewTuning(sessionId: string): Promise<JsonRecord>;
  runStructuredLightingTuningSearch(sessionId: string, payload?: JsonRecord): Promise<JsonRecord>;
  getStructuredLightingTuningSearch(sessionId: string): Promise<JsonRecord>;
  getStructuredLightingCalibration(sessionId: string): Promise<JsonRecord>;
  getStructuredLightingArtifactReview(sessionId: string): Promise<JsonRecord>;
  updateStructuredLightingReview(sessionId: string, payload: JsonRecord): Promise<JsonRecord>;
  publishStructuredLightingMappingScene(sessionId: string, payload?: JsonRecord): Promise<JsonRecord>;
  getStructuredLightingStepImageUrl(sessionId: string, stepIndex: number | string): string;
  getStructuredLightingCaptureImageUrl(sessionId: string, stepIndex: number | string): string;
  getStructuredLightingArtifactPreviewUrl(sessionId: string, previewId: string): string;
  getStructuredLightingPreviewTuningPreviewUrl(sessionId: string, candidateId: string, previewName: string): string;
  getStructuredLightingTuningSearchPreviewUrl(sessionId: string, candidateId: string, previewName: string): string;
  getStructuredLightingExportUrl(sessionId: string): string;
  uploadStructuredLightingCapture(sessionId: string, formData: FormData): Promise<JsonRecord>;
}

class RemoteControlPlaneAdapter implements ControlPlaneClient {
  readonly mode: AppMode = 'remote';
  readonly apiBaseUrl: string;
  readonly rootBaseUrl: string;
  private readonly client: NanoDlnaApiClient;

  constructor(apiBaseUrl: string) {
    this.apiBaseUrl = normalizeApiBaseUrl(apiBaseUrl || DEFAULT_REMOTE_API_BASE_URL);
    this.client = new NanoDlnaApiClient(this.apiBaseUrl);
    this.rootBaseUrl = this.client.rootBaseUrl;
  }

  getHealth() { return this.client.getHealth(); }
  listDevices() { return this.client.listDevices(); }
  getDevice(deviceId: number | string) { return this.client.getDevice(deviceId); }
  getDiscoveryStatus() { return this.client.getDiscoveryStatus(); }
  getUnifiedDiscoveryStatus() { return this.client.getUnifiedDiscoveryStatus(); }
  getUnifiedDiscoveryCapabilities() { return this.client.getUnifiedDiscoveryCapabilities(); }
  listDiscoveryBackends() { return this.client.listDiscoveryBackends(); }
  enableDiscoveryBackend(backendName: string) { return this.client.enableDiscoveryBackend(backendName); }
  disableDiscoveryBackend(backendName: string) { return this.client.disableDiscoveryBackend(backendName); }
  pauseDiscovery() { return this.client.pauseDiscovery(); }
  resumeDiscovery() { return this.client.resumeDiscovery(); }
  discoverDevices(timeoutSeconds = 5) { return this.client.discoverDevices(timeoutSeconds); }
  getDeviceControlMode(deviceId: number | string) { return this.client.getDeviceControlMode(deviceId); }
  enableAutoMode(deviceId: number | string) { return this.client.enableAutoMode(deviceId); }
  enableManualMode(deviceId: number | string, options?: { reason?: string; expiresIn?: number }) { return this.client.enableManualMode(deviceId, options); }
  pauseDevicePlayback(deviceId: number | string) { return this.client.pauseDevicePlayback(deviceId); }
  stopDevicePlayback(deviceId: number | string) { return this.client.stopDevicePlayback(deviceId); }
  playVideoOnDevice(deviceId: number | string, videoId: number | string, options?: { loop?: boolean; syncOverlays?: boolean }) { return this.client.playVideoOnDevice(deviceId, videoId, options); }
  listVideos() { return this.client.listVideos(); }
  listPhotos() { return this.client.listPhotos(); }
  listMediaDirectories() { return this.client.listMediaDirectories(); }
  scanMediaDirectory(directoryId: number | string) { return this.client.scanMediaDirectory(directoryId); }
  listMediaLists() { return this.client.listMediaLists(); }
  listMediaChannels() { return this.client.listMediaChannels(); }
  advanceMediaChannel(channelId: number | string) { return this.client.advanceMediaChannel(channelId); }
  listPhotoLists() { return this.client.listPhotoLists(); }
  createMediaList(payload: JsonRecord) { return this.client.createMediaList(payload); }
  createMediaChannel(payload: JsonRecord) { return this.client.createMediaChannel(payload); }
  deleteMediaList(listId: number | string) { return this.client.deleteMediaList(listId); }
  deleteMediaChannel(channelId: number | string) { return this.client.deleteMediaChannel(channelId); }
  createVideo(payload: JsonRecord) { return this.client.createVideo(payload); }
  deleteVideo(videoId: number | string) { return this.client.deleteVideo(videoId); }
  uploadVideo(formData: FormData) { return this.client.uploadVideo(formData); }
  createPhoto(payload: JsonRecord) { return this.client.createPhoto(payload); }
  deletePhoto(photoId: number | string) { return this.client.deletePhoto(photoId); }
  uploadPhoto(formData: FormData) { return this.client.uploadPhoto(formData); }
  createMediaDirectory(payload: JsonRecord) { return this.client.createMediaDirectory(payload); }
  deleteMediaDirectory(directoryId: number | string) { return this.client.deleteMediaDirectory(directoryId); }
  createPhotoList(payload: JsonRecord) { return this.client.createPhotoList(payload); }
  deletePhotoList(listId: number | string) { return this.client.deletePhotoList(listId); }
  getGlobalApiConfigs() { return this.client.getGlobalApiConfigs(); }
  updateGlobalApiConfigs(payload: JsonRecord) { return this.client.updateGlobalApiConfigs(payload); }
  getProjectorRedirectConfig() { return this.client.getProjectorRedirectConfig(); }
  updateProjectorRedirectConfig(payload: JsonRecord) { return this.client.updateProjectorRedirectConfig(payload); }
  getRecentProjectorRedirectRequests(limit?: number) { return this.client.getRecentProjectorRedirectRequests(limit); }
  getServiceDiagnostics(params?: QueryRecord) { return this.client.getServiceDiagnostics(params); }
  getIncidentDetail(incidentId: string, params?: QueryRecord) { return this.client.getIncidentDetail(incidentId, params); }
  getLogs(params?: QueryRecord) { return this.client.getLogs(params); }
  getLogSources() { return this.client.getLogSources(); }
  getLogLevels() { return this.client.getLogLevels(); }
  getLogStats() { return this.client.getLogStats(); }
  tailLogSource(source: string, lines?: number) { return this.client.tailLogSource(source, lines); }
  exportLogs(format: string, params?: QueryRecord) { return this.client.exportLogs(format, params); }
  getStreamingAnalytics() { return this.client.getStreamingAnalytics(); }
  listStreamingSessions() { return this.client.listStreamingSessions(); }
  getStreamingHealth() { return this.client.getStreamingHealth(); }
  completeStreamingSession(sessionId: string) { return this.client.completeStreamingSession(sessionId); }
  resetStreamingSession(sessionId: string) { return this.client.resetStreamingSession(sessionId); }
  stopStreamingSession(sessionId: string) { return this.client.stopStreamingSession(sessionId); }
  listOverlayCastSessions() { return this.client.listOverlayCastSessions(); }
  stopOverlayCastSession(sessionId: string) { return this.client.stopOverlayCastSession(sessionId); }
  listRenderers() { return this.client.listRenderers(); }
  listProjectors() { return this.client.listProjectors(); }
  getRendererStatus(projectorId: string) { return this.client.getRendererStatus(projectorId); }
  discoverAirPlayDevices() { return this.client.discoverAirPlayDevices(); }
  listAirPlayDevices() { return this.client.listAirPlayDevices(); }
  getAllAirPlayDevices() { return this.client.getAllAirPlayDevices(); }
  listOverlayConfigs() { return this.client.listOverlayConfigs(); }
  createOverlayConfig(payload: JsonRecord) { return this.client.createOverlayConfig(payload); }
  deleteOverlayConfig(configId: number | string) { return this.client.deleteOverlayConfig(configId); }
  getOverlayBrightness() { return this.client.getOverlayBrightness(); }
  setOverlayBrightness(brightness: number) { return this.client.setOverlayBrightness(brightness); }
  exportOverlayMp4(payload: JsonRecord) { return this.client.exportOverlayMp4(payload); }
  startOverlayCast(payload: JsonRecord) { return this.client.startOverlayCast(payload); }
  listRendererScenes() { return this.client.listRendererScenes(); }
  startRenderer(projector: string, scene: string) { return this.client.startRenderer(projector, scene); }
  startProjector(projectorId: string) { return this.client.startProjector(projectorId); }
  pauseRenderer(projectorId: string) { return this.client.pauseRenderer(projectorId); }
  resumeRenderer(projectorId: string) { return this.client.resumeRenderer(projectorId); }
  stopRenderer(projectorId: string) { return this.client.stopRenderer(projectorId); }
  getOverlayStatus() { return this.client.getOverlayStatus(); }
  triggerOverlaySync(options?: { triggeredBy?: string; videoName?: string }) { return this.client.triggerOverlaySync(options); }
  listMappingScenes() { return this.client.listMappingScenes(); }
  listSceneRanks() { return this.client.listSceneRanks(); }
  listSceneControlPresets() { return this.client.listSceneControlPresets(); }
  listProjectionConfigs() { return this.client.listProjectionConfigs(); }
  launchProjectionConfig(configId: number | string) { return this.client.launchProjectionConfig(configId); }
  getProjectionSession(sessionId: string) { return this.client.getProjectionSession(sessionId); }
  listProjectionAnimations() { return this.client.listProjectionAnimations(); }
  listProjectionAnimationLists() { return this.client.listProjectionAnimationLists(); }
  getProjectionAnimationList(id: number | string) { return this.client.getProjectionAnimationList(id); }
  createProjectionAnimationList(data: JsonRecord) { return this.client.createProjectionAnimationList(data); }
  updateProjectionAnimationList(id: number | string, data: JsonRecord) {
    return this.client.updateProjectionAnimationList(id, data);
  }
  deleteProjectionAnimationList(id: number | string) { return this.client.deleteProjectionAnimationList(id); }
  getStructuredLightingCapabilities() { return this.client.getStructuredLightingCapabilities(); }
  getStructuredLightingStatus() { return this.client.getStructuredLightingStatus(); }
  listStructuredLightingSessions() { return this.client.listStructuredLightingSessions(); }
  createStructuredLightingSession(payload: JsonRecord) {
    return this.client.createStructuredLightingSession(payload);
  }
  deleteStructuredLightingSession(sessionId: string) {
    return this.client.deleteStructuredLightingSession(sessionId);
  }
  getStructuredLightingRuntime(sessionId: string) {
    return this.client.getStructuredLightingRuntime(sessionId);
  }
  listStructuredLightingCaptures(sessionId: string) {
    return this.client.listStructuredLightingCaptures(sessionId);
  }
  startStructuredLightingSession(sessionId: string) {
    return this.client.startStructuredLightingSession(sessionId);
  }
  uploadDepthMap(formData: FormData) { return this.client.uploadDepthMap(formData); }
  getDepthPreviewUrl(depthId: number | string) { return this.client.getDepthPreviewUrl(depthId); }
  segmentDepthMap(depthId: number | string, segmentationParams: JsonRecord) {
    return this.client.segmentDepthMap(depthId, segmentationParams);
  }
  getDepthSegmentationPreviewUrl(depthId: number | string, alpha?: number) {
    return this.client.getDepthSegmentationPreviewUrl(depthId, alpha);
  }
  exportDepthMasks(
    depthId: number | string,
    segmentIds: Array<number | string>,
    cleanMask?: boolean,
    minArea?: number,
    kernelSize?: number,
  ) {
    return this.client.exportDepthMasks(depthId, segmentIds, cleanMask, minArea, kernelSize);
  }
  deleteDepthMap(depthId: number | string) { return this.client.deleteDepthMap(depthId); }
  getDepthMaskUrl(
    depthId: number | string,
    segmentId: number | string,
    clean?: boolean,
    minArea?: number,
    kernelSize?: number,
  ) {
    return this.client.getDepthMaskUrl(depthId, segmentId, clean, minArea, kernelSize);
  }
  createDepthProjection(config: JsonRecord) { return this.client.createDepthProjection(config); }
  getDepthProjectionUrl(configId: number | string) { return this.client.getDepthProjectionUrl(configId); }
  deleteDepthProjection(configId: number | string) { return this.client.deleteDepthProjection(configId); }
  async listActionHistory(): Promise<ActionHistoryEntry[]> {
    return [
      {
        id: 'remote-adapter-active',
        title: 'Remote adapter active',
        detail: `Using ${this.apiBaseUrl} as the shared control plane.`,
        created_at: new Date().toISOString(),
        status: 'info',
        mode: 'remote',
      },
    ];
  }
  async listCapabilities(): Promise<LocalCapabilitySummary[]> {
    return [
      {
        key: 'remote-adapter',
        label: 'Remote adapter',
        status: 'ready',
        detail: 'The mobile app is using the existing FastAPI control plane through the adapter.',
      },
      {
        key: 'local-mode',
        label: 'Local mode available',
        status: 'ready',
        detail: 'Switch to local mode from Settings to run without a backend.',
      },
    ];
  }
  async listDeferredFeatures(): Promise<DeferredFeatureSummary[]> {
    return [];
  }

  duplicateOverlayConfig(configId: number | string) { return this.client.duplicateOverlayConfig(configId); }
  createOverlayStream(payload: JsonRecord) { return this.client.createOverlayStream(payload); }
  getOverlayWindowInit(projectorId?: string) { return this.client.getOverlayWindowInit(projectorId); }
  getOverlayWindowRefreshState(projectorId?: string) { return this.client.getOverlayWindowRefreshState(projectorId); }
  getOverlayWidgetData(projectorId?: string) { return this.client.getOverlayWidgetData(projectorId); }
  heartbeatProjectorClient(payload: JsonRecord) { return this.client.heartbeatProjectorClient(payload); }
  getOverlayPlaybackSync(projectorId?: string) { return this.client.getOverlayPlaybackSync(projectorId); }
  getBrightnessStatus() { return this.client.getBrightnessStatus(); }
  getOverlayEventsUrl() { return this.client.getOverlayEventsUrl(); }
  createProjectionSession(payload: JsonRecord) { return this.client.createProjectionSession(payload); }
  deleteProjectionSession(sessionId: string) { return this.client.deleteProjectionSession(sessionId); }
  uploadProjectionMask(formData: FormData) { return this.client.uploadProjectionMask(formData); }
  getProjectionMask(maskId: string) { return this.client.getProjectionMask(maskId); }
  getProjectionMaskImageUrl(sessionId: string) { return this.client.getProjectionMaskImageUrl(sessionId); }
  importCodepenAnimation(payload: JsonRecord) { return this.client.importCodepenAnimation(payload); }
  startStructuredLightingWorker(payload: JsonRecord) { return this.client.startStructuredLightingWorker(payload); }
  stopStructuredLightingWorker() { return this.client.stopStructuredLightingWorker(); }
  confirmStructuredLightingWorkerReady(workerId: string) { return this.client.confirmStructuredLightingWorkerReady(workerId); }
  decodeStructuredLightingSession(sessionId: string, payload?: JsonRecord) { return this.client.decodeStructuredLightingSession(sessionId, payload); }
  runStructuredLightingPreviewTuning(sessionId: string, payload?: JsonRecord) { return this.client.runStructuredLightingPreviewTuning(sessionId, payload); }
  getStructuredLightingPreviewTuning(sessionId: string) { return this.client.getStructuredLightingPreviewTuning(sessionId); }
  runStructuredLightingTuningSearch(sessionId: string, payload?: JsonRecord) { return this.client.runStructuredLightingTuningSearch(sessionId, payload); }
  getStructuredLightingTuningSearch(sessionId: string) { return this.client.getStructuredLightingTuningSearch(sessionId); }
  getStructuredLightingCalibration(sessionId: string) { return this.client.getStructuredLightingCalibration(sessionId); }
  getStructuredLightingArtifactReview(sessionId: string) { return this.client.getStructuredLightingArtifactReview(sessionId); }
  updateStructuredLightingReview(sessionId: string, payload: JsonRecord) { return this.client.updateStructuredLightingReview(sessionId, payload); }
  publishStructuredLightingMappingScene(sessionId: string, payload?: JsonRecord) { return this.client.publishStructuredLightingMappingScene(sessionId, payload); }
  getStructuredLightingStepImageUrl(sessionId: string, stepIndex: number | string) { return this.client.getStructuredLightingStepImageUrl(sessionId, stepIndex); }
  getStructuredLightingCaptureImageUrl(sessionId: string, stepIndex: number | string) { return this.client.getStructuredLightingCaptureImageUrl(sessionId, stepIndex); }
  getStructuredLightingArtifactPreviewUrl(sessionId: string, previewId: string) { return this.client.getStructuredLightingArtifactPreviewUrl(sessionId, previewId); }
  getStructuredLightingPreviewTuningPreviewUrl(sessionId: string, candidateId: string, previewName: string) { return this.client.getStructuredLightingPreviewTuningPreviewUrl(sessionId, candidateId, previewName); }
  getStructuredLightingTuningSearchPreviewUrl(sessionId: string, candidateId: string, previewName: string) { return this.client.getStructuredLightingTuningSearchPreviewUrl(sessionId, candidateId, previewName); }
  getStructuredLightingExportUrl(sessionId: string) { return this.client.getStructuredLightingExportUrl(sessionId); }
  uploadStructuredLightingCapture(sessionId: string, formData: FormData) { return this.client.uploadStructuredLightingCapture(sessionId, formData); }
}

class LocalControlPlaneClient implements ControlPlaneClient {
  readonly mode: AppMode = 'local';
  readonly apiBaseUrl = 'local://control-plane';
  readonly rootBaseUrl = 'local://control-plane';

  private buildLocalFeatureUrl(path: string, query?: QueryRecord): string {
    const search = new URLSearchParams();

    for (const [key, rawValue] of Object.entries(query ?? {})) {
      if (rawValue === undefined || rawValue === null) {
        continue;
      }

      const values = Array.isArray(rawValue) ? rawValue : [rawValue];
      for (const value of values) {
        search.append(key, String(value));
      }
    }

    const queryString = search.toString();
    return `${this.rootBaseUrl}${path}${queryString ? `?${queryString}` : ''}`;
  }

  private async recordDeferredFeature(title: string, detail: string): Promise<void> {
    await updateLocalControlPlaneState((state) =>
      appendActionHistory(state, {
        title,
        detail,
        status: 'deferred',
        mode: 'local',
      }),
    );
  }

  private async getLocalWritableDevice(deviceId: number | string) {
    const state = await loadLocalControlPlaneState();
    const device = state.devices.find((entry) => String(entry.id) === String(deviceId)) ?? null;
    const supportsManualActions = Boolean(device?.config?.supports_manual_actions);
    return {
      device,
      supportsManualActions,
    };
  }

  private async unsupportedTransportResponse(
    deviceId: number | string,
    actionLabel: string,
  ): Promise<DeviceActionResponse> {
    const { device } = await this.getLocalWritableDevice(deviceId);
    const deviceLabel =
      (typeof device?.friendly_name === 'string' && device.friendly_name) ||
      (typeof device?.device_name === 'string' && device.device_name) ||
      (typeof device?.name === 'string' && device.name) ||
      String(deviceId);

    await updateLocalControlPlaneState((state) =>
      appendActionHistory(state, {
        title: `${actionLabel} deferred`,
        detail: `${deviceLabel} was discovered successfully, but protocol-specific transport control is not wired for this target yet.`,
        status: 'deferred',
        mode: 'local',
      }),
    );

    return {
      success: false,
      status: 'deferred',
      message: `${deviceLabel} is discovery-only until protocol-specific sender transport is implemented.`,
    };
  }

  async getHealth(): Promise<HealthResponse> {
    const state = await loadLocalControlPlaneState();
    return state.health;
  }

  async listDevices(): Promise<DeviceSummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.devices.map(summarizeDevice);
  }

  async getDevice(deviceId: number | string): Promise<DeviceDetail> {
    const state = await loadLocalControlPlaneState();
    return state.devices.find((device) => String(device.id) === String(deviceId)) ?? {
      id: deviceId,
      friendly_name: 'Unknown local device',
      status: 'missing',
      derived_status: 'missing',
      config: {
        reason: 'No matching local device profile was found.',
      },
    };
  }

  async getDiscoveryStatus(): Promise<DiscoveryStatus> {
    const state = await loadLocalControlPlaneState();
    return state.discoveryStatus;
  }

  async getUnifiedDiscoveryStatus(): Promise<DiscoverySystemStatus> {
    const state = await loadLocalControlPlaneState();
    return {
      ...state.unifiedDiscoveryStatus,
      total_devices: state.devices.length,
      active_sessions: state.sessions.length,
      online_devices: state.devices.filter((device) => device.status !== 'profile-only').length,
    };
  }

  async getUnifiedDiscoveryCapabilities(): Promise<DiscoveryCapabilities> {
    const state = await loadLocalControlPlaneState();
    return state.discoveryCapabilities;
  }

  async listDiscoveryBackends(): Promise<DiscoveryBackendSummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.discoveryBackends;
  }

  async enableDiscoveryBackend(backendName: string): Promise<DeviceActionResponse> {
    await updateLocalControlPlaneState((state) => {
      state.discoveryBackends = state.discoveryBackends.map((backend) =>
        backend.name === backendName ? { ...backend, enabled: true, active: true, healthy: true } : backend,
      );
      state.unifiedDiscoveryStatus.discovery_running = true;
      return appendActionHistory(state, {
        title: 'Enabled discovery backend',
        detail: `${backendName} is enabled in local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return { success: true, message: `${backendName} enabled for local mode.` };
  }

  async disableDiscoveryBackend(backendName: string): Promise<DeviceActionResponse> {
    await updateLocalControlPlaneState((state) => {
      state.discoveryBackends = state.discoveryBackends.map((backend) =>
        backend.name === backendName ? { ...backend, enabled: false, active: false } : backend,
      );
      return appendActionHistory(state, {
        title: 'Disabled discovery backend',
        detail: `${backendName} is disabled in local mode.`,
        status: 'info',
        mode: 'local',
      });
    });
    return { success: true, message: `${backendName} disabled.` };
  }

  async pauseDiscovery(): Promise<DeviceActionResponse> {
    await updateLocalControlPlaneState((state) => {
      state.discoveryStatus.paused = true;
      state.discoveryStatus.running = false;
      state.unifiedDiscoveryStatus.discovery_running = false;
      return appendActionHistory(state, {
        title: 'Paused local discovery',
        detail: 'Discovery loop paused locally.',
        status: 'info',
        mode: 'local',
      });
    });
    return { success: true, message: 'Local discovery paused.' };
  }

  async resumeDiscovery(): Promise<DeviceActionResponse> {
    await updateLocalControlPlaneState((state) => {
      state.discoveryStatus.paused = false;
      state.discoveryStatus.running = true;
      state.unifiedDiscoveryStatus.discovery_running = true;
      return appendActionHistory(state, {
        title: 'Resumed local discovery',
        detail: 'Discovery loop resumed locally.',
        status: 'ok',
        mode: 'local',
      });
    });
    return { success: true, message: 'Local discovery resumed.' };
  }

  async discoverDevices(timeoutSeconds = 5): Promise<JsonRecord> {
    const nativeDiscovery = await discoverNativeServices({
      serviceTypes: [...DEFAULT_DISCOVERY_SERVICE_TYPES],
      timeoutMs: Math.max(1500, timeoutSeconds * 1000),
    });

    const state = await updateLocalControlPlaneState((draft) => {
      const discoveredDevices = nativeDiscovery.services.map((service) => ({
        id: `native-${service.id}`,
        friendly_name: service.name,
        device_name: service.name,
        type: classifyDiscoveryService(service),
        manufacturer: 'Bonjour/mDNS',
        location: service.hostName ?? 'local network',
        status: 'discovered',
        derived_status: 'native discovery',
        playback_state: 'idle',
        is_playing: false,
        current_media_title: 'Ready',
        action_url: `local://device/native-${service.id}`,
        hostname: service.hostName,
        config: {
          transport: 'native-discovery',
          supports_manual_actions: false,
          service_type: service.serviceType,
          domain: service.domain,
          port: service.port,
          addresses: service.addresses ?? [],
        },
        control_mode: {
          mode: 'native-discovery',
          reason: 'Resolved from the on-device Bonjour/mDNS discovery module.',
          expires_at: null,
        },
      }));

      const manualDevices = draft.devices.filter(
        (device) => !String(device.id).startsWith('native-'),
      );

      draft.devices = [...discoveredDevices, ...manualDevices];
      draft.discoveryStatus.running = true;
      draft.discoveryStatus.paused = false;
      draft.unifiedDiscoveryStatus.discovery_running = true;
      draft.unifiedDiscoveryStatus.total_devices = draft.devices.length;
      draft.unifiedDiscoveryStatus.online_devices = discoveredDevices.length;
      draft.discoveryCapabilities.casting_methods = [
        ...new Set([
          ...(draft.discoveryCapabilities.casting_methods ?? []),
          ...nativeDiscovery.services.map((service) => classifyDiscoveryService(service)),
        ]),
      ];
      draft.discoveryBackends = draft.discoveryBackends.map((backend) =>
        backend.name === 'local'
          ? { ...backend, active: true, enabled: true, healthy: true, last_seen: new Date().toISOString() }
          : backend,
      );
      draft.capabilities = draft.capabilities.map((capability) =>
        capability.key === 'native-discovery'
          ? {
              ...capability,
              status: nativeDiscovery.available ? 'ready' : 'deferred',
              detail: nativeDiscovery.available
                ? nativeDiscovery.services.length > 0
                  ? `Native discovery found ${nativeDiscovery.services.length} Bonjour service${nativeDiscovery.services.length === 1 ? '' : 's'} (${nativeDiscovery.services
                      .map((service) => service.name)
                      .slice(0, 3)
                      .join(', ')}).`
                  : 'Native Bonjour discovery is wired but no matching services were found on the current network.'
                : 'Native discovery module is unavailable in this runtime; local mode is using saved/manual device profiles.',
            }
          : capability,
      );
      return appendActionHistory(draft, {
        title: 'Ran local discovery',
        detail: nativeDiscovery.available
          ? `Local discovery scanned Bonjour/mDNS services and refreshed ${draft.devices.length} device entries in ${timeoutSeconds}s budget.`
          : `Local discovery refreshed saved/manual device profiles in ${timeoutSeconds}s budget.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return {
      success: true,
      message: nativeDiscovery.available
        ? `Local discovery found ${nativeDiscovery.services.length} native service${nativeDiscovery.services.length === 1 ? '' : 's'} and refreshed ${state.devices.length} device entries.`
        : `Local discovery refreshed ${state.devices.length} device profiles.`,
      devices: state.devices.map(summarizeDevice),
      notes: nativeDiscovery.notes ?? [],
    };
  }

  async getDeviceControlMode(deviceId: number | string): Promise<DeviceControlMode> {
    const state = await loadLocalControlPlaneState();
    return (
      state.devices.find((device) => String(device.id) === String(deviceId))?.control_mode ?? {
        mode: 'local',
        reason: 'Managed by the on-device control plane.',
        expires_at: null,
      }
    );
  }

  async enableAutoMode(deviceId: number | string): Promise<DeviceActionResponse> {
    const { supportsManualActions } = await this.getLocalWritableDevice(deviceId);
    if (!supportsManualActions) {
      return this.unsupportedTransportResponse(deviceId, 'Auto mode');
    }

    await updateLocalControlPlaneState((state) => {
      state.devices = state.devices.map((device) =>
        String(device.id) === String(deviceId)
          ? { ...device, control_mode: { mode: 'auto', reason: 'Automatic local mode', expires_at: null } }
          : device,
      );
      return appendActionHistory(state, {
        title: 'Enabled auto mode',
        detail: `Device ${String(deviceId)} switched to automatic local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return { success: true, message: 'Automatic local mode enabled.' };
  }

  async enableManualMode(
    deviceId: number | string,
    options?: { reason?: string; expiresIn?: number },
  ): Promise<DeviceActionResponse> {
    const { supportsManualActions } = await this.getLocalWritableDevice(deviceId);
    if (!supportsManualActions) {
      return this.unsupportedTransportResponse(deviceId, 'Manual mode');
    }

    const expiresAt = options?.expiresIn
      ? new Date(Date.now() + options.expiresIn * 1000).toISOString()
      : null;
    await updateLocalControlPlaneState((state) => {
      state.devices = state.devices.map((device) =>
        String(device.id) === String(deviceId)
          ? {
              ...device,
              control_mode: {
                mode: 'manual',
                reason: options?.reason ?? 'local_manual',
                expires_at: expiresAt,
              },
            }
          : device,
      );
      return appendActionHistory(state, {
        title: 'Enabled manual mode',
        detail: `Device ${String(deviceId)} locked to manual mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return { success: true, message: 'Manual mode enabled locally.' };
  }

  async pauseDevicePlayback(deviceId: number | string): Promise<DeviceActionResponse> {
    const { supportsManualActions } = await this.getLocalWritableDevice(deviceId);
    if (!supportsManualActions) {
      return this.unsupportedTransportResponse(deviceId, 'Pause playback');
    }

    await updateLocalControlPlaneState((state) => {
      state.devices = state.devices.map((device) =>
        String(device.id) === String(deviceId)
          ? { ...device, playback_state: 'paused', is_playing: false }
          : device,
      );
      state.sessions = state.sessions.map((session) =>
        String(session.session_id) === `local-session-${String(deviceId)}`
          ? { ...session, status: 'paused' }
          : session,
      );
      return appendActionHistory(state, {
        title: 'Paused playback',
        detail: `Paused playback on ${String(deviceId)} via local control plane.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return { success: true, message: 'Playback paused locally.' };
  }

  async stopDevicePlayback(deviceId: number | string): Promise<DeviceActionResponse> {
    const { supportsManualActions } = await this.getLocalWritableDevice(deviceId);
    if (!supportsManualActions) {
      return this.unsupportedTransportResponse(deviceId, 'Stop playback');
    }

    await updateLocalControlPlaneState((state) => {
      state.devices = state.devices.map((device) =>
        String(device.id) === String(deviceId)
          ? {
              ...device,
              playback_state: 'stopped',
              is_playing: false,
              current_video: undefined,
              current_media_title: 'Stopped',
              playback_progress: 0,
            }
          : device,
      );
      state.sessions = state.sessions.filter(
        (session) => String(session.session_id) !== `local-session-${String(deviceId)}`,
      );
      state.analytics.active_sessions = state.sessions.length;
      state.analytics.session_count = state.sessions.length;
      return appendActionHistory(state, {
        title: 'Stopped playback',
        detail: `Stopped playback on ${String(deviceId)} in local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return { success: true, message: 'Playback stopped locally.' };
  }

  async playVideoOnDevice(
    deviceId: number | string,
    videoId: number | string,
    options?: { loop?: boolean; syncOverlays?: boolean },
  ): Promise<DeviceActionResponse> {
    const { supportsManualActions } = await this.getLocalWritableDevice(deviceId);
    if (!supportsManualActions) {
      return this.unsupportedTransportResponse(deviceId, 'Start playback');
    }

    await updateLocalControlPlaneState((state) => {
      const video = state.videos.find((item) => String(item.id) === String(videoId));
      state.devices = state.devices.map((device) =>
        String(device.id) === String(deviceId)
          ? {
              ...device,
              playback_state: 'playing',
              is_playing: true,
              current_video: String(videoId),
              current_media_title:
                (typeof video?.title === 'string' && video.title) ||
                (typeof video?.name === 'string' && video.name) ||
                `Video ${String(videoId)}`,
              playback_progress: 0,
            }
          : device,
      );
      const existingIndex = state.sessions.findIndex(
        (session) => String(session.session_id) === `local-session-${String(deviceId)}`,
      );
      const nextSession: StreamingSessionSummary = {
        session_id: `local-session-${String(deviceId)}`,
        device_name: String(deviceId),
        consumer_id: `local-consumer-${String(videoId)}`,
        stream_type: options?.syncOverlays ? 'video+overlay' : 'video',
        status: 'playing',
      };
      if (existingIndex >= 0) {
        state.sessions[existingIndex] = nextSession;
      } else {
        state.sessions.unshift(nextSession);
      }
      state.analytics.active_sessions = state.sessions.length;
      state.analytics.session_count = state.sessions.length;
      return appendActionHistory(state, {
        title: 'Started local playback',
        detail: `Started ${nextSession.stream_type} playback on ${String(deviceId)} with ${String(videoId)}.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return { success: true, message: 'Playback started via local control plane.' };
  }

  async listVideos(): Promise<VideoSummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.videos;
  }

  async listPhotos(): Promise<PhotoSummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.photos;
  }

  async listMediaDirectories(): Promise<MediaDirectorySummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.directories;
  }

  async scanMediaDirectory(directoryId: number | string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) =>
      appendActionHistory(state, {
        title: 'Scanned local directory',
        detail: `Refreshed local directory ${String(directoryId)}.`,
        status: 'ok',
        mode: 'local',
      }),
    );
    return { success: true, message: 'Local media directory scan completed.' };
  }

  async listMediaLists(): Promise<MediaListSummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.lists;
  }

  async listMediaChannels(): Promise<MediaChannelSummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.channels;
  }

  async advanceMediaChannel(channelId: number | string): Promise<MediaChannelSummary> {
    let nextChannel: MediaChannelSummary | null = null;
    await updateLocalControlPlaneState((state) => {
      state.channels = state.channels.map((channel) => {
        if (String(channel.id) !== String(channelId)) {
          return channel;
        }
        const nextIndex = ((channel.current_index ?? 0) + 1) % state.videos.length;
        nextChannel = {
          ...channel,
          current_index: nextIndex,
          current_video_id: state.videos[nextIndex]?.id ?? null,
        };
        return nextChannel;
      });
      return appendActionHistory(state, {
        title: 'Advanced local channel',
        detail: `Advanced channel ${String(channelId)}.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return nextChannel ?? {
      id: channelId,
      name: `Channel ${String(channelId)}`,
      current_video_id: null,
      current_index: 0,
    };
  }

  async listPhotoLists(): Promise<JsonRecord[]> {
    const state = await loadLocalControlPlaneState();
    return state.photoLists;
  }

  async createMediaList(payload: JsonRecord): Promise<JsonRecord> {
    let created: JsonRecord = {};
    await updateLocalControlPlaneState((state) => {
      created = {
        id: payload.id ?? `list-${state.lists.length + 1}`,
        name: payload.name ?? `Local list ${state.lists.length + 1}`,
        category: payload.category ?? 'local',
        playback_mode: payload.playback_mode ?? 'manual',
        ...payload,
      };
      state.lists = [...state.lists, created as MediaListSummary];
      return appendActionHistory(state, {
        title: 'Saved local media list',
        detail: `Saved media list ${String(created.name ?? created.id)} in local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return created;
  }

  async createMediaChannel(payload: JsonRecord): Promise<JsonRecord> {
    let created: JsonRecord = {};
    await updateLocalControlPlaneState((state) => {
      created = {
        id: payload.id ?? `channel-${state.channels.length + 1}`,
        name: payload.name ?? `Local channel ${state.channels.length + 1}`,
        media_list_id: payload.media_list_id ?? state.lists[0]?.id ?? '',
        current_video_id: payload.current_video_id ?? state.videos[0]?.id ?? null,
        current_index: payload.current_index ?? 0,
        ...payload,
      };
      state.channels = [...state.channels, created as MediaChannelSummary];
      return appendActionHistory(state, {
        title: 'Saved local media channel',
        detail: `Saved media channel ${String(created.name ?? created.id)} in local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return created;
  }

  async deleteMediaList(listId: number | string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.lists = state.lists.filter((list) => String(list.id) !== String(listId));
      state.channels = state.channels.filter(
        (channel) => String(channel.media_list_id) !== String(listId),
      );
      return appendActionHistory(state, {
        title: 'Deleted local media list',
        detail: `Deleted media list ${String(listId)} in local mode.`,
        status: 'info',
        mode: 'local',
      });
    });
    return { success: true, message: `Deleted media list ${String(listId)} locally.` };
  }

  async deleteMediaChannel(channelId: number | string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.channels = state.channels.filter((channel) => String(channel.id) !== String(channelId));
      return appendActionHistory(state, {
        title: 'Deleted local media channel',
        detail: `Deleted media channel ${String(channelId)} in local mode.`,
        status: 'info',
        mode: 'local',
      });
    });
    return { success: true, message: `Deleted media channel ${String(channelId)} locally.` };
  }

  async createVideo(payload: JsonRecord): Promise<JsonRecord> {
    let created: JsonRecord = {};
    await updateLocalControlPlaneState((state) => {
      created = {
        id: payload.id ?? `video-${state.videos.length + 1}`,
        title: payload.title ?? payload.name ?? `Local video ${state.videos.length + 1}`,
        file_path: payload.file_path ?? payload.path ?? `local://media/video-${state.videos.length + 1}.mp4`,
        ...payload,
      };
      state.videos = [...state.videos, created as VideoSummary];
      return appendActionHistory(state, {
        title: 'Saved local video',
        detail: `Saved video ${String(created.title ?? created.id)} in local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return created;
  }

  async deleteVideo(videoId: number | string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.videos = state.videos.filter((video) => String(video.id) !== String(videoId));
      state.channels = state.channels.map((channel) =>
        String(channel.current_video_id) === String(videoId)
          ? { ...channel, current_video_id: null }
          : channel,
      );
      state.devices = state.devices.map((device) =>
        String(device.current_video) === String(videoId)
          ? {
              ...device,
              current_video: undefined,
              current_media_title: 'Video removed',
              playback_state: 'stopped',
              is_playing: false,
            }
          : device,
      );
      state.sessions = state.sessions.filter(
        (session) => String(session.consumer_id) !== `local-consumer-${String(videoId)}`,
      );
      return appendActionHistory(state, {
        title: 'Deleted local video',
        detail: `Deleted video ${String(videoId)} in local mode.`,
        status: 'info',
        mode: 'local',
      });
    });
    return { success: true, message: `Deleted video ${String(videoId)} locally.` };
  }

  async uploadVideo(_formData: FormData): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) =>
      appendActionHistory(state, {
        title: 'Deferred local video upload',
        detail: 'File uploads remain remote-only until a native/mobile-safe ingest flow is approved.',
        status: 'deferred',
        mode: 'local',
      }),
    );
    return makeDeferredResult(
      'Video upload is remote-only until a native/mobile-safe ingest flow is approved.',
    );
  }

  async createPhoto(payload: JsonRecord): Promise<JsonRecord> {
    let created: JsonRecord = {};
    await updateLocalControlPlaneState((state) => {
      created = {
        id: payload.id ?? `photo-${state.photos.length + 1}`,
        name: payload.name ?? payload.file_name ?? `Local photo ${state.photos.length + 1}`,
        path: payload.path ?? `local://media/photo-${state.photos.length + 1}.png`,
        category: payload.category ?? 'reference',
        ...payload,
      };
      state.photos = [...state.photos, created as PhotoSummary];
      return appendActionHistory(state, {
        title: 'Saved local photo',
        detail: `Saved photo ${String(created.name ?? created.id)} in local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return created;
  }

  async deletePhoto(photoId: number | string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.photos = state.photos.filter((photo) => String(photo.id) !== String(photoId));
      state.photoLists = state.photoLists.map((list) => {
        const photoIds = Array.isArray(list.photo_ids)
          ? list.photo_ids.filter((entry) => String(entry) !== String(photoId))
          : list.photo_ids;
        return { ...list, photo_ids: photoIds };
      });
      return appendActionHistory(state, {
        title: 'Deleted local photo',
        detail: `Deleted photo ${String(photoId)} in local mode.`,
        status: 'info',
        mode: 'local',
      });
    });
    return { success: true, message: `Deleted photo ${String(photoId)} locally.` };
  }

  async uploadPhoto(_formData: FormData): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) =>
      appendActionHistory(state, {
        title: 'Deferred local photo upload',
        detail: 'Photo uploads remain remote-only until a native/mobile-safe ingest flow is approved.',
        status: 'deferred',
        mode: 'local',
      }),
    );
    return makeDeferredResult(
      'Photo upload is remote-only until a native/mobile-safe ingest flow is approved.',
    );
  }

  async createMediaDirectory(payload: JsonRecord): Promise<JsonRecord> {
    let created: JsonRecord = {};
    await updateLocalControlPlaneState((state) => {
      created = {
        id: payload.id ?? `dir-${state.directories.length + 1}`,
        name: payload.name ?? `Local dir ${state.directories.length + 1}`,
        path: payload.path ?? `local://media/local-dir-${state.directories.length + 1}`,
        category: payload.category ?? 'local',
        enabled: payload.enabled ?? true,
        scan_mode: payload.scan_mode ?? 'on-demand',
        ...payload,
      };
      state.directories = [...state.directories, created as MediaDirectorySummary];
      return appendActionHistory(state, {
        title: 'Saved local directory',
        detail: `Saved media directory ${String(created.name ?? created.id)} in local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return created;
  }

  async deleteMediaDirectory(directoryId: number | string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.directories = state.directories.filter(
        (directory) => String(directory.id) !== String(directoryId),
      );
      return appendActionHistory(state, {
        title: 'Deleted local directory',
        detail: `Deleted media directory ${String(directoryId)} in local mode.`,
        status: 'info',
        mode: 'local',
      });
    });
    return { success: true, message: `Deleted media directory ${String(directoryId)} locally.` };
  }

  async createPhotoList(payload: JsonRecord): Promise<JsonRecord> {
    let created: JsonRecord = {};
    await updateLocalControlPlaneState((state) => {
      created = {
        id: payload.id ?? `photo-list-${state.photoLists.length + 1}`,
        name: payload.name ?? `Local photo list ${state.photoLists.length + 1}`,
        photo_ids: Array.isArray(payload.photo_ids) ? payload.photo_ids : [],
        ...payload,
      };
      state.photoLists = [...state.photoLists, created];
      return appendActionHistory(state, {
        title: 'Saved local photo list',
        detail: `Saved photo list ${String(created.name ?? created.id)} in local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return created;
  }

  async deletePhotoList(listId: number | string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.photoLists = state.photoLists.filter((list) => String(list.id) !== String(listId));
      return appendActionHistory(state, {
        title: 'Deleted local photo list',
        detail: `Deleted photo list ${String(listId)} in local mode.`,
        status: 'info',
        mode: 'local',
      });
    });
    return { success: true, message: `Deleted photo list ${String(listId)} locally.` };
  }

  async getGlobalApiConfigs(): Promise<JsonRecord> {
    return {};
  }

  async updateGlobalApiConfigs(_payload: JsonRecord): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) =>
      appendActionHistory(state, {
        title: 'Deferred backend settings save',
        detail: 'Backend-owned global API configs remain explicit remote-only settings.',
        status: 'deferred',
        mode: 'local',
      }),
    );
    return makeDeferredResult('Global API configs remain remote-only in this slice.');
  }

  async getProjectorRedirectConfig(): Promise<JsonRecord> {
    return {
      enabled: false,
      client_ip: '',
      target_path: '',
      rules: [],
    };
  }

  async updateProjectorRedirectConfig(_payload: JsonRecord): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) =>
      appendActionHistory(state, {
        title: 'Deferred projector redirect save',
        detail: 'Projector redirect rules remain backend-owned in remote mode.',
        status: 'deferred',
        mode: 'local',
      }),
    );
    return makeDeferredResult('Projector redirect settings remain remote-only in this slice.');
  }

  async getRecentProjectorRedirectRequests(): Promise<JsonRecord[]> {
    return [];
  }

  async getServiceDiagnostics(_params?: QueryRecord): Promise<JsonRecord> {
    return {
      current_run: {
        status: 'local-only',
        uptime_seconds: 0,
      },
      recent_incidents: [],
      supervisor_events: [],
    };
  }

  async getIncidentDetail(incidentId: string, _params?: QueryRecord): Promise<JsonRecord> {
    return {
      incident: {
        incident_id: incidentId,
        status: 'local-only',
        detail: 'Incident detail is only available in remote mode.',
      },
      related_logs: [],
    };
  }

  async getLogs(_params?: QueryRecord): Promise<JsonRecord> {
    return {
      logs: [],
      total: 0,
    };
  }

  async getLogSources(): Promise<JsonRecord> {
    return {
      sources: [],
    };
  }

  async getLogLevels(): Promise<JsonRecord> {
    return {
      levels: [],
    };
  }

  async getLogStats(): Promise<JsonRecord> {
    return {
      total_logs: 0,
      recent_logs_1h: 0,
      active_websockets: 0,
    };
  }

  async tailLogSource(source: string, lines = 100): Promise<JsonRecord> {
    return {
      source,
      lines,
      entries: [],
    };
  }

  async exportLogs(_format: string, _params?: QueryRecord): Promise<Blob> {
    await this.recordDeferredFeature(
      'Logs export deferred',
      'Aggregated backend log export remains explicit remote-only in local mode.',
    );
    return new Blob([JSON.stringify(makeDeferredResult('Logs export remains remote-only in local mode.'))], {
      type: 'application/json',
    });
  }

  async getStreamingAnalytics(): Promise<StreamingAnalytics> {
    const state = await loadLocalControlPlaneState();
    return {
      ...state.analytics,
      active_sessions: state.sessions.filter((session) => session.status === 'playing').length,
      session_count: state.sessions.length,
    };
  }

  async listStreamingSessions(): Promise<StreamingSessionSummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.sessions;
  }

  async getStreamingHealth(): Promise<StreamingHealthResponse> {
    const state = await loadLocalControlPlaneState();
    return {
      status: 'healthy',
      health_score: 100,
      stalled_sessions: 0,
      error_sessions: 0,
      total_active_sessions: state.sessions.length,
      sessions_by_stream_type: state.sessions.reduce<Record<string, number>>((acc, session) => {
        const streamType =
          typeof session.stream_type === 'string' && session.stream_type.length > 0
            ? session.stream_type
            : 'unknown';
        acc[streamType] = (acc[streamType] ?? 0) + 1;
        return acc;
      }, {}),
      stalled_by_stream_type: {},
      error_by_stream_type: {},
    };
  }

  async completeStreamingSession(sessionId: string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.sessions = state.sessions.map((session) =>
        session.session_id === sessionId ? { ...session, status: 'completed' } : session,
      );
      state.analytics.active_sessions = state.sessions.filter((session) => session.status === 'playing').length;
      return appendActionHistory(state, {
        title: 'Completed local session',
        detail: `Marked ${sessionId} complete.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return { success: true, message: 'Local streaming session completed.' };
  }

  async resetStreamingSession(sessionId: string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.sessions = state.sessions.map((session) =>
        session.session_id === sessionId ? { ...session, status: 'idle' } : session,
      );
      return appendActionHistory(state, {
        title: 'Reset local session',
        detail: `Reset ${sessionId}.`,
        status: 'info',
        mode: 'local',
      });
    });
    return { success: true, message: 'Local streaming session reset.' };
  }

  async stopStreamingSession(sessionId: string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.sessions = state.sessions.filter((session) => session.session_id !== sessionId);
      state.analytics.active_sessions = state.sessions.filter((session) => session.status === 'playing').length;
      return appendActionHistory(state, {
        title: 'Stopped local session',
        detail: `Stopped ${sessionId}.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return { success: true, message: 'Local streaming session removed.' };
  }

  async listOverlayCastSessions(): Promise<OverlayCastSessionSummary[]> {
    return [];
  }

  async stopOverlayCastSession(sessionId: string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) =>
      appendActionHistory(state, {
        title: 'Overlay cast stop deferred',
        detail: `Overlay cast session ${sessionId} is not available in local mode.`,
        status: 'deferred',
        mode: 'local',
      }),
    );

    return {
      status: 'deferred',
      message: 'Overlay cast sessions are deferred in local mode.',
      session_id: sessionId,
    };
  }

  async listRenderers(): Promise<RendererInstanceSummary[]> {
    return [];
  }

  async listProjectors(): Promise<RendererProjectorSummary[]> {
    return [];
  }

  async getRendererStatus(_projectorId: string): Promise<JsonRecord> {
    return { status: 'deferred', message: 'Renderer status is deferred in local mode.' };
  }

  async discoverAirPlayDevices(): Promise<JsonRecord> {
    return { devices: [], status: 'deferred' };
  }

  async listAirPlayDevices(): Promise<JsonRecord> {
    return { devices: [], status: 'deferred' };
  }

  async getAllAirPlayDevices(): Promise<JsonRecord> {
    return { devices: [], status: 'deferred' };
  }

  async listOverlayConfigs(): Promise<OverlayConfigSummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.overlayConfigs;
  }

  async createOverlayConfig(payload: JsonRecord): Promise<JsonRecord> {
    let created: JsonRecord = {};
    await updateLocalControlPlaneState((state) => {
      created = {
        id: payload.id ?? `overlay-${state.overlayConfigs.length + 1}`,
        name: payload.name ?? `Local overlay ${state.overlayConfigs.length + 1}`,
        ...payload,
      };
      state.overlayConfigs = [...state.overlayConfigs, created as OverlayConfigSummary];
      return appendActionHistory(state, {
        title: 'Saved local overlay config',
        detail: `Saved overlay config ${String(created.name ?? created.id)} in local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return created;
  }

  async deleteOverlayConfig(configId: number | string): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.overlayConfigs = state.overlayConfigs.filter(
        (config) => String(config.id) !== String(configId),
      );
      return appendActionHistory(state, {
        title: 'Deleted local overlay config',
        detail: `Deleted overlay config ${String(configId)} in local mode.`,
        status: 'info',
        mode: 'local',
      });
    });
    return { success: true, message: `Deleted overlay config ${String(configId)} locally.` };
  }

  async getOverlayBrightness(): Promise<JsonRecord> {
    const state = await loadLocalControlPlaneState();
    return {
      brightness: state.overlayStatus.brightness ?? 0,
    };
  }

  async setOverlayBrightness(brightness: number): Promise<JsonRecord> {
    await updateLocalControlPlaneState((state) => {
      state.overlayStatus = {
        ...state.overlayStatus,
        brightness,
      };
      return appendActionHistory(state, {
        title: 'Updated local overlay brightness',
        detail: `Overlay brightness set to ${String(brightness)} in local mode.`,
        status: 'ok',
        mode: 'local',
      });
    });
    return { brightness };
  }

  async exportOverlayMp4(_payload: JsonRecord): Promise<Blob> {
    await this.recordDeferredFeature(
      'Overlay export deferred',
      'Overlay MP4 export remains explicit remote-only in local mode.',
    );
    return new Blob([], { type: 'video/mp4' });
  }

  async startOverlayCast(payload: JsonRecord): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Overlay cast deferred',
      `Overlay cast for config ${String(payload.config_id ?? 'unknown')} remains remote-only in local mode.`,
    );
    return makeDeferredResult('Overlay casting remains remote-only in local mode.');
  }

  async listRendererScenes(): Promise<RendererSceneSummary[]> {
    return [];
  }

  async startRenderer(_projector: string, _scene: string): Promise<RendererActionResponse> {
    return makeDeferredResult('Renderer orchestration is deferred in local mode.') as RendererActionResponse;
  }

  async startProjector(_projectorId: string): Promise<RendererActionResponse> {
    return makeDeferredResult('Projector launch is deferred in local mode.') as RendererActionResponse;
  }

  async pauseRenderer(_projectorId: string): Promise<RendererActionResponse> {
    return makeDeferredResult('Renderer pause is deferred in local mode.') as RendererActionResponse;
  }

  async resumeRenderer(_projectorId: string): Promise<RendererActionResponse> {
    return makeDeferredResult('Renderer resume is deferred in local mode.') as RendererActionResponse;
  }

  async stopRenderer(_projectorId: string): Promise<RendererActionResponse> {
    return makeDeferredResult('Renderer stop is deferred in local mode.') as RendererActionResponse;
  }

  async getOverlayStatus(): Promise<OverlayStatusResponse> {
    const state = await loadLocalControlPlaneState();
    return state.overlayStatus;
  }

  async triggerOverlaySync(): Promise<OverlaySyncResponse> {
    await updateLocalControlPlaneState((state) =>
      appendActionHistory(state, {
        title: 'Skipped overlay sync',
        detail: 'Overlay sync is deferred in local mode and is surfaced as a safe no-op.',
        status: 'deferred',
        mode: 'local',
      }),
    );
    return {
      status: 'deferred',
      affected_overlays: '0',
      synced_devices: [],
      failed_devices: [],
      device_count: 0,
    };
  }

  async listMappingScenes(): Promise<MappingSceneSummary[]> {
    return [];
  }

  async listSceneRanks(): Promise<SceneRankSummary[]> {
    return [];
  }

  async listSceneControlPresets(): Promise<SceneControlPresetSummary[]> {
    return [];
  }

  async listProjectionConfigs(): Promise<ProjectionConfigSummary[]> {
    return [];
  }

  async launchProjectionConfig(configId: number | string): Promise<ProjectionSessionSummary> {
    await updateLocalControlPlaneState((state) =>
      appendActionHistory(state, {
        title: 'Projection deferred',
        detail: `Projection config ${String(configId)} remains deferred in local mode.`,
        status: 'deferred',
        mode: 'local',
      }),
    );
    return {
      id: `deferred-${String(configId)}`,
      status: 'deferred',
      config_id: configId,
      zones: [],
    };
  }

  async getProjectionSession(sessionId: string): Promise<ProjectionSessionSummary> {
    return {
      id: sessionId,
      status: 'deferred',
      zones: [],
    };
  }

  async listProjectionAnimations(): Promise<JsonRecord> {
    return {
      animations: [],
    };
  }

  async listProjectionAnimationLists(): Promise<JsonRecord[]> {
    return [];
  }

  async getProjectionAnimationList(id: number | string): Promise<JsonRecord> {
    return {
      id,
      status: 'deferred',
    };
  }

  async createProjectionAnimationList(_data: JsonRecord): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Projection animation list deferred',
      'Projection animation list management remains explicit remote-only in local mode.',
    );
    return makeDeferredResult('Projection animation list management remains remote-only in local mode.');
  }

  async updateProjectionAnimationList(_id: number | string, _data: JsonRecord): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Projection animation update deferred',
      'Projection animation list management remains explicit remote-only in local mode.',
    );
    return makeDeferredResult('Projection animation list management remains remote-only in local mode.');
  }

  async deleteProjectionAnimationList(id: number | string): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Projection animation delete deferred',
      `Projection animation list ${String(id)} remains remote-only in local mode.`,
    );
    return makeDeferredResult('Projection animation list management remains remote-only in local mode.');
  }

  async getStructuredLightingCapabilities(): Promise<JsonRecord> {
    return makeDeferredResult('Structured lighting remains remote-only in local mode.');
  }

  async getStructuredLightingStatus(): Promise<JsonRecord> {
    return makeDeferredResult('Structured lighting remains remote-only in local mode.');
  }

  async listStructuredLightingSessions(): Promise<JsonRecord[]> {
    return [];
  }

  async createStructuredLightingSession(_payload: JsonRecord): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Structured lighting deferred',
      'Structured lighting session creation remains explicit remote-only in local mode.',
    );
    return makeDeferredResult('Structured lighting remains remote-only in local mode.');
  }

  async deleteStructuredLightingSession(sessionId: string): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Structured lighting deferred',
      `Structured lighting session ${sessionId} remains remote-only in local mode.`,
    );
    return makeDeferredResult('Structured lighting remains remote-only in local mode.');
  }

  async getStructuredLightingRuntime(sessionId: string): Promise<JsonRecord> {
    return makeDeferredResult('Structured lighting runtime remains remote-only in local mode.', {
      session_id: sessionId,
    });
  }

  async listStructuredLightingCaptures(_sessionId: string): Promise<JsonRecord[]> {
    return [];
  }

  async startStructuredLightingSession(sessionId: string): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Structured lighting deferred',
      `Structured lighting session ${sessionId} remains remote-only in local mode.`,
    );
    return makeDeferredResult('Structured lighting remains remote-only in local mode.');
  }

  async uploadDepthMap(_formData: FormData): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Depth upload deferred',
      'Depth processing remains explicit remote-only in local mode.',
    );
    return makeDeferredResult('Depth processing remains remote-only in local mode.');
  }

  getDepthPreviewUrl(depthId: number | string): string {
    return this.buildLocalFeatureUrl(`/depth/preview/${depthId}`);
  }

  async segmentDepthMap(depthId: number | string, _segmentationParams: JsonRecord): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Depth segmentation deferred',
      `Depth map ${String(depthId)} segmentation remains remote-only in local mode.`,
    );
    return makeDeferredResult('Depth processing remains remote-only in local mode.');
  }

  getDepthSegmentationPreviewUrl(depthId: number | string, alpha = 0.5): string {
    return this.buildLocalFeatureUrl(`/depth/segmentation_preview/${depthId}`, { alpha });
  }

  async exportDepthMasks(
    depthId: number | string,
    _segmentIds: Array<number | string>,
    _cleanMask = true,
    _minArea = 100,
    _kernelSize = 3,
  ): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Depth mask export deferred',
      `Depth mask export for ${String(depthId)} remains remote-only in local mode.`,
    );
    return makeDeferredResult('Depth processing remains remote-only in local mode.');
  }

  async deleteDepthMap(depthId: number | string): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Depth delete deferred',
      `Depth map ${String(depthId)} remains remote-only in local mode.`,
    );
    return makeDeferredResult('Depth processing remains remote-only in local mode.');
  }

  getDepthMaskUrl(
    depthId: number | string,
    segmentId: number | string,
    clean = true,
    minArea = 100,
    kernelSize = 3,
  ): string {
    return this.buildLocalFeatureUrl(`/depth/mask/${depthId}/${segmentId}`, {
      clean,
      min_area: minArea,
      kernel_size: kernelSize,
    });
  }

  async createDepthProjection(_config: JsonRecord): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Depth projection deferred',
      'Depth projection creation remains explicit remote-only in local mode.',
    );
    return makeDeferredResult('Depth processing remains remote-only in local mode.');
  }

  getDepthProjectionUrl(configId: number | string): string {
    return this.buildLocalFeatureUrl(`/depth/projection/${configId}`);
  }

  async deleteDepthProjection(configId: number | string): Promise<JsonRecord> {
    await this.recordDeferredFeature(
      'Depth projection deferred',
      `Depth projection ${String(configId)} remains remote-only in local mode.`,
    );
    return makeDeferredResult('Depth processing remains remote-only in local mode.');
  }

  async listActionHistory(): Promise<ActionHistoryEntry[]> {
    const state = await loadLocalControlPlaneState();
    return state.actionHistory;
  }

  async listCapabilities(): Promise<LocalCapabilitySummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.capabilities;
  }

  async listDeferredFeatures(): Promise<DeferredFeatureSummary[]> {
    const state = await loadLocalControlPlaneState();
    return state.deferredFeatures;
  }

  async duplicateOverlayConfig(_configId: number | string): Promise<OverlayConfigSummary> {
    await this.recordDeferredFeature('Overlay config duplication deferred', 'Remains remote-only in local mode.');
    return makeDeferredResult('Duplication deferred') as unknown as OverlayConfigSummary;
  }
  async createOverlayStream(_payload: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Overlay stream deferred'); }
  async getOverlayWindowInit(_projectorId?: string): Promise<JsonRecord> { return makeDeferredResult('Overlay window init deferred'); }
  async getOverlayWindowRefreshState(_projectorId?: string): Promise<JsonRecord> { return makeDeferredResult('Overlay window state deferred'); }
  async getOverlayWidgetData(_projectorId?: string): Promise<JsonRecord> { return makeDeferredResult('Overlay widget data deferred'); }
  async heartbeatProjectorClient(_payload: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Overlay heartbeat deferred'); }
  async getOverlayPlaybackSync(_projectorId?: string): Promise<JsonRecord> { return makeDeferredResult('Overlay playback sync deferred'); }
  async getBrightnessStatus(): Promise<JsonRecord> { return makeDeferredResult('Overlay brightness status deferred'); }
  getOverlayEventsUrl(): string { return this.buildLocalFeatureUrl('/overlay/events'); }

  async createProjectionSession(_payload: JsonRecord): Promise<ProjectionSessionSummary> {
    return makeDeferredResult('Projection session deferred') as unknown as ProjectionSessionSummary;
  }
  async deleteProjectionSession(_sessionId: string): Promise<JsonRecord> { return makeDeferredResult('Projection session deferred'); }
  async uploadProjectionMask(_formData: FormData): Promise<JsonRecord> { return makeDeferredResult('Projection mask upload deferred'); }
  async getProjectionMask(_maskId: string): Promise<JsonRecord> { return makeDeferredResult('Projection mask deferred'); }
  getProjectionMaskImageUrl(sessionId: string): string { return this.buildLocalFeatureUrl('/projection/masks/' + sessionId + '/image'); }
  async importCodepenAnimation(_payload: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Codepen import deferred'); }

  async startStructuredLightingWorker(_payload: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting worker deferred'); }
  async stopStructuredLightingWorker(): Promise<JsonRecord> { return makeDeferredResult('Structured lighting worker deferred'); }
  async confirmStructuredLightingWorkerReady(_workerId: string): Promise<JsonRecord> { return makeDeferredResult('Structured lighting worker deferred'); }
  async decodeStructuredLightingSession(_sessionId: string, _payload?: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting decode deferred'); }
  async runStructuredLightingPreviewTuning(_sessionId: string, _payload?: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting tuning deferred'); }
  async getStructuredLightingPreviewTuning(_sessionId: string): Promise<JsonRecord> { return makeDeferredResult('Structured lighting tuning deferred'); }
  async runStructuredLightingTuningSearch(_sessionId: string, _payload?: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting tuning deferred'); }
  async getStructuredLightingTuningSearch(_sessionId: string): Promise<JsonRecord> { return makeDeferredResult('Structured lighting tuning deferred'); }
  async getStructuredLightingCalibration(_sessionId: string): Promise<JsonRecord> { return makeDeferredResult('Structured lighting calibration deferred'); }
  async getStructuredLightingArtifactReview(_sessionId: string): Promise<JsonRecord> { return makeDeferredResult('Structured lighting artifact review deferred'); }
  async updateStructuredLightingReview(_sessionId: string, _payload: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting review deferred'); }
  async publishStructuredLightingMappingScene(_sessionId: string, _payload?: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting publish mapping deferred'); }
  getStructuredLightingStepImageUrl(sessionId: string, stepIndex: number | string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/steps/' + stepIndex + '/image'); }
  getStructuredLightingCaptureImageUrl(sessionId: string, stepIndex: number | string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/captures/' + stepIndex + '/image'); }
  getStructuredLightingArtifactPreviewUrl(sessionId: string, previewId: string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/artifacts/previews/' + previewId); }
  getStructuredLightingPreviewTuningPreviewUrl(sessionId: string, candidateId: string, previewName: string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/preview-tuning/' + candidateId + '/previews/' + previewName); }
  getStructuredLightingTuningSearchPreviewUrl(sessionId: string, candidateId: string, previewName: string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/tuning-search/' + candidateId + '/previews/' + previewName); }
  getStructuredLightingExportUrl(sessionId: string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/export'); }
  async uploadStructuredLightingCapture(_sessionId: string, _formData: FormData): Promise<JsonRecord> { return makeDeferredResult('Structured lighting capture upload deferred'); }
}

export function createControlPlaneClient(mode: AppMode, apiBaseUrl: string): ControlPlaneClient {
  if (mode === 'local') {
    return new LocalControlPlaneClient();
  }
  return new RemoteControlPlaneAdapter(apiBaseUrl);
}

export { DEFAULT_REMOTE_API_BASE_URL };
