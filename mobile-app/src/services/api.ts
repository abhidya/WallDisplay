import type {
  DeviceSummary,
  HealthResponse,
  JsonRecord,
  StreamingAnalytics,
  VideoSummary,
} from '../types/api';

const rawDefaultBaseUrl =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000/api';

export const DEFAULT_API_BASE_URL = normalizeApiBaseUrl(rawDefaultBaseUrl);

function ensureApiSuffix(pathname: string): string {
  const trimmed = pathname.replace(/\/+$/, '');
  if (trimmed.endsWith('/api')) {
    return trimmed;
  }
  return `${trimmed}/api`;
}

export function normalizeApiBaseUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return DEFAULT_API_BASE_URL;
  }

  if (/^https?:\/\//i.test(trimmed)) {
    const url = new URL(trimmed);
    url.pathname = ensureApiSuffix(url.pathname || '');
    url.search = '';
    url.hash = '';
    return url.toString().replace(/\/+$/, '');
  }

  if (trimmed.startsWith('/')) {
    return ensureApiSuffix(trimmed);
  }

  return normalizeApiBaseUrl(`http://${trimmed}`);
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text.trim()) {
    return {} as T;
  }

  return JSON.parse(text) as T;
}

function asArray<T>(value: unknown): T[] {
  if (Array.isArray(value)) {
    return value as T[];
  }
  return [];
}

export class NanoDlnaApiClient {
  readonly apiBaseUrl: string;
  readonly rootBaseUrl: string;

  constructor(apiBaseUrl: string) {
    this.apiBaseUrl = normalizeApiBaseUrl(apiBaseUrl);
    this.rootBaseUrl = this.apiBaseUrl.replace(/\/api$/, '');
  }

  private async requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.apiBaseUrl}${path}`, {
      headers: {
        Accept: 'application/json',
        ...(init?.headers ?? {}),
      },
      ...init,
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(
        `${response.status} ${response.statusText}${body ? ` - ${body}` : ''}`.trim(),
      );
    }

    return parseJson<T>(response);
  }

  async getHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.rootBaseUrl}/health`, {
      headers: { Accept: 'application/json' },
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(
        `${response.status} ${response.statusText}${body ? ` - ${body}` : ''}`.trim(),
      );
    }

    return parseJson<HealthResponse>(response);
  }

  async listDevices(): Promise<DeviceSummary[]> {
    const payload = await this.requestJson<unknown>('/devices');
    if (Array.isArray(payload)) {
      return payload as DeviceSummary[];
    }
    if (payload && typeof payload === 'object') {
      const record = payload as JsonRecord;
      return asArray<DeviceSummary>(record.devices);
    }
    return [];
  }

  async discoverDevices(timeoutSeconds = 5): Promise<JsonRecord> {
    return this.requestJson<JsonRecord>(`/devices/discover?timeout=${timeoutSeconds}`, {
      method: 'POST',
    });
  }

  async listVideos(): Promise<VideoSummary[]> {
    const payload = await this.requestJson<unknown>('/videos');
    if (Array.isArray(payload)) {
      return payload as VideoSummary[];
    }
    if (payload && typeof payload === 'object') {
      const record = payload as JsonRecord;
      return asArray<VideoSummary>(record.videos);
    }
    return [];
  }

  async getStreamingAnalytics(): Promise<StreamingAnalytics> {
    return this.requestJson<StreamingAnalytics>('/streaming/analytics');
  }
}
