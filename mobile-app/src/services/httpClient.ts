import type { JsonRecord } from '../types/api.ts';

export type QueryScalar = string | number | boolean;
export type QueryValue = QueryScalar | QueryScalar[] | null | undefined;
export type QueryRecord = Record<string, QueryValue>;
export type ResponseParseMode = 'json' | 'text' | 'blob' | 'raw' | 'none';

type RequestBody = BodyInit | JsonRecord | unknown[] | null | undefined;

export interface HttpRequestDescriptor {
  method: string;
  url: string;
  headers: Headers;
  body: BodyInit | null;
  query?: QueryRecord;
}

export interface HttpRequestOptions extends Omit<RequestInit, 'body'> {
  query?: QueryRecord;
  body?: RequestBody;
  timeout?: number;
  parseAs?: ResponseParseMode;
}

export interface HttpClientConfig extends Omit<RequestInit, 'headers'> {
  baseURL?: string;
  headers?: HeadersInit;
  timeout?: number;
  normalizeApiBase?: boolean;
  fetchImpl?: typeof fetch;
  onRequest?: (request: HttpRequestDescriptor) => void | Promise<void>;
  onResponse?: (response: Response, request: HttpRequestDescriptor) => void | Promise<void>;
  onError?: (error: Error, request: HttpRequestDescriptor) => void | Promise<void>;
}

export interface HttpClient {
  readonly baseURL: string;
  buildUrl(path: string, query?: QueryRecord): string;
  request<T = unknown>(path: string, options?: HttpRequestOptions): Promise<T>;
  get<T = unknown>(path: string, options?: Omit<HttpRequestOptions, 'method'>): Promise<T>;
  post<T = unknown>(path: string, options?: Omit<HttpRequestOptions, 'method'>): Promise<T>;
  put<T = unknown>(path: string, options?: Omit<HttpRequestOptions, 'method'>): Promise<T>;
  delete<T = unknown>(path: string, options?: Omit<HttpRequestOptions, 'method'>): Promise<T>;
}

const rawDefaultBaseUrl =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000/api';

export const DEFAULT_HTTP_BASE_URL = normalizeApiBaseUrl(rawDefaultBaseUrl);

function ensureApiSuffix(pathname: string): string {
  const trimmed = pathname.replace(/\/+$/, '');
  if (!trimmed || trimmed === '/') {
    return '/api';
  }
  if (trimmed.endsWith('/api')) {
    return trimmed;
  }
  return `${trimmed}/api`;
}

export function normalizeApiBaseUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return DEFAULT_HTTP_BASE_URL;
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

function isBodyInitValue(value: unknown): value is BodyInit {
  if (typeof value === 'string') {
    return true;
  }

  if (typeof URLSearchParams !== 'undefined' && value instanceof URLSearchParams) {
    return true;
  }

  if (typeof FormData !== 'undefined' && value instanceof FormData) {
    return true;
  }

  if (typeof Blob !== 'undefined' && value instanceof Blob) {
    return true;
  }

  if (typeof ArrayBuffer !== 'undefined' && value instanceof ArrayBuffer) {
    return true;
  }

  return typeof ArrayBuffer !== 'undefined' && ArrayBuffer.isView(value);
}

