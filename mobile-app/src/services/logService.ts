import type { JsonRecord } from '../types/api.ts';
import { normalizeApiBaseUrl } from './httpClient.ts';

export type LogLevel = 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';

export interface FrontendLogEntry extends JsonRecord {
  level: LogLevel;
  message: string;
  component: string;
  filename: string;
  line_number: number;
  timestamp: number;
  stack?: string;
  extra_data?: JsonRecord;
  user_agent?: string;
  url?: string;
}

export interface FrontendLogPayload extends JsonRecord {
  logs: FrontendLogEntry[];
  session_id: string;
  timestamp: number;
}

export interface FrontendLogServiceOptions {
  backendUrl?: string;
  batchSize?: number;
  flushIntervalMs?: number;
  fetchImpl?: typeof fetch;
  captureConsole?: boolean;
  autoStart?: boolean;
  online?: boolean;
  consoleRef?: Pick<Console, 'log' | 'warn' | 'error' | 'info' | 'debug'>;
  sessionId?: string;
  userAgent?: string;
  appUrl?: string;
}

type ConsoleMethod = (...args: unknown[]) => void;

type ConsoleLike = Pick<Console, 'log' | 'warn' | 'error' | 'info' | 'debug'>;

function deriveBackendUrl(value?: string): string {
  const normalized = normalizeApiBaseUrl(
    value ?? process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000/api',
  );
  return normalized.replace(/\/api$/, '');
}

function createSessionId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function asJsonRecord(value: unknown): JsonRecord {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : {};
}

