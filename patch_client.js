const fs = require('fs');

const path = 'mobile-app/src/control-plane/client.ts';
let code = fs.readFileSync(path, 'utf-8');

const interfaceAdditions = `
  duplicateOverlayConfig(configId: number | string): Promise<OverlayConfigSummary>;
  createOverlayStream(payload: JsonRecord): Promise<JsonRecord>;
  getOverlayWindowInit(projectorId?: string): Promise<JsonRecord>;
  getOverlayWindowRefreshState(projectorId?: string): Promise<JsonRecord>;
  getOverlayWidgetData(projectorId?: string): Promise<JsonRecord>;
  heartbeatProjectorClient(payload: JsonRecord): Promise<JsonRecord>;
  getOverlayPlaybackSync(projectorId?: string): Promise<JsonRecord>;
  getBrightnessStatus(): Promise<JsonRecord>;
  getOverlayEventsUrl(): string;
  createProjectionSession(payload: JsonRecord): Promise<ProjectionSessionSummary>;
  deleteProjectionSession(sessionId: string): Promise<JsonRecord>;
  uploadProjectionMask(formData: FormData): Promise<JsonRecord>;
  getProjectionMask(maskId: string): Promise<JsonRecord>;
  getProjectionMaskImageUrl(sessionId: string): string;
  importCodepenAnimation(payload: JsonRecord): Promise<JsonRecord>;
  startStructuredLightingWorker(payload: JsonRecord): Promise<JsonRecord>;
  stopStructuredLightingWorker(): Promise<JsonRecord>;
  confirmStructuredLightingWorkerReady(workerId: string): Promise<JsonRecord>;
  decodeStructuredLightingSession(sessionId: string, payload?: JsonRecord): Promise<JsonRecord>;
  runStructuredLightingPreviewTuning(sessionId: string, payload?: JsonRecord): Promise<JsonRecord>;
  getStructuredLightingPreviewTuning(sessionId: string): Promise<JsonRecord>;
  runStructuredLightingTuningSearch(sessionId: string, payload?: JsonRecord): Promise<JsonRecord>;
  getStructuredLightingTuningSearch(sessionId: string): Promise<JsonRecord>;
  getStructuredLightingCalibration(sessionId: string): Promise<JsonRecord>;
  getStructuredLightingArtifactReview(sessionId: string): Promise<JsonRecord>;
  updateStructuredLightingReview(sessionId: string, payload: JsonRecord): Promise<JsonRecord>;
  publishStructuredLightingMappingScene(sessionId: string, payload?: JsonRecord): Promise<JsonRecord>;
  getStructuredLightingStepImageUrl(sessionId: string, stepIndex: number | string): string;
  getStructuredLightingCaptureImageUrl(sessionId: string, stepIndex: number | string): string;
  getStructuredLightingArtifactPreviewUrl(sessionId: string, previewId: string): string;
  getStructuredLightingPreviewTuningPreviewUrl(sessionId: string, candidateId: string, previewName: string): string;
  getStructuredLightingTuningSearchPreviewUrl(sessionId: string, candidateId: string, previewName: string): string;
  getStructuredLightingExportUrl(sessionId: string): string;
  uploadStructuredLightingCapture(sessionId: string, formData: FormData): Promise<JsonRecord>;
`;

