import type {
  ActionHistoryEntry,
  DeferredFeatureSummary,
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
  OverlayStatusResponse,
  PhotoSummary,
  ProjectionConfigSummary,
  ProjectionSessionSummary,
  RendererProjectorSummary,
  RendererSceneSummary,
  SceneControlPresetSummary,
  SceneRankSummary,
  StreamingAnalytics,
  StreamingSessionSummary,
  VideoSummary,
} from '../types/api.ts';
import { getStoredJson, setStoredJson } from './storage.ts';

export type AppMode = 'local' | 'remote';

export interface PersistedAppState {
  apiBaseUrl: string;
  mode: AppMode;
  selectedDeviceId: number | string | null;
  selectedDeviceLabel: string | null;
}

interface PersistedLocalDevice extends DeviceDetail {
  control_mode?: DeviceControlMode;
}

export interface LocalControlPlaneState {
  version: number;
  app: PersistedAppState;
  discoveryStatus: DiscoveryStatus;
  unifiedDiscoveryStatus: DiscoverySystemStatus;
  health: HealthResponse;
  discoveryBackends: DiscoveryBackendSummary[];
  discoveryCapabilities: DiscoveryCapabilities;
  devices: PersistedLocalDevice[];
  videos: VideoSummary[];
  photos: PhotoSummary[];
  directories: MediaDirectorySummary[];
  lists: MediaListSummary[];
  channels: MediaChannelSummary[];
  analytics: StreamingAnalytics;
  sessions: StreamingSessionSummary[];
  actionHistory: ActionHistoryEntry[];
  capabilities: LocalCapabilitySummary[];
  deferredFeatures: DeferredFeatureSummary[];
  renderers: RendererProjectorSummary[];
  rendererScenes: RendererSceneSummary[];
  overlayConfigs: OverlayConfigSummary[];
  overlayStatus: OverlayStatusResponse;
  mappingScenes: MappingSceneSummary[];
  sceneRanks: SceneRankSummary[];
  sceneControlPresets: SceneControlPresetSummary[];
  projectionConfigs: ProjectionConfigSummary[];
  projectionSessions: ProjectionSessionSummary[];
}

const LOCAL_STATE_KEY = 'nano-dlna/mobile-app/local-control-plane-state/v1';

export const DEFAULT_REMOTE_API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000/api';

export const defaultAppState: PersistedAppState = {
  apiBaseUrl: DEFAULT_REMOTE_API_BASE_URL,
  mode: 'local',
  selectedDeviceId: 'local-sim-1',
  selectedDeviceLabel: 'Local simulator display',
};

const initialDevices: PersistedLocalDevice[] = [
  {
    id: 'local-sim-1',
    friendly_name: 'Local simulator display',
    device_name: 'Simulator display',
    type: 'local-simulator',
    manufacturer: 'nano-dlna',
    location: 'On device',
    status: 'ready',
    derived_status: 'ready',
    playback_state: 'idle',
    is_playing: false,
    current_media_title: 'Idle',
    action_url: 'local://device/local-sim-1',
    control_mode: {
      mode: 'local',
      reason: 'App-owned control plane',
      expires_at: null,
    },
    config: {
      kind: 'simulated',
      supports_manual_actions: true,
      supports_native_discovery: false,
      note: 'Use this built-in target to validate local workflows without a backend.',
    },
  },
  {
    id: 'saved-dlna-target',
    friendly_name: 'Saved DLNA target (profile)',
    device_name: 'Saved target',
    type: 'manual-profile',
    manufacturer: 'Manual profile',
    location: 'Saved config',
    status: 'profile-only',
    derived_status: 'idle',
    playback_state: 'idle',
    is_playing: false,
    current_media_title: 'No active playback',
    action_url: 'local://device/saved-dlna-target',
    control_mode: {
      mode: 'manual-profile',
      reason: 'Native discovery is deferred in v1; this profile keeps local workflows testable.',
      expires_at: null,
    },
    config: {
      kind: 'manual-profile',
      supports_manual_actions: true,
      supports_native_discovery: false,
      note: 'Replace this with native discovery/device APIs in a follow-up iteration.',
    },
  },
];

const initialVideos: VideoSummary[] = [
  {
    id: 'video-1',
    title: 'Operator console demo reel',
    duration: 94,
    mime_type: 'video/mp4',
    file_path: 'local://media/operator-demo.mp4',
  },
  {
    id: 'video-2',
    title: 'Projection diagnostics clip',
    duration: 42,
    mime_type: 'video/mp4',
    file_path: 'local://media/projection-diagnostics.mp4',
  },
];