function formatConsoleArgument(value: unknown): string {
  if (typeof value === 'string') {
    return value;
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function extractStackLocation(stack: string | undefined): { filename: string; lineNumber: number } {
  if (!stack) {
    return { filename: 'unknown', lineNumber: 0 };
  }

  const lines = stack.split('\n');
  for (const line of lines.slice(2)) {
    const match = line.match(/([^/\\s]+):(\d+):(\d+)/);
    if (match) {
      return {
        filename: match[1],
        lineNumber: Number(match[2]),
      };
    }
  }

  return { filename: 'unknown', lineNumber: 0 };
}

export class FrontendLogService {
  readonly backendUrl: string;
  readonly batchSize: number;
  readonly flushIntervalMs: number;
  private readonly fetchImpl?: typeof fetch;
  private readonly consoleRef: ConsoleLike;
  private readonly sessionId: string;
  private readonly userAgent: string;
  private readonly appUrl: string;
  private readonly originalConsole: Record<keyof ConsoleLike, ConsoleMethod>;
  private readonly logQueue: FrontendLogEntry[] = [];
  private isOnline: boolean;
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private consoleCaptureEnabled = false;

  constructor(options: FrontendLogServiceOptions = {}) {
    this.backendUrl = deriveBackendUrl(options.backendUrl);
    this.batchSize = options.batchSize ?? 10;
    this.flushIntervalMs = options.flushIntervalMs ?? 5_000;
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch;
    this.consoleRef = options.consoleRef ?? console;
    this.sessionId = options.sessionId ?? createSessionId();
    this.userAgent = options.userAgent ?? 'expo-mobile-app';
    this.appUrl = options.appUrl ?? 'mobile-app://session';
    this.isOnline = options.online ?? true;
    this.originalConsole = {
      log: this.consoleRef.log.bind(this.consoleRef),
      warn: this.consoleRef.warn.bind(this.consoleRef),
      error: this.consoleRef.error.bind(this.consoleRef),
      info: this.consoleRef.info.bind(this.consoleRef),
      debug: this.consoleRef.debug.bind(this.consoleRef),
    };

    if (options.autoStart !== false) {
      this.startBatchProcessor();
    }

    if (options.captureConsole) {
      this.setupConsoleCapture();
    }
  }

  getSessionId(): string {
    return this.sessionId;
  }

  getQueueSize(): number {
    return this.logQueue.length;
  }

  setOnline(online: boolean): void {
    this.isOnline = online;
  }

  setupConsoleCapture(): void {
    if (this.consoleCaptureEnabled) {
      return;
    }

    this.consoleRef.log = (...args: unknown[]) => {
      this.originalConsole.log(...args);
      this.captureConsoleLog('INFO', args);
    };

    this.consoleRef.warn = (...args: unknown[]) => {
      this.originalConsole.warn(...args);
      this.captureConsoleLog('WARNING', args);
    };

    this.consoleRef.error = (...args: unknown[]) => {
      this.originalConsole.error(...args);
      this.captureConsoleLog('ERROR', args);
    };

    this.consoleRef.info = (...args: unknown[]) => {
      this.originalConsole.info(...args);
      this.captureConsoleLog('INFO', args);
    };

    this.consoleRef.debug = (...args: unknown[]) => {
      this.originalConsole.debug(...args);
      this.captureConsoleLog('DEBUG', args);
    };

    this.consoleCaptureEnabled = true;
  }

  private captureConsoleLog(level: LogLevel, args: unknown[]): void {
    const message = args.map(formatConsoleArgument).join(' ');
    const stack = new Error().stack;
    const location = extractStackLocation(stack);

    this.addLogEntry({
      level,
      message,
      component: 'console',
      filename: location.filename,
      line_number: location.lineNumber,
      stack: level === 'ERROR' ? stack : undefined,
    });
  }

  startBatchProcessor(): void {
    if (this.flushTimer || this.flushIntervalMs <= 0) {
      return;
    }

    this.flushTimer = setInterval(() => {
      if (this.logQueue.length > 0) {
        void this.flushLogs();
      }
    }, this.flushIntervalMs);

    const unref = (this.flushTimer as { unref?: () => void }).unref;
    unref?.call(this.flushTimer);
  }

  stopBatchProcessor(): void {
    if (!this.flushTimer) {
      return;
    }
    clearInterval(this.flushTimer);
    this.flushTimer = null;
  }

  addLogEntry(logData: Omit<FrontendLogEntry, 'timestamp' | 'user_agent' | 'url'> & { timestamp?: number }): void {
    const entry: FrontendLogEntry = {
      ...(logData as FrontendLogEntry),
      timestamp: logData.timestamp ?? Date.now() / 1000,
      user_agent: this.userAgent,
      url: this.appUrl,
    };

    this.logQueue.push(entry);

    if (entry.level === 'ERROR' || this.logQueue.length >= this.batchSize) {
      void this.flushLogs();
    }
  }

  async flushLogs(): Promise<boolean> {
    if (this.logQueue.length === 0 || !this.isOnline || typeof this.fetchImpl !== 'function') {
      return false;
    }

    const logsToSend = [...this.logQueue];
    this.logQueue.splice(0, this.logQueue.length);

    try {
      const response = await this.fetchImpl(`${this.backendUrl}/api/logs/frontend`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          logs: logsToSend,
          session_id: this.sessionId,
          timestamp: Date.now() / 1000,
        } satisfies FrontendLogPayload),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return true;
    } catch (error) {
      this.logQueue.unshift(...logsToSend);
      this.originalConsole.error('Failed to send logs to backend:', error);
      return false;
    }
  }

  logInfo(message: string, data: JsonRecord = {}): void {
    const extra = asJsonRecord(data);
    this.addLogEntry({
      level: 'INFO',
      message,
      component: String(extra.component ?? 'app'),
      filename: String(extra.filename ?? 'unknown'),
      line_number: Number(extra.line_number ?? 0),
      extra_data: extra,
    });
  }

  logWarning(message: string, data: JsonRecord = {}): void {
    const extra = asJsonRecord(data);
    this.addLogEntry({
      level: 'WARNING',
      message,
      component: String(extra.component ?? 'app'),
      filename: String(extra.filename ?? 'unknown'),
      line_number: Number(extra.line_number ?? 0),
      extra_data: extra,
    });
  }

  logError(message: string, data: JsonRecord = {}): void {
    const extra = asJsonRecord(data);
    this.addLogEntry({
      level: 'ERROR',
      message,
      component: String(extra.component ?? 'app'),
      filename: String(extra.filename ?? 'unknown'),
      line_number: Number(extra.line_number ?? 0),
      stack: typeof extra.stack === 'string' ? extra.stack : undefined,
      extra_data: extra,
    });
  }

  logDebug(message: string, data: JsonRecord = {}): void {
    const extra = asJsonRecord(data);
    this.addLogEntry({
      level: 'DEBUG',
      message,
      component: String(extra.component ?? 'app'),
      filename: String(extra.filename ?? 'unknown'),
      line_number: Number(extra.line_number ?? 0),
      extra_data: extra,
    });
  }

  logComponentMount(componentName: string): void {
    this.logInfo(`Component mounted: ${componentName}`, {
      component: componentName,
      event_type: 'mount',
    });
  }

  logComponentUnmount(componentName: string): void {
    this.logInfo(`Component unmounted: ${componentName}`, {
      component: componentName,
      event_type: 'unmount',
    });
  }

  logUserAction(action: string, data: JsonRecord = {}): void {
    this.logInfo(`User action: ${action}`, {
      component: 'user_interaction',
      action,
      ...data,
    });
  }

  logApiCall(url: string, method: string, status: number, duration: number, error: string | null = null): void {
    const level: LogLevel = error ? 'ERROR' : status >= 400 ? 'WARNING' : 'INFO';
    this.addLogEntry({
      level,
      message: `API call: ${method} ${url} - ${status}${error ? ` (${error})` : ''}`,
      component: 'api',
      filename: 'api_client',
      line_number: 0,
      extra_data: {
        url,
        method,
        status,
        duration,
        error,
      },
    });
  }

  logPerformance(metric: string, value: number | string, data: JsonRecord = {}): void {
    this.logInfo(`Performance: ${metric} = ${value}`, {
      component: 'performance',
      metric,
      value,
      ...data,
    });
  }

  destroy(): void {
    this.stopBatchProcessor();

    if (this.consoleCaptureEnabled) {
      this.consoleRef.log = this.originalConsole.log;
      this.consoleRef.warn = this.originalConsole.warn;
      this.consoleRef.error = this.originalConsole.error;
      this.consoleRef.info = this.originalConsole.info;
      this.consoleRef.debug = this.originalConsole.debug;
      this.consoleCaptureEnabled = false;
    }

    void this.flushLogs();
  }
}

const logService = new FrontendLogService({ captureConsole: false });

export default logService;

export const logInfo = logService.logInfo.bind(logService);
export const logWarning = logService.logWarning.bind(logService);
export const logError = logService.logError.bind(logService);
export const logDebug = logService.logDebug.bind(logService);
export const logComponentMount = logService.logComponentMount.bind(logService);
export const logComponentUnmount = logService.logComponentUnmount.bind(logService);
export const logUserAction = logService.logUserAction.bind(logService);
export const logApiCall = logService.logApiCall.bind(logService);
export const logPerformance = logService.logPerformance.bind(logService);