const remoteAdditions = `
  duplicateOverlayConfig(configId: number | string) { return this.client.duplicateOverlayConfig(configId); }
  createOverlayStream(payload: JsonRecord) { return this.client.createOverlayStream(payload); }
  getOverlayWindowInit(projectorId?: string) { return this.client.getOverlayWindowInit(projectorId); }
  getOverlayWindowRefreshState(projectorId?: string) { return this.client.getOverlayWindowRefreshState(projectorId); }
  getOverlayWidgetData(projectorId?: string) { return this.client.getOverlayWidgetData(projectorId); }
  heartbeatProjectorClient(payload: JsonRecord) { return this.client.heartbeatProjectorClient(payload); }
  getOverlayPlaybackSync(projectorId?: string) { return this.client.getOverlayPlaybackSync(projectorId); }
  getBrightnessStatus() { return this.client.getBrightnessStatus(); }
  getOverlayEventsUrl() { return this.client.getOverlayEventsUrl(); }
  createProjectionSession(payload: JsonRecord) { return this.client.createProjectionSession(payload); }
  deleteProjectionSession(sessionId: string) { return this.client.deleteProjectionSession(sessionId); }
  uploadProjectionMask(formData: FormData) { return this.client.uploadProjectionMask(formData); }
  getProjectionMask(maskId: string) { return this.client.getProjectionMask(maskId); }
  getProjectionMaskImageUrl(sessionId: string) { return this.client.getProjectionMaskImageUrl(sessionId); }
  importCodepenAnimation(payload: JsonRecord) { return this.client.importCodepenAnimation(payload); }
  startStructuredLightingWorker(payload: JsonRecord) { return this.client.startStructuredLightingWorker(payload); }
  stopStructuredLightingWorker() { return this.client.stopStructuredLightingWorker(); }
  confirmStructuredLightingWorkerReady(workerId: string) { return this.client.confirmStructuredLightingWorkerReady(workerId); }
  decodeStructuredLightingSession(sessionId: string, payload?: JsonRecord) { return this.client.decodeStructuredLightingSession(sessionId, payload); }
  runStructuredLightingPreviewTuning(sessionId: string, payload?: JsonRecord) { return this.client.runStructuredLightingPreviewTuning(sessionId, payload); }
  getStructuredLightingPreviewTuning(sessionId: string) { return this.client.getStructuredLightingPreviewTuning(sessionId); }
  runStructuredLightingTuningSearch(sessionId: string, payload?: JsonRecord) { return this.client.runStructuredLightingTuningSearch(sessionId, payload); }
  getStructuredLightingTuningSearch(sessionId: string) { return this.client.getStructuredLightingTuningSearch(sessionId); }
  getStructuredLightingCalibration(sessionId: string) { return this.client.getStructuredLightingCalibration(sessionId); }
  getStructuredLightingArtifactReview(sessionId: string) { return this.client.getStructuredLightingArtifactReview(sessionId); }
  updateStructuredLightingReview(sessionId: string, payload: JsonRecord) { return this.client.updateStructuredLightingReview(sessionId, payload); }
  publishStructuredLightingMappingScene(sessionId: string, payload?: JsonRecord) { return this.client.publishStructuredLightingMappingScene(sessionId, payload); }
  getStructuredLightingStepImageUrl(sessionId: string, stepIndex: number | string) { return this.client.getStructuredLightingStepImageUrl(sessionId, stepIndex); }
  getStructuredLightingCaptureImageUrl(sessionId: string, stepIndex: number | string) { return this.client.getStructuredLightingCaptureImageUrl(sessionId, stepIndex); }
  getStructuredLightingArtifactPreviewUrl(sessionId: string, previewId: string) { return this.client.getStructuredLightingArtifactPreviewUrl(sessionId, previewId); }
  getStructuredLightingPreviewTuningPreviewUrl(sessionId: string, candidateId: string, previewName: string) { return this.client.getStructuredLightingPreviewTuningPreviewUrl(sessionId, candidateId, previewName); }
  getStructuredLightingTuningSearchPreviewUrl(sessionId: string, candidateId: string, previewName: string) { return this.client.getStructuredLightingTuningSearchPreviewUrl(sessionId, candidateId, previewName); }
  getStructuredLightingExportUrl(sessionId: string) { return this.client.getStructuredLightingExportUrl(sessionId); }
  uploadStructuredLightingCapture(sessionId: string, formData: FormData) { return this.client.uploadStructuredLightingCapture(sessionId, formData); }
`;