const initialPhotos: PhotoSummary[] = [
  {
    id: 'photo-1',
    name: 'Operator dashboard poster',
    resolution: '1920x1080',
    format: 'png',
    category: 'reference',
    path: 'local://media/poster.png',
  },
];

const initialDirectories: MediaDirectorySummary[] = [
  {
    id: 'dir-1',
    name: 'Bundled samples',
    path: 'local://media/',
    category: 'bundled',
    enabled: true,
    scan_mode: 'on-demand',
  },
];

const initialLists: MediaListSummary[] = [
  {
    id: 'list-1',
    name: 'Ready to play',
    category: 'local',
    playback_mode: 'manual',
  },
];

const initialChannels: MediaChannelSummary[] = [
  {
    id: 'channel-1',
    name: 'Diagnostics loop',
    media_list_id: 'list-1',
    current_video_id: 'video-1',
    current_index: 0,
  },
];

const initialCapabilities: LocalCapabilitySummary[] = [
  {
    key: 'local-mode',
    label: 'Local control plane',
    status: 'ready',
    detail: 'The app owns UI state, saved configuration, and workflow orchestration locally.',
  },
  {
    key: 'device-profiles',
    label: 'Saved device profiles',
    status: 'ready',
    detail: 'Local workflows can target saved/manual device records without requiring FastAPI.',
  },
  {
    key: 'native-discovery',
    label: 'Native discovery adapters',
    status: 'deferred',
    detail: 'mDNS/SSDP/native local-network discovery requires native modules and development builds.',
  },
  {
    key: 'advanced-renderer',
    label: 'Renderer / overlay / projection parity',
    status: 'deferred',
    detail: 'Advanced operations are intentionally reduced in v1 to keep local mode safe.',
  },
];

const initialDeferredFeatures: DeferredFeatureSummary[] = [
  {
    id: 'deferred-renderer',
    title: 'Renderer orchestration deferred',
    detail: 'Full renderer start/pause/resume and scene routing stay behind the backend until a native/mobile-safe design is approved.',
    next_step: 'Follow-up PRD for renderer / overlay / projection parity.',
  },
  {
    id: 'deferred-receiver',
    title: 'Receiver / extended display deferred',
    detail: 'AirPlay receiver, Chromecast receiver, DLNA receiver, and external-display hosting are out of scope for this iteration.',
    next_step: 'Separate sender/receiver planning after local workflows stabilize.',
  },
];

function createInitialState(): LocalControlPlaneState {
  return {
    version: 1,
    app: defaultAppState,
    health: {
      status: 'local-ready',
      message: 'Local control plane active. No backend server required.',
    },
    discoveryStatus: {
      running: true,
      paused: false,
      interval_seconds: 0,
      authority: 'on-device',
      unified_running: true,
    },
    unifiedDiscoveryStatus: {
      discovery_running: true,
      total_devices: initialDevices.length,
      online_devices: 1,
      active_sessions: 0,
      backends: {
        local: {
          name: 'local',
          active: true,
          enabled: true,
          healthy: true,
          last_seen: new Date().toISOString(),
        },
        remote_adapter: {
          name: 'remote_adapter',
          active: false,
          enabled: true,
          healthy: true,
        },
      },
    },
    discoveryBackends: [
      {
        name: 'local',
        active: true,
        enabled: true,
        healthy: true,
        last_seen: new Date().toISOString(),
      },
      {
        name: 'remote_adapter',
        active: false,
        enabled: true,
        healthy: true,
      },
    ],
    discoveryCapabilities: {
      casting_methods: ['local-control-plane', 'manual-device-profile'],
      device_capabilities: ['playback-controls', 'saved-configs', 'action-history'],
      content_types: ['video', 'photo', 'diagnostics'],
    },
    devices: initialDevices,
    videos: initialVideos,
    photos: initialPhotos,
    directories: initialDirectories,
    lists: initialLists,
    channels: initialChannels,
    analytics: {
      active_sessions: 0,
      session_count: 0,
      overlay_sessions: 0,
      total_bandwidth_mbps: 0,
    },
    sessions: [],
    actionHistory: [
      {
        id: 'boot-local-mode',
        title: 'Local mode ready',
        detail: 'App booted with the built-in control plane and no backend dependency.',
        created_at: new Date().toISOString(),
        status: 'ok',
        mode: 'local',
      },
    ],
    capabilities: initialCapabilities,
    deferredFeatures: initialDeferredFeatures,
    renderers: [],
    rendererScenes: [],
    overlayConfigs: [],
    overlayStatus: {
      brightness: 0,
      sync: {
        mode: 'deferred',
      },
    },
    mappingScenes: [],
    sceneRanks: [],
    sceneControlPresets: [],
    projectionConfigs: [],
    projectionSessions: [],
  };
}

