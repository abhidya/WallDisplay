import type { JsonRecord } from '../../types/api.ts';

export type CaptureStepStatus = 'pending' | 'captured' | 'uploaded' | 'failed';

export interface StructuredLightingCaptureStep {
  index: number;
  label: string;
  imageUrl?: string;
  status: CaptureStepStatus;
  localUri?: string;
  uploadedAt?: string;
  error?: string;
}

export interface StructuredLightingCaptureState {
  sessionId: string;
  planVersion?: string;
  steps: StructuredLightingCaptureStep[];
  currentStepIndex?: number;
  startedAt?: string;
  updatedAt?: string;
}

export interface StructuredLightingCaptureFile {
  uri: string;
  name?: string;
  type?: string;
  blob?: Blob;
}

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

function asStepRecords(payload: JsonRecord): JsonRecord[] {
  const candidates = [payload.steps, payload.capture_steps, asRecord(payload.plan)?.steps];
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate.filter((item): item is JsonRecord => Boolean(asRecord(item)));
    }
  }
  return [];
}

function asStepIndex(step: JsonRecord, fallback: number): number {
  const raw = step.index ?? step.step_index ?? step.sequence ?? fallback;
  const numeric = typeof raw === 'number' ? raw : Number(raw);
  return Number.isFinite(numeric) ? numeric : fallback;
}

export function normalizeCapturePlan(
  sessionId: string,
  payload: JsonRecord,
  existingCaptures: JsonRecord[] = [],
): StructuredLightingCaptureState {
  const uploadedSteps = new Set(
    existingCaptures
      .map((capture) => capture.step_index ?? capture.index ?? capture.step)
      .filter((value) => value !== null && value !== undefined)
      .map(String),
  );
  const planRecord = asRecord(payload.plan);
  const steps = asStepRecords(payload).map((step, fallbackIndex) => {
    const index = asStepIndex(step, fallbackIndex);
    const uploaded = uploadedSteps.has(String(index));
    return {
      index,
      label: String(step.label ?? step.name ?? step.pattern ?? `Step ${index}`),
      imageUrl: typeof step.image_url === 'string' ? step.image_url : undefined,
      status: uploaded ? 'uploaded' as const : 'pending' as const,
      uploadedAt: uploaded ? String(step.uploaded_at ?? '') || undefined : undefined,
    };
  });

  return {
    sessionId,
    planVersion: String(payload.plan_version ?? planRecord?.version ?? '') || undefined,
    steps,
    currentStepIndex: steps.find((step) => step.status !== 'uploaded')?.index ?? steps[0]?.index,
    updatedAt: new Date().toISOString(),
  };
}

export function markStepCaptured(
  state: StructuredLightingCaptureState,
  stepIndex: number,
  localUri: string,
): StructuredLightingCaptureState {
  const steps = state.steps.map((step) =>
    step.index === stepIndex
      ? { ...step, status: 'captured' as const, localUri, error: undefined }
      : step,
  );
  return { ...state, steps, currentStepIndex: stepIndex, updatedAt: new Date().toISOString() };
}

export function markStepUploaded(
  state: StructuredLightingCaptureState,
  stepIndex: number,
): StructuredLightingCaptureState {
  const uploadedAt = new Date().toISOString();
  const steps = state.steps.map((step) =>
    step.index === stepIndex
      ? { ...step, status: 'uploaded' as const, uploadedAt, error: undefined }
      : step,
  );
  const currentStepIndex = steps.find((step) => step.status !== 'uploaded')?.index ?? stepIndex;
  return { ...state, steps, currentStepIndex, updatedAt: uploadedAt };
}

export function markStepFailed(
  state: StructuredLightingCaptureState,
  stepIndex: number,
  error: string,
): StructuredLightingCaptureState {
  const steps = state.steps.map((step) =>
    step.index === stepIndex ? { ...step, status: 'failed' as const, error } : step,
  );
  return { ...state, steps, currentStepIndex: stepIndex, updatedAt: new Date().toISOString() };
}


export function getSafeCapturePathSegment(value: string): string {
  return value.replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'capture';
}

export function getPersistedCaptureFileName(
  sessionId: string,
  stepIndex: number,
  uri: string,
  fallbackName?: string,
): string {
  const baseName = getCaptureFileName(stepIndex, uri, fallbackName);
  return `${getSafeCapturePathSegment(sessionId)}-step-${stepIndex}-${getSafeCapturePathSegment(baseName)}`;
}

export function getCaptureFileName(stepIndex: number, uri: string, fallbackName?: string): string {
  if (fallbackName) {
    return fallbackName;
  }

  const cleanUri = uri.split('?')[0]?.split('#')[0] ?? '';
  const basename = cleanUri.split('/').filter(Boolean).pop();
  return basename && basename.includes('.')
    ? basename
    : `structured-lighting-step-${stepIndex}.jpg`;
}

export function buildStructuredLightingCaptureFormData(
  stepIndex: number,
  file: StructuredLightingCaptureFile,
): FormData {
  const formData = new FormData();
  formData.append('step_index', String(stepIndex));
  if (file.blob) {
    formData.append('file', file.blob, file.name ?? `structured-lighting-step-${stepIndex}.jpg`);
    return formData;
  }

  formData.append('file', {
    uri: file.uri,
    name: getCaptureFileName(stepIndex, file.uri, file.name),
    type: file.type ?? 'image/jpeg',
  } as unknown as Blob);
  return formData;
}
