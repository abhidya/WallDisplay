import axios from 'axios';

// Create an axios instance with default config
const api = axios.create({
  baseURL: `${window.location.protocol}//${window.location.host}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add a request interceptor
api.interceptors.request.use(
  (config) => {
    // You can add auth tokens here if needed
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add a response interceptor
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Handle common errors here
    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx
      console.error('API Error Response:', error.response.data);
      console.error('Status:', error.response.status);
      
      // Add more specific error handling based on status codes
      if (error.response.status === 404) {
        console.error('API endpoint not found:', error.config.url);
        // You could dispatch to a notification system here
      } else if (error.response.status === 500) {
        console.error('Server error occurred:', error.config.url);
      } else if (error.response.status === 401) {
        console.error('Unauthorized access:', error.config.url);
      } else if (error.response.status === 403) {
        console.error('Forbidden access:', error.config.url);
      }
    } else if (error.request) {
      // The request was made but no response was received
      console.error('No response received from API. Backend may be down.');
      console.error('API Error Request:', error.request);
    } else {
      // Something happened in setting up the request that triggered an Error
      console.error('API Error Message:', error.message);
    }
    return Promise.reject(error);
  }
);

// Device API
const deviceApi = {
  getDevices: (params = {}) => api.get('/devices/', { params }),
  getDevice: (id) => api.get(`/devices/${id}`),
  createDevice: (data) => api.post('/devices/', data),
  updateDevice: (id, data) => api.put(`/devices/${id}`, data),
  deleteDevice: (id) => api.delete(`/devices/${id}`),
  discoverDevices: () => api.get('/devices/discover'),
  playVideo: (deviceId, videoId, loop = false, syncOverlays = false) => 
    api.post(`/devices/${deviceId}/play`, { video_id: videoId, loop }, {
      params: { sync_overlays: syncOverlays }
    }),
  stopVideo: (deviceId) => api.post(`/devices/${deviceId}/stop`),
  pauseVideo: (deviceId) => api.post(`/devices/${deviceId}/pause`),
  seekVideo: (deviceId, position) => 
    api.post(`/devices/${deviceId}/seek`, null, { params: { position } }),
  loadConfig: (configFile) => 
    api.post('/devices/load-config', null, { params: { config_file: configFile } }),
  saveConfig: (configFile) => 
    api.post('/devices/save-config', null, { params: { config_file: configFile } }),
  // Discovery control
  pauseDiscovery: () => api.post('/devices/discovery/pause'),
  resumeDiscovery: () => api.post('/devices/discovery/resume'),
  getDiscoveryStatus: () => api.get('/devices/discovery/status'),
  // User control mode
  enableAutoMode: (deviceId) => api.post(`/devices/${deviceId}/control/auto`),
  enableManualMode: (deviceId, reason, expiresIn) => 
    api.post(`/devices/${deviceId}/control/manual`, null, { 
      params: { reason, expires_in: expiresIn } 
    }),
  getControlMode: (deviceId) => api.get(`/devices/${deviceId}/control`),
};

// Discovery V2 API
const discoveryV2Api = {
  // Device Discovery
  getDevices: (params = {}) => api.get('/v2/discovery/devices', { params }),
  getDevice: (deviceId) => api.get(`/v2/discovery/devices/${deviceId}`),
  triggerDiscovery: (backend = null, timeout = 30) => 
    api.post('/v2/discovery/discover', null, { params: { backend, timeout } }),
  
  // Configuration Management
  getDeviceConfigs: () => api.get('/v2/discovery/config/devices'),
  getDeviceConfig: (deviceName) => api.get(`/v2/discovery/config/devices/${deviceName}`),
  updateDeviceConfig: (deviceName, config) => api.put(`/v2/discovery/config/devices/${deviceName}`, config),
  deleteDeviceConfig: (deviceName) => api.delete(`/v2/discovery/config/devices/${deviceName}`),
  getGlobalConfig: () => api.get('/v2/discovery/config/global'),
  updateGlobalConfig: (config) => api.put('/v2/discovery/config/global', config),
  
  // Backend Management
  getBackends: () => api.get('/v2/discovery/backends'),
  enableBackend: (backendName) => api.post(`/v2/discovery/backends/${backendName}/enable`),
  disableBackend: (backendName) => api.post(`/v2/discovery/backends/${backendName}/disable`),
  
  // Casting Control
  startCast: (deviceId, contentUrl, options = {}) => 
    api.post('/v2/discovery/cast', {
      device_id: deviceId,
      content_url: contentUrl,
      content_type: options.content_type || 'video/mp4',
      metadata: options.metadata || null,
    }),
  stopCast: (sessionId) => api.post(`/v2/discovery/stop/${sessionId}`),
  pauseCast: (sessionId) => api.post(`/v2/discovery/pause/${sessionId}`),
  resumeCast: (sessionId) => api.post(`/v2/discovery/resume/${sessionId}`),
  getActiveSessions: () => api.get('/v2/discovery/sessions'),
  
  // System Status
  getSystemStatus: () => api.get('/v2/discovery/status'),
};

const overlayApi = {
  startCast: (payload) => api.post('/overlay/cast', payload),
  listCastSessions: () => api.get('/overlay/cast/sessions'),
  stopCastSession: (sessionId) => api.delete(`/overlay/cast/sessions/${sessionId}`),
};

const structuredLightingApi = {
  getCapabilities: () => api.get('/structured-lighting/capabilities'),
  getStatus: () => api.get('/structured-lighting/status'),
  startWorker: (payload) => api.post('/structured-lighting/worker/start', payload),
  stopWorker: () => api.post('/structured-lighting/worker/stop'),
  confirmWorkerReady: (workerId) => api.post(`/structured-lighting/worker/${workerId}/confirm-ready`),
  listSessions: () => api.get('/structured-lighting/sessions'),
  createSession: (payload) => api.post('/structured-lighting/sessions', payload),
  deleteSession: (sessionId) => api.delete(`/structured-lighting/sessions/${sessionId}`),
  getCapturePlan: (sessionId) => api.get(`/structured-lighting/sessions/${sessionId}/capture-plan`),
  getRuntime: (sessionId) => api.get(`/structured-lighting/sessions/${sessionId}/runtime`),
  listCaptures: (sessionId) => api.get(`/structured-lighting/sessions/${sessionId}/captures`),
  decodeSession: (sessionId, payload = {}) => api.post(`/structured-lighting/sessions/${sessionId}/decode`, payload),
  getCalibration: (sessionId) => api.get(`/structured-lighting/sessions/${sessionId}/calibration`),
  getArtifactReview: (sessionId) => api.get(`/structured-lighting/sessions/${sessionId}/artifacts/review`),
  updateReview: (sessionId, payload) => api.post(`/structured-lighting/sessions/${sessionId}/review`, payload),
  startSession: (sessionId) => api.post(`/structured-lighting/sessions/${sessionId}/start`),
  getStepImageUrl: (sessionId, stepIndex) => `/api/structured-lighting/sessions/${sessionId}/steps/${stepIndex}/image`,
  getArtifactPreviewUrl: (sessionId, previewId) => `/api/structured-lighting/sessions/${sessionId}/artifacts/previews/${previewId}`,
  getExportUrl: (sessionId) => `/api/structured-lighting/sessions/${sessionId}/export`,
};

// Video API
const videoApi = {
  getVideos: (params = {}) => api.get('/videos/', { params }),
  getVideo: (id) => api.get(`/videos/${id}`),
  createVideo: (data) => api.post('/videos/', data),
  updateVideo: (id, data) => api.put(`/videos/${id}`, data),
  deleteVideo: (id) => api.delete(`/videos/${id}`),
  uploadVideo: (formData, config = {}) => api.post('/videos/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 300000, // 5 minutes timeout for large uploads
    ...config
  }),
  streamVideo: (id, serveIp) => 
    api.post(`/videos/${id}/stream`, null, { params: { serve_ip: serveIp } }),
  scanDirectory: (directory, category = 'background', sourceDirectoryId = null) => 
    api.post('/videos/scan-directory', null, { params: { directory, category, source_directory_id: sourceDirectoryId } }),
};

const photoApi = {
  getPhotos: (params = {}) => api.get('/photos/', { params }),
  getPhoto: (id) => api.get(`/photos/${id}`),
  createPhoto: (data) => api.post('/photos/', data),
  updatePhoto: (id, data) => api.put(`/photos/${id}`, data),
  deletePhoto: (id) => api.delete(`/photos/${id}`),
  uploadPhoto: (formData, config = {}) => api.post('/photos/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 300000,
    ...config,
  }),
  scanDirectory: (directory, category = 'background', sourceDirectoryId = null) =>
    api.post('/photos/scan-directory', null, { params: { directory, category, source_directory_id: sourceDirectoryId } }),
};

const mappingsApi = {
  listScenes: () => api.get('/mappings/scenes'),
  getScene: (id) => api.get(`/mappings/scenes/${id}`),
  createScene: (data) => api.post('/mappings/scenes', data),
  updateScene: (id, data) => api.put(`/mappings/scenes/${id}`, data),
  deleteScene: (id) => api.delete(`/mappings/scenes/${id}`),
  createPolygonMask: (id, data) => api.post(`/mappings/scenes/${id}/masks/polygon`, data),
  uploadMasks: (id, formData) => api.post(`/mappings/scenes/${id}/masks/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  }),
  deleteMask: (sceneId, maskId) => api.delete(`/mappings/scenes/${sceneId}/masks/${maskId}`),
};