export function createDefaultLocalControlPlaneState(): LocalControlPlaneState {
  return createInitialState();
}

function cloneState<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function ensureStateShape(state: LocalControlPlaneState): LocalControlPlaneState {
  return {
    ...createInitialState(),
    ...state,
    app: {
      ...defaultAppState,
      ...(state.app ?? {}),
    },
    devices: state.devices?.length ? state.devices : createInitialState().devices,
    videos: state.videos?.length ? state.videos : createInitialState().videos,
    photos: state.photos?.length ? state.photos : createInitialState().photos,
    directories: state.directories?.length ? state.directories : createInitialState().directories,
    lists: state.lists?.length ? state.lists : createInitialState().lists,
    channels: state.channels?.length ? state.channels : createInitialState().channels,
    actionHistory: state.actionHistory?.length
      ? state.actionHistory
      : createInitialState().actionHistory,
    capabilities: state.capabilities?.length ? state.capabilities : createInitialState().capabilities,
    deferredFeatures: state.deferredFeatures?.length
      ? state.deferredFeatures
      : createInitialState().deferredFeatures,
  };
}

export async function loadLocalControlPlaneState(): Promise<LocalControlPlaneState> {
  const state = await getStoredJson<LocalControlPlaneState>(LOCAL_STATE_KEY, createInitialState());
  return ensureStateShape(state);
}

export async function saveLocalControlPlaneState(state: LocalControlPlaneState): Promise<void> {
  await setStoredJson(LOCAL_STATE_KEY, ensureStateShape(state));
}

export async function resetLocalControlPlaneState(): Promise<LocalControlPlaneState> {
  const initial = createInitialState();
  await saveLocalControlPlaneState(initial);
  return initial;
}

export async function updateLocalControlPlaneState(
  updater: (state: LocalControlPlaneState) => LocalControlPlaneState,
): Promise<LocalControlPlaneState> {
  const current = await loadLocalControlPlaneState();
  const next = ensureStateShape(updater(cloneState(current)));
  await saveLocalControlPlaneState(next);
  return next;
}

export function appendActionHistory(
  state: LocalControlPlaneState,
  entry: {
    title: string;
    detail: string;
    status: 'ok' | 'success' | 'info' | 'deferred';
    mode?: string;
    id?: string;
    created_at?: string;
  },
): LocalControlPlaneState {
  const nextEntry: ActionHistoryEntry = {
    id: entry.id ?? `${entry.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${Date.now()}`,
    created_at: entry.created_at ?? new Date().toISOString(),
    title: entry.title,
    detail: entry.detail ?? '',
    status:
      entry.status === 'ok' ||
      entry.status === 'success' ||
      entry.status === 'info' ||
      entry.status === 'deferred'
        ? entry.status
        : 'info',
    mode: entry.mode === 'remote' ? 'remote' : 'local',
  };

  return {
    ...state,
    actionHistory: [nextEntry, ...state.actionHistory].slice(0, 20),
  };
}

export function updateSelectedDeviceInState(
  state: LocalControlPlaneState,
  deviceId: number | string | null,
  label: string | null,
): LocalControlPlaneState {
  return {
    ...state,
    app: {
      ...state.app,
      selectedDeviceId: deviceId,
      selectedDeviceLabel: label,
    },
  };
}

export function summarizeDevice(device: PersistedLocalDevice): DeviceSummary {
  return {
    id: device.id,
    name: device.name,
    friendly_name: device.friendly_name,
    device_name: device.device_name,
    type: device.type,
    hostname: device.hostname,
    status: device.status,
    availability: device.availability,
    derived_status: device.derived_status,
    playback_state: device.playback_state,
    is_playing: device.is_playing,
    current_video: device.current_video,
    current_media_title: device.current_media_title,
    playback_position: device.playback_position,
    playback_duration: device.playback_duration,
    playback_progress: device.playback_progress,
    manufacturer: device.manufacturer,
    location: device.location,
    streaming_url: device.streaming_url,
    active_overlay_cast: device.active_overlay_cast,
    seconds_since_seen: device.seconds_since_seen,
  };
}

export function makeDeferredResult(message: string, extra?: JsonRecord): JsonRecord {
  return {
    success: false,
    status: 'deferred',
    message,
    ...extra,
  };
}
