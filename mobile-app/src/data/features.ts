export interface FeatureCardData {
  title: string;
  description: string;
  endpoints: string[];
}

export const currentProductAreas: FeatureCardData[] = [
  {
    title: 'Device discovery and control',
    description:
      'Local-first device inventory, saved profiles, and direct control workflows with remote fallback available during migration.',
    endpoints: ['local://devices', 'local://discovery', '/api/devices'],
  },
  {
    title: 'Media inventory',
    description:
      'On-device media state, bundled samples, and playback initiation against the selected target.',
    endpoints: ['local://media', 'local://media/channels', '/api/videos'],
  },
  {
    title: 'Diagnostics and action history',
    description:
      'Control-plane health, recent actions, active sessions, and operator-facing local diagnostics.',
    endpoints: ['local://health', 'local://history', '/health'],
  },
  {
    title: 'Deferred advanced operations',
    description:
      'Renderer, overlay, mapping, and projection flows remain explicitly deferred until a mobile-safe design is approved.',
    endpoints: ['local://deferred/renderer', '/api/renderer', '/api/projection'],
  },
];

export const mobileRewritePrinciples: string[] = [
  'Keep the rewrite isolated in mobile-app/ and leave the current React dashboard intact.',
  'Default to an on-device control plane so the app stays useful with no backend running.',
  'Expose operator-first local workflows before recreating advanced renderer or receiver features.',
  'Keep one shared seam that can switch between local mode and the FastAPI remote adapter.',
];

export const mobileModules: FeatureCardData[] = [
  {
    title: 'Overview',
    description:
      'Local-vs-remote control-plane summary, runtime health, and rewrite boundaries.',
    endpoints: ['local://health', 'local://capabilities', '/health'],
  },
  {
    title: 'Devices',
    description:
      'Local device inventory, saved profiles, discovery refresh, and direct playback controls.',
    endpoints: ['local://devices', 'local://discovery', '/api/devices'],
  },
  {
    title: 'Media',
    description:
      'Local media inventory, bundled samples, and playback initiation against the selected target.',
    endpoints: ['local://media', 'local://media/channels', '/api/videos'],
  },
  {
    title: 'Operations',
    description:
      'Reduced local-safe diagnostics, capability matrix, action history, and explicit deferred advanced features.',
    endpoints: ['local://history', 'local://capabilities', '/api/streaming/analytics'],
  },
];

export const emulatorConnectionNotes = [
  'Local mode requires no backend server and is the default control-plane path for this rewrite.',
  'iOS simulator can usually reach a remote fallback backend at http://127.0.0.1:8000/api.',
  'Android emulator usually needs http://10.0.2.2:8000/api for remote fallback.',
  'A physical device should use your Mac or backend host LAN IP, not localhost, when testing remote mode.',
];