const mediaLibraryApi = {
  listDirectories: () => api.get('/media-library/directories'),
  createDirectory: (data) => api.post('/media-library/directories', data),
  updateDirectory: (id, data) => api.put(`/media-library/directories/${id}`, data),
  deleteDirectory: (id) => api.delete(`/media-library/directories/${id}`),
  scanDirectory: (id) => api.post(`/media-library/directories/${id}/scan`),
  listMediaLists: () => api.get('/media-library/lists'),
  createMediaList: (data) => api.post('/media-library/lists', data),
  updateMediaList: (id, data) => api.put(`/media-library/lists/${id}`, data),
  deleteMediaList: (id) => api.delete(`/media-library/lists/${id}`),
  listMediaChannels: () => api.get('/media-library/channels'),
  createMediaChannel: (data) => api.post('/media-library/channels', data),
  updateMediaChannel: (id, data) => api.put(`/media-library/channels/${id}`, data),
  advanceMediaChannel: (id) => api.post(`/media-library/channels/${id}/advance`),
  deleteMediaChannel: (id) => api.delete(`/media-library/channels/${id}`),
};

const photoListApi = {
  listPhotoLists: () => api.get('/photo-lists/'),
  createPhotoList: (data) => api.post('/photo-lists/', data),
  updatePhotoList: (id, data) => api.put(`/photo-lists/${id}`, data),
  deletePhotoList: (id) => api.delete(`/photo-lists/${id}`),
};

