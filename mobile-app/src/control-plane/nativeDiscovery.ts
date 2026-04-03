import type {
  DiscoveryRequest,
  DiscoveryResponse,
  DiscoveryServiceRecord,
} from '../../modules/nano-dlna-discovery';

export const DEFAULT_DISCOVERY_SERVICE_TYPES = [
  '_googlecast._tcp.',
  '_airplay._tcp.',
  '_raop._tcp.',
] as const;

export interface NativeDiscoveryResult extends DiscoveryResponse {
  available: boolean;
}

async function loadNativeDiscoveryModule() {
  try {
    const module = await import('../../modules/nano-dlna-discovery/index.ts');
    return module.default as {
      discoverAsync: (serviceTypes: string[], timeoutMs?: number) => Promise<DiscoveryResponse>;
    };
  } catch {
    return null;
  }
}

export async function discoverNativeServices(
  request: DiscoveryRequest = { serviceTypes: [...DEFAULT_DISCOVERY_SERVICE_TYPES] },
): Promise<NativeDiscoveryResult> {
  const module = await loadNativeDiscoveryModule();
  if (!module) {
    return {
      available: false,
      services: [],
      startedAt: new Date().toISOString(),
      finishedAt: new Date().toISOString(),
      notes: ['Native discovery module unavailable in this runtime.'],
    };
  }

  const response = await module.discoverAsync(request.serviceTypes, request.timeoutMs);
  return {
    ...response,
    available: true,
  };
}

export function classifyDiscoveryService(service: DiscoveryServiceRecord): string {
  const normalizedType = service.serviceType.toLowerCase();
  if (normalizedType.includes('googlecast')) {
    return 'google-cast';
  }
  if (normalizedType.includes('airplay')) {
    return 'airplay';
  }
  if (normalizedType.includes('raop')) {
    return 'airplay-audio';
  }
  return 'bonjour-service';
}
