import { NanoDlnaApiClient, normalizeApiBaseUrl } from '../services/api.ts';
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
  listActionHistory(): Promise<ActionHistoryEntry[]>;
  listCapabilities(): Promise<LocalCapabilitySummary[]>;
  listDeferredFeatures(): Promise<DeferredFeatureSummary[]>;
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
}

class LocalControlPlaneClient implements ControlPlaneClient {
  readonly mode: AppMode = 'local';
  readonly apiBaseUrl = 'local://control-plane';
  readonly rootBaseUrl = 'local://control-plane';

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
    return [];
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
}

export function createControlPlaneClient(mode: AppMode, apiBaseUrl: string): ControlPlaneClient {
  if (mode === 'local') {
    return new LocalControlPlaneClient();
  }
  return new RemoteControlPlaneAdapter(apiBaseUrl);
}

export { DEFAULT_REMOTE_API_BASE_URL };
