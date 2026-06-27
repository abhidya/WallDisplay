import type { ControlPlaneClient } from './client';

export type DeviceControlModule = Pick<
  ControlPlaneClient,
  | 'getHealth'
  | 'listDevices'
  | 'getDevice'
  | 'getDiscoveryStatus'
  | 'getUnifiedDiscoveryStatus'
  | 'getUnifiedDiscoveryCapabilities'
  | 'listDiscoveryBackends'
  | 'enableDiscoveryBackend'
  | 'disableDiscoveryBackend'
  | 'pauseDiscovery'
  | 'resumeDiscovery'
  | 'discoverDevices'
  | 'getDeviceControlMode'
  | 'enableAutoMode'
  | 'enableManualMode'
  | 'pauseDevicePlayback'
  | 'stopDevicePlayback'
  | 'playVideoOnDevice'
>;

export type MediaLibraryModule = Pick<
  ControlPlaneClient,
  | 'listVideos'
  | 'listPhotos'
  | 'listMediaDirectories'
  | 'scanMediaDirectory'
  | 'listMediaLists'
  | 'listMediaChannels'
  | 'advanceMediaChannel'
  | 'listPhotoLists'
  | 'createMediaList'
  | 'createMediaChannel'
  | 'deleteMediaList'
  | 'deleteMediaChannel'
  | 'createVideo'
  | 'deleteVideo'
  | 'uploadVideo'
  | 'createPhoto'
  | 'deletePhoto'
  | 'uploadPhoto'
  | 'createMediaDirectory'
  | 'deleteMediaDirectory'
  | 'createPhotoList'
  | 'deletePhotoList'
  | 'playVideoOnDevice'
>;

export type OperationsModule = Pick<
  ControlPlaneClient,
  | 'mode'
  | 'getStreamingAnalytics'
  | 'listStreamingSessions'
  | 'getStreamingHealth'
  | 'completeStreamingSession'
  | 'resetStreamingSession'
  | 'stopStreamingSession'
  | 'listOverlayCastSessions'
  | 'stopOverlayCastSession'
  | 'listRenderers'
  | 'listProjectors'
  | 'getRendererStatus'
  | 'getAllAirPlayDevices'
  | 'listOverlayConfigs'
  | 'startRenderer'
  | 'startProjector'
  | 'pauseRenderer'
  | 'resumeRenderer'
  | 'stopRenderer'
  | 'getOverlayStatus'
  | 'triggerOverlaySync'
  | 'listMappingScenes'
  | 'listSceneRanks'
  | 'listSceneControlPresets'
  | 'listProjectionConfigs'
  | 'launchProjectionConfig'
  | 'getProjectionSession'
  | 'listCapabilities'
  | 'listActionHistory'
  | 'listDeferredFeatures'
  | 'listRendererScenes'
>;

export type OverviewModule = Pick<
  ControlPlaneClient,
  | 'getHealth'
  | 'listDevices'
  | 'getStreamingAnalytics'
  | 'listRenderers'
  | 'listProjectionConfigs'
  | 'getUnifiedDiscoveryStatus'
>;

export type OverlayProjectionModule = Pick<
  ControlPlaneClient,
  | 'listOverlayConfigs'
  | 'listOverlayCastSessions'
  | 'getOverlayStatus'
  | 'getBrightnessStatus'
>;

export type ProjectionModule = Pick<
  ControlPlaneClient,
  | 'listProjectionConfigs'
  | 'listProjectionAnimations'
  | 'listProjectionAnimationLists'
>;

export type SettingsModule = Pick<
  ControlPlaneClient,
  | 'getHealth'
  | 'getUnifiedDiscoveryStatus'
  | 'getGlobalApiConfigs'
  | 'updateGlobalApiConfigs'
  | 'getProjectorRedirectConfig'
  | 'updateProjectorRedirectConfig'
  | 'getRecentProjectorRedirectRequests'
  | 'getServiceDiagnostics'
  | 'getIncidentDetail'
>;

export type StructuredLightingModule = Pick<
  ControlPlaneClient,
  | 'getStructuredLightingCapabilities'
  | 'getStructuredLightingStatus'
  | 'listStructuredLightingSessions'
>;
