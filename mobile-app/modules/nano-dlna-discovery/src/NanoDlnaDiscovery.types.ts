export interface DiscoveryServiceRecord {
  id: string;
  name: string;
  serviceType: string;
  domain: string;
  hostName?: string;
  port?: number;
  addresses?: string[];
  txtRecord?: Record<string, string>;
}

export interface DiscoveryRequest {
  serviceTypes: string[];
  timeoutMs?: number;
}

export interface DiscoveryResponse {
  services: DiscoveryServiceRecord[];
  startedAt: string;
  finishedAt: string;
  notes?: string[];
}
