/* global FormData, Response */

import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';

import { createServiceModules } from '../src/services/api.ts';

function jsonResponse(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

function blobResponse(body, init = {}) {
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'application/octet-stream' },
    ...init,
  });
}

function installFetchMock(responses) {
  const originalFetch = globalThis.fetch;
  const calls = [];
  let index = 0;

  globalThis.fetch = async (input, init) => {
    calls.push({ input: String(input), init });
    const next = responses[index];
    index += 1;
    if (!next) {
      throw new Error(`Unexpected fetch call for ${String(input)}`);
    }
    return typeof next === 'function' ? next(input, init) : next;
  };

  return {
    calls,
    restore() {
      globalThis.fetch = originalFetch;
    },
  };
}

let activeMock = null;

afterEach(() => {
  activeMock?.restore();
  activeMock = null;
});

test('service modules expose the legacy frontend service surface inside mobile-app', () => {
  const services = createServiceModules('http://controller.local:8000');
  const expectedMethods = {
    api: ['get', 'post', 'put', 'delete', 'request', 'buildUrl'],
    deviceApi: ['getDevices', 'getDevice', 'createDevice', 'updateDevice', 'deleteDevice', 'discoverDevices', 'playVideo', 'stopVideo', 'pauseVideo', 'seekVideo', 'loadConfig', 'saveConfig', 'pauseDiscovery', 'resumeDiscovery', 'setDiscoveryInterval', 'getDiscoveryStatus', 'enableAutoMode', 'enableManualMode', 'getControlMode'],
    discoveryV2Api: ['getDevices', 'getDevice', 'triggerDiscovery', 'getDeviceConfigs', 'getDeviceConfig', 'updateDeviceConfig', 'deleteDeviceConfig', 'getGlobalConfig', 'updateGlobalConfig', 'getBackends', 'enableBackend', 'disableBackend', 'startCast', 'stopCast', 'pauseCast', 'resumeCast', 'getActiveSessions', 'getSystemStatus'],
    overlayApi: ['listConfigs', 'getConfig', 'createConfig', 'updateConfig', 'deleteConfig', 'duplicateConfig', 'getGlobalApiConfigs', 'updateGlobalApiConfigs', 'getProjectorRedirectConfig', 'updateProjectorRedirectConfig', 'getRecentProjectorRedirectRequests', 'listTemplates', 'createConfigFromTemplate', 'getBrightness', 'setBrightness', 'exportMp4', 'startCast', 'listCastSessions', 'stopCastSession'],
    structuredLightingApi: ['getCapabilities', 'getStatus', 'startWorker', 'stopWorker', 'confirmWorkerReady', 'listSessions', 'createSession', 'deleteSession', 'getCapturePlan', 'getRuntime', 'listCaptures', 'decodeSession', 'runPreviewTuning', 'getPreviewTuning', 'runTuningSearch', 'getTuningSearch', 'getCalibration', 'getArtifactReview', 'updateReview', 'startSession', 'publishMappingScene', 'getStepImageUrl', 'getCaptureImageUrl', 'getArtifactPreviewUrl', 'getPreviewTuningPreviewUrl', 'getTuningSearchPreviewUrl', 'getExportUrl'],
    videoApi: ['getVideos', 'getVideo', 'createVideo', 'updateVideo', 'deleteVideo', 'uploadVideo', 'streamVideo', 'scanDirectory'],
    photoApi: ['getPhotos', 'getPhoto', 'createPhoto', 'updatePhoto', 'deletePhoto', 'uploadPhoto', 'scanDirectory'],
    mappingsApi: ['listScenes', 'getScene', 'createScene', 'updateScene', 'deleteScene', 'listRanks', 'getRank', 'createRank', 'updateRank', 'deleteRank', 'listSceneControlPresets', 'getSceneControlPreset', 'createSceneControlPreset', 'updateSceneControlPreset', 'deleteSceneControlPreset', 'importScene', 'getExportUrl', 'createPolygonMask', 'uploadMasks', 'deleteMask'],
    mediaLibraryApi: ['listDirectories', 'browseDirectories', 'createDirectory', 'updateDirectory', 'deleteDirectory', 'scanDirectory', 'listMediaLists', 'createMediaList', 'updateMediaList', 'deleteMediaList', 'listMediaChannels', 'createMediaChannel', 'updateMediaChannel', 'advanceMediaChannel', 'deleteMediaChannel'],
    photoListApi: ['listPhotoLists', 'createPhotoList', 'updatePhotoList', 'deletePhotoList'],
    projectionApi: ['listAnimations', 'listAnimationLists', 'getAnimationList', 'createAnimationList', 'updateAnimationList', 'deleteAnimationList'],
    rendererApi: ['startRenderer', 'stopRenderer', 'pauseRenderer', 'resumeRenderer', 'getRendererStatus', 'listRenderers', 'listProjectors', 'listScenes', 'startProjector', 'discoverAirPlayDevices', 'listAirPlayDevices', 'getAllAirPlayDevices'],
    depthApi: ['uploadDepthMap', 'previewDepthMap', 'segmentDepthMap', 'previewSegmentation', 'exportMasks', 'deleteDepthMap', 'getMask', 'createProjection', 'getProjection', 'deleteProjection'],
    streamingApi: ['getStreamingStats', 'startStreaming', 'getSessions', 'getSession', 'deleteSession', 'getSessionsForDevice', 'completeSession', 'resetSession', 'getStreamingAnalytics', 'getStreamingHealth'],
    diagnosticsApi: ['getServiceDiagnostics', 'getIncidentDetail'],
    logsApi: ['getLogs', 'getSources', 'getLevels', 'getStats', 'tailSource', 'exportLogs'],
    settingsApi: ['getSettings', 'updateSettings'],
  };

  for (const [serviceName, methodNames] of Object.entries(expectedMethods)) {
    for (const methodName of methodNames) {
      assert.equal(
        typeof services[serviceName][methodName],
        'function',
        `${serviceName}.${methodName} should be defined`,
      );
    }
  }
});

