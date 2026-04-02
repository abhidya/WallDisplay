export interface FeatureCardData {
  title: string;
  description: string;
  endpoints: string[];
}

export const currentProductAreas: FeatureCardData[] = [
  {
    title: 'Device discovery and control',
    description:
      'Discover DLNA and related casting targets, inspect state, and control playback.',
    endpoints: ['/api/devices', '/api/devices/discover', '/api/v2/discovery'],
  },
  {
    title: 'Media library',
    description:
      'Browse indexed videos, uploads, photos, and device-linked playback metadata.',
    endpoints: ['/api/videos', '/api/photos', '/api/media-library'],
  },
  {
    title: 'Streaming diagnostics',
    description:
      'Track session health, bandwidth, active streams, and runtime log events.',
    endpoints: ['/api/streaming', '/api/logs', '/health'],
  },
  {
    title: 'Renderer and overlay workflows',
    description:
      'Coordinate AirPlay/renderer targets, overlay casting, mapping scenes, and projection.',
    endpoints: ['/api/renderer', '/api/overlay', '/api/mappings', '/api/projection'],
  },
];

export const mobileRewritePrinciples: string[] = [
  'Keep the rewrite isolated in mobile-app/ and leave the current React dashboard intact.',
  'Treat FastAPI as the source of truth for devices, streaming, media, and diagnostics.',
  'Expose operator-first screens before recreating advanced projection authoring UIs.',
  'Use the same API groups the web app already relies on so the backend stays shared.',
];

export const mobileModules: FeatureCardData[] = [
  {
    title: 'Overview',
    description:
      'Architecture summary, existing platform capabilities, and rewrite boundaries.',
    endpoints: ['/api/devices', '/api/videos', '/api/streaming'],
  },
  {
    title: 'Devices',
    description:
      'Live device inventory and discovery actions for playback-capable targets.',
    endpoints: ['/api/devices', '/api/devices/discover'],
  },
  {
    title: 'Media',
    description: 'Video-library oriented shell for media browsing and upcoming playback flows.',
    endpoints: ['/api/videos', '/api/media-library'],
  },
  {
    title: 'Operations',
    description:
      'Renderer, overlay, mapping, projection, and streaming analytics planning surface.',
    endpoints: ['/api/streaming/analytics', '/api/overlay', '/api/renderer'],
  },
];

export const emulatorConnectionNotes = [
  'iOS simulator can usually reach a local backend at http://127.0.0.1:8000/api.',
  'Android emulator usually needs http://10.0.2.2:8000/api.',
  'A physical device should use your Mac or backend host LAN IP, not localhost.',
  'You can override the base URL with EXPO_PUBLIC_API_BASE_URL before starting Expo.',
];