const localAdditions = `
  async duplicateOverlayConfig(_configId: number | string): Promise<OverlayConfigSummary> {
    await this.recordDeferredFeature('Overlay config duplication deferred', 'Remains remote-only in local mode.');
    return makeDeferredResult('Duplication deferred') as unknown as OverlayConfigSummary;
  }
  async createOverlayStream(_payload: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Overlay stream deferred'); }
  async getOverlayWindowInit(_projectorId?: string): Promise<JsonRecord> { return makeDeferredResult('Overlay window init deferred'); }
  async getOverlayWindowRefreshState(_projectorId?: string): Promise<JsonRecord> { return makeDeferredResult('Overlay window state deferred'); }
  async getOverlayWidgetData(_projectorId?: string): Promise<JsonRecord> { return makeDeferredResult('Overlay widget data deferred'); }
  async heartbeatProjectorClient(_payload: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Overlay heartbeat deferred'); }
  async getOverlayPlaybackSync(_projectorId?: string): Promise<JsonRecord> { return makeDeferredResult('Overlay playback sync deferred'); }
  async getBrightnessStatus(): Promise<JsonRecord> { return makeDeferredResult('Overlay brightness status deferred'); }
  getOverlayEventsUrl(): string { return this.buildLocalFeatureUrl('/overlay/events'); }

  async createProjectionSession(_payload: JsonRecord): Promise<ProjectionSessionSummary> {
    return makeDeferredResult('Projection session deferred') as unknown as ProjectionSessionSummary;
  }
  async deleteProjectionSession(_sessionId: string): Promise<JsonRecord> { return makeDeferredResult('Projection session deferred'); }
  async uploadProjectionMask(_formData: FormData): Promise<JsonRecord> { return makeDeferredResult('Projection mask upload deferred'); }
  async getProjectionMask(_maskId: string): Promise<JsonRecord> { return makeDeferredResult('Projection mask deferred'); }
  getProjectionMaskImageUrl(sessionId: string): string { return this.buildLocalFeatureUrl('/projection/masks/' + sessionId + '/image'); }
  async importCodepenAnimation(_payload: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Codepen import deferred'); }

  async startStructuredLightingWorker(_payload: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting worker deferred'); }
  async stopStructuredLightingWorker(): Promise<JsonRecord> { return makeDeferredResult('Structured lighting worker deferred'); }
  async confirmStructuredLightingWorkerReady(_workerId: string): Promise<JsonRecord> { return makeDeferredResult('Structured lighting worker deferred'); }
  async decodeStructuredLightingSession(_sessionId: string, _payload?: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting decode deferred'); }
  async runStructuredLightingPreviewTuning(_sessionId: string, _payload?: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting tuning deferred'); }
  async getStructuredLightingPreviewTuning(_sessionId: string): Promise<JsonRecord> { return makeDeferredResult('Structured lighting tuning deferred'); }
  async runStructuredLightingTuningSearch(_sessionId: string, _payload?: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting tuning deferred'); }
  async getStructuredLightingTuningSearch(_sessionId: string): Promise<JsonRecord> { return makeDeferredResult('Structured lighting tuning deferred'); }
  async getStructuredLightingCalibration(_sessionId: string): Promise<JsonRecord> { return makeDeferredResult('Structured lighting calibration deferred'); }
  async getStructuredLightingArtifactReview(_sessionId: string): Promise<JsonRecord> { return makeDeferredResult('Structured lighting artifact review deferred'); }
  async updateStructuredLightingReview(_sessionId: string, _payload: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting review deferred'); }
  async publishStructuredLightingMappingScene(_sessionId: string, _payload?: JsonRecord): Promise<JsonRecord> { return makeDeferredResult('Structured lighting publish mapping deferred'); }
  getStructuredLightingStepImageUrl(sessionId: string, stepIndex: number | string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/steps/' + stepIndex + '/image'); }
  getStructuredLightingCaptureImageUrl(sessionId: string, stepIndex: number | string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/captures/' + stepIndex + '/image'); }
  getStructuredLightingArtifactPreviewUrl(sessionId: string, previewId: string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/artifacts/previews/' + previewId); }
  getStructuredLightingPreviewTuningPreviewUrl(sessionId: string, candidateId: string, previewName: string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/preview-tuning/' + candidateId + '/previews/' + previewName); }
  getStructuredLightingTuningSearchPreviewUrl(sessionId: string, candidateId: string, previewName: string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/tuning-search/' + candidateId + '/previews/' + previewName); }
  getStructuredLightingExportUrl(sessionId: string): string { return this.buildLocalFeatureUrl('/structured-lighting/sessions/' + sessionId + '/export'); }
  async uploadStructuredLightingCapture(_sessionId: string, _formData: FormData): Promise<JsonRecord> { return makeDeferredResult('Structured lighting capture upload deferred'); }
`;

// 1. Insert into ControlPlaneClient
code = code.replace(
  '  listDeferredFeatures(): Promise<DeferredFeatureSummary[]>;\n}',
  '  listDeferredFeatures(): Promise<DeferredFeatureSummary[]>;\n' + interfaceAdditions + '}'
);

// 2. Insert into RemoteControlPlaneAdapter
code = code.replace(
  '  async listDeferredFeatures(): Promise<DeferredFeatureSummary[]> {\n    return [];\n  }\n}',
  '  async listDeferredFeatures(): Promise<DeferredFeatureSummary[]> {\n    return [];\n  }\n' + remoteAdditions + '}'
);

// 3. Insert into LocalControlPlaneClient
code = code.replace(
  '  async listDeferredFeatures(): Promise<DeferredFeatureSummary[]> {\n    const state = await loadLocalControlPlaneState();\n    return state.deferredFeatures;\n  }\n}',
  '  async listDeferredFeatures(): Promise<DeferredFeatureSummary[]> {\n    const state = await loadLocalControlPlaneState();\n    return state.deferredFeatures;\n  }\n' + localAdditions + '}'
);

fs.writeFileSync(path, code);
console.log('Patched client.ts successfully');