test('service modules route representative requests through absolute mobile-safe URLs', async () => {
  activeMock = installFetchMock([
    jsonResponse([{ id: 1, friendly_name: 'Living Room' }]),
    jsonResponse({ success: true, message: 'interval updated' }),
    jsonResponse({ success: true }),
    blobResponse('binary-export'),
    jsonResponse({ status: 'decoded' }),
    jsonResponse({ uploaded: true }),
    jsonResponse({ scanned: true }),
    jsonResponse({ uploaded: true }),
    jsonResponse({ id: 'channel-1' }),
    jsonResponse({ id: 'list-1' }),
    jsonResponse({ projector: 'alpha', scene: 'main' }),
    jsonResponse({ projection: 'created' }),
    jsonResponse({ status: 'ok' }),
    jsonResponse({ id: 'incident-1' }),
  ]);

  const services = createServiceModules('http://controller.local:8000');
  const formData = new FormData();
  formData.append('file', 'demo');

  await services.deviceApi.getDevices();
  await services.deviceApi.setDiscoveryInterval(15);
  await services.discoveryV2Api.updateDeviceConfig('Office TV', { enabled: true });
  await services.overlayApi.exportMp4({ name: 'demo' });
  await services.structuredLightingApi.decodeSession('sess-1', { mode: 'fast' });
  await services.videoApi.uploadVideo(formData);
  await services.photoApi.scanDirectory('/photos', 'background', 'source-1');
  await services.mappingsApi.uploadMasks('scene-1', formData);
  await services.mediaLibraryApi.advanceMediaChannel('channel-1');
  await services.projectionApi.createAnimationList({ name: 'Ambient' });
  await services.rendererApi.getRendererStatus('proj-1');
  await services.depthApi.createProjection({ name: 'depth' });
  await services.streamingApi.getStreamingHealth();
  await services.diagnosticsApi.getIncidentDetail('incident-1', { include_resolved: true });

  assert.equal(
    services.structuredLightingApi.getStepImageUrl('sess-1', 2),
    'http://controller.local:8000/api/structured-lighting/sessions/sess-1/steps/2/image',
  );
  assert.equal(
    services.depthApi.previewDepthMap('depth-1'),
    'http://controller.local:8000/api/depth/preview/depth-1',
  );
  assert.equal(
    services.mappingsApi.getExportUrl('scene-1'),
    'http://controller.local:8000/api/mappings/scenes/scene-1/export',
  );

  assert.deepEqual(
    activeMock.calls.map((call) => ({
      input: call.input,
      method: call.init?.method ?? 'GET',
    })),
    [
      { input: 'http://controller.local:8000/api/devices', method: 'GET' },
      { input: 'http://controller.local:8000/api/devices/discovery/interval?seconds=15', method: 'POST' },
      { input: 'http://controller.local:8000/api/v2/discovery/config/devices/Office%20TV', method: 'PUT' },
      { input: 'http://controller.local:8000/api/overlay/export', method: 'POST' },
      { input: 'http://controller.local:8000/api/structured-lighting/sessions/sess-1/decode', method: 'POST' },
      { input: 'http://controller.local:8000/api/videos/upload', method: 'POST' },
      { input: 'http://controller.local:8000/api/photos/scan-directory?directory=%2Fphotos&category=background&source_directory_id=source-1', method: 'POST' },
      { input: 'http://controller.local:8000/api/mappings/scenes/scene-1/masks/upload', method: 'POST' },
      { input: 'http://controller.local:8000/api/media-library/channels/channel-1/advance', method: 'POST' },
      { input: 'http://controller.local:8000/api/projection/animation-lists', method: 'POST' },
      { input: 'http://controller.local:8000/api/renderer/status/proj-1', method: 'GET' },
      { input: 'http://controller.local:8000/api/depth/projection/create', method: 'POST' },
      { input: 'http://controller.local:8000/api/streaming/health', method: 'GET' },
      { input: 'http://controller.local:8000/api/diagnostics/incidents/incident-1?include_resolved=true', method: 'GET' },
    ],
  );
});