// Renderer API
const rendererApi = {
  startRenderer: (scene, projector, options = {}) => 
    api.post('/renderer/start', { scene, projector, options }),
  stopRenderer: (projector) => 
    api.post('/renderer/stop', { projector }),
  pauseRenderer: (projectorId) => 
    api.post(`/renderer/pause/${projectorId}`),
  resumeRenderer: (projectorId) => 
    api.post(`/renderer/resume/${projectorId}`),
  getRendererStatus: (projectorId) => 
    api.get(`/renderer/status/${projectorId}`),
  listRenderers: () => 
    api.get('/renderer/list'),
  listProjectors: () => 
    api.get('/renderer/projectors'),
  listScenes: () => 
    api.get('/renderer/scenes'),
  startProjector: (projectorId) => 
    api.post('/renderer/start_projector', null, { params: { projector_id: projectorId } }),
  // AirPlay discovery endpoints
  discoverAirPlayDevices: () => 
    api.get('/renderer/airplay/discover'),
  listAirPlayDevices: () => 
    api.get('/renderer/airplay/list'),
  getAllAirPlayDevices: () => 
    api.get('/renderer/airplay/devices'),
};

// Depth Processing API
const depthApi = {
  uploadDepthMap: (formData) => 
    api.post('/depth/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }),
  previewDepthMap: (depthId) => 
    `/api/depth/preview/${depthId}`,
  segmentDepthMap: (depthId, segmentationParams) => 
    api.post(`/depth/segment/${depthId}`, segmentationParams),
  previewSegmentation: (depthId, alpha = 0.5) => 
    `/api/depth/segmentation_preview/${depthId}?alpha=${alpha}`,
  exportMasks: (depthId, segmentIds, cleanMask = true, minArea = 100, kernelSize = 3) => 
    api.post(`/depth/export_masks/${depthId}`, { segment_ids: segmentIds, clean_mask: cleanMask, min_area: minArea, kernel_size: kernelSize }),
  deleteDepthMap: (depthId) => 
    api.delete(`/depth/${depthId}`),
  getMask: (depthId, segmentId, clean = true, minArea = 100, kernelSize = 3) => 
    `/api/depth/mask/${depthId}/${segmentId}?clean=${clean}&min_area=${minArea}&kernel_size=${kernelSize}`,
  createProjection: (config) => 
    api.post('/depth/projection/create', config),
  getProjection: (configId) => 
    `/api/depth/projection/${configId}`,
  deleteProjection: (configId) => 
    api.delete(`/depth/projection/${configId}`),
};

// Streaming API
const streamingApi = {
  getStreamingStats: () => api.get('/streaming/'),
  startStreaming: (deviceId, videoPath) => 
    api.post('/streaming/start', { device_id: deviceId, video_path: videoPath }),
  getSessions: () => api.get('/streaming/sessions'),
  getSession: (sessionId) => api.get(`/streaming/sessions/${sessionId}`),
  deleteSession: (sessionId) => api.delete(`/streaming/sessions/${sessionId}`),
  getSessionsForDevice: (deviceName) => api.get(`/streaming/device/${deviceName}`),
  completeSession: (sessionId) => api.post(`/streaming/sessions/${sessionId}/complete`),
  resetSession: (sessionId) => api.post(`/streaming/sessions/${sessionId}/reset`),
  getStreamingAnalytics: () => api.get('/streaming/analytics'),
  getStreamingHealth: () => api.get('/streaming/health'),
};

// Settings API (placeholder for future implementation)
const settingsApi = {
  getSettings: () => Promise.resolve({ 
    autoDiscoverDevices: true,
    defaultVideoDirectory: '/tmp/nanodlna/uploads',
    enableLogging: true,
    logLevel: 'info',
    serverPort: 8000,
    enableSubtitles: true
  }),
  updateSettings: (settings) => Promise.resolve(settings),
};

export { 
  api, 
  deviceApi, 
  videoApi, 
  photoApi,
  mappingsApi,
  mediaLibraryApi,
  photoListApi,
  rendererApi, 
  depthApi, 
  streamingApi, 
  settingsApi,
  discoveryV2Api,
  overlayApi,
  structuredLightingApi,
};