function appendQuery(url: string, query?: QueryRecord): string {
  if (!query) {
    return url;
  }

  const search = new URLSearchParams();
  for (const [key, rawValue] of Object.entries(query)) {
    if (rawValue === undefined || rawValue === null) {
      continue;
    }

    const values = Array.isArray(rawValue) ? rawValue : [rawValue];
    for (const value of values) {
      search.append(key, String(value));
    }
  }

  const queryString = search.toString();
  if (!queryString) {
    return url;
  }

  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}${queryString.replace(/\+/g, '%20')}`;
}

function resolveUrl(baseURL: string, path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const normalizedBase = baseURL.replace(/\/+$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return encodeURI(`${normalizedBase}${normalizedPath}`);
}

function toBodyInit(body: RequestBody, headers: Headers): BodyInit | null {
  if (body === undefined || body === null) {
    return null;
  }

  if (isBodyInitValue(body)) {
    return body;
  }

  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return JSON.stringify(body);
}

async function parseResponse<T>(response: Response, parseAs: ResponseParseMode): Promise<T> {
  if (parseAs === 'raw') {
    return response as T;
  }

  if (parseAs === 'none') {
    return undefined as T;
  }

  if (parseAs === 'blob') {
    if (typeof response.blob === 'function') {
      return (await response.blob()) as T;
    }
    return (new Blob([await response.arrayBuffer()])) as T;
  }

  if (parseAs === 'text') {
    return (await response.text()) as T;
  }

  const text = await response.text();
  if (!text.trim()) {
    return {} as T;
  }

  return JSON.parse(text) as T;
}

function buildHttpError(response: Response, body: string, request: HttpRequestDescriptor): Error {
  const message = `${response.status} ${response.statusText}${body ? ` - ${body}` : ''}`.trim();
  const error = new Error(message) as Error & {
    status?: number;
    url?: string;
    method?: string;
    body?: string;
    response?: Response;
  };
  error.status = response.status;
  error.url = request.url;
  error.method = request.method;
  error.body = body;
  error.response = response;
  return error;
}

export function createHttpClient(config: HttpClientConfig = {}): HttpClient {
  const {
    baseURL = DEFAULT_HTTP_BASE_URL,
    headers: defaultHeaders = {},
    timeout: defaultTimeout = 30_000,
    normalizeApiBase = true,
    fetchImpl = globalThis.fetch,
    onRequest,
    onResponse,
    onError,
    ...defaultInit
  } = config;

  const normalizedBaseURL = normalizeApiBase ? normalizeApiBaseUrl(baseURL) : baseURL.replace(/\/+$/, '');

  return {
    baseURL: normalizedBaseURL,
    buildUrl(path: string, query?: QueryRecord): string {
      return appendQuery(resolveUrl(normalizedBaseURL, path), query);
    },
    async request<T = unknown>(path: string, options: HttpRequestOptions = {}): Promise<T> {
      if (typeof fetchImpl !== 'function') {
        throw new Error('Global fetch is unavailable. Provide fetchImpl when creating the client.');
      }

      const {
        query,
        body,
        timeout = defaultTimeout,
        parseAs = 'json',
        headers,
        method = 'GET',
        signal,
        ...requestInit
      } = options;

      const url = appendQuery(resolveUrl(normalizedBaseURL, path), query);
      const mergedHeaders = new Headers(defaultHeaders);
      if (headers) {
        new Headers(headers).forEach((value, key) => mergedHeaders.set(key, value));
      }
      if (!mergedHeaders.has('Accept')) {
        mergedHeaders.set('Accept', 'application/json');
      }

      const finalBody = toBodyInit(body, mergedHeaders);
      const abortController = !signal && timeout && timeout > 0 ? new AbortController() : null;
      const timeoutHandle = abortController
        ? setTimeout(() => abortController.abort(), timeout)
        : null;
      const request: HttpRequestDescriptor = {
        method: String(method).toUpperCase(),
        url,
        headers: mergedHeaders,
        body: finalBody,
        query,
      };

      try {
        await onRequest?.(request);

        const response = await fetchImpl(url, {
          ...defaultInit,
          ...requestInit,
          method: request.method,
          headers: mergedHeaders,
          body: finalBody,
          signal: signal ?? abortController?.signal,
        });

        await onResponse?.(response, request);

        if (!response.ok) {
          const bodyText = await response.text();
          const error = buildHttpError(response, bodyText, request);
          await onError?.(error, request);
          throw error;
        }

        return await parseResponse<T>(response, parseAs);
      } catch (error) {
        if (error instanceof Error) {
          await onError?.(error, request);
        }
        throw error;
      } finally {
        if (timeoutHandle) {
          clearTimeout(timeoutHandle);
        }
      }
    },
    get<T = unknown>(path: string, options: Omit<HttpRequestOptions, 'method'> = {}) {
      return this.request<T>(path, { ...options, method: 'GET' });
    },
    post<T = unknown>(path: string, options: Omit<HttpRequestOptions, 'method'> = {}) {
      return this.request<T>(path, { ...options, method: 'POST' });
    },
    put<T = unknown>(path: string, options: Omit<HttpRequestOptions, 'method'> = {}) {
      return this.request<T>(path, { ...options, method: 'PUT' });
    },
    delete<T = unknown>(path: string, options: Omit<HttpRequestOptions, 'method'> = {}) {
      return this.request<T>(path, { ...options, method: 'DELETE' });
    },
  };
}

export const defaultHttpClient = createHttpClient();
