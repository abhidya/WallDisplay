import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import StructuredLighting from '../pages/StructuredLighting';
import { discoveryV2Api, structuredLightingApi } from '../services/api';

jest.mock('../services/api', () => ({
  structuredLightingApi: {
      getCapabilities: jest.fn(),
      getStatus: jest.fn(),
      getHdmiPreflight: jest.fn(),
      startWorker: jest.fn(),
      listSessions: jest.fn(),
    createSession: jest.fn(),
    getCapturePlan: jest.fn(),
    getRuntime: jest.fn(),
    listCaptures: jest.fn(),
    getArtifactReview: jest.fn(),
    getPreviewTuning: jest.fn(),
    getTuningSearch: jest.fn(),
  },
  discoveryV2Api: {
    triggerDiscovery: jest.fn(),
    getDevices: jest.fn(),
  },
}));

const renderStructuredLighting = () => render(
  <BrowserRouter>
    <StructuredLighting />
  </BrowserRouter>
);

describe('StructuredLighting HDMI workflow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    structuredLightingApi.getCapabilities.mockResolvedValue({
      data: {
        presentation_modes: [
          { id: 'dlna_step', label: 'DLNA Step' },
          { id: 'hdmi_step', label: 'HDMI Step' },
        ],
        pattern_sets: [
          { id: 'gray_code', label: 'Gray Code' },
          { id: 'calibration', label: 'Calibration' },
          { id: 'grid', label: 'Grid' },
          { id: 'checkerboard', label: 'Checkerboard' },
        ],
        workflow: [],
      },
    });
    structuredLightingApi.getStatus.mockResolvedValue({
      data: {
        worker: { state: 'stopped', process_state: 'stopped', message: 'Worker stopped.' },
        summary: {
          total_sessions: 0,
          active_sessions: 0,
          total_planned_frames: 0,
          total_estimated_capture_seconds: 0,
        },
      },
    });
    structuredLightingApi.getHdmiPreflight.mockResolvedValue({
      data: {
        status: 'ready',
        checks: [
          { id: 'display', label: 'HDMI display target', status: 'ok', detail: 'DISPLAY5 3840x2160 at 3840,0' },
        ],
        recommended_worker: {
          base_url: 'http://localhost',
          camera_index: 1,
          projector_screen_x: 3840,
          projector_screen_y: 0,
          projector_width: 3840,
          projector_height: 2160,
          settle_seconds: 1,
          flush_count: 30,
          pump_ms: 400,
          poll_seconds: 1,
          min_frame_delta: 0,
          max_capture_attempts: 1,
        },
        recommended_session: {
          projector_device_id: 'proj-hdmi-local',
          presentation_mode: 'hdmi_step',
          camera_index: 1,
          projector_width: 3840,
          projector_height: 2160,
          pattern_set: 'gray_code',
          hold_ms: 1200,
        },
      },
    });
    structuredLightingApi.startWorker.mockResolvedValue({ data: {} });
    structuredLightingApi.listSessions.mockResolvedValue({ data: [] });
    structuredLightingApi.createSession.mockResolvedValue({ data: {} });
    structuredLightingApi.getCapturePlan.mockResolvedValue({
      data: {
        session: { session_id: 'session-1', pattern_set: 'gray_code' },
        summary: {
          pattern_set: 'gray_code',
          total_frames: 0,
          graycode_frames: 0,
          reference_frames: 0,
          estimated_capture_seconds: 0,
        },
        steps: [],
      },
    });
    structuredLightingApi.getRuntime.mockResolvedValue({
      data: {
        session: { session_id: 'session-1', status: 'draft', pattern_set: 'gray_code' },
        worker: { state: 'stopped' },
        progress: { captured_frames: 0, remaining_frames: 0, current_step_index: 0 },
        current_step: null,
      },
    });
    structuredLightingApi.listCaptures.mockResolvedValue({
      data: { captured_frames: 0, expected_frames: 0, captures: [] },
    });
    structuredLightingApi.getArtifactReview.mockResolvedValue({
      data: { review: { status: 'pending' }, previews: [] },
    });
    structuredLightingApi.getPreviewTuning.mockResolvedValue({ data: { status: 'not_started', candidates: [] } });
    structuredLightingApi.getTuningSearch.mockResolvedValue({ data: { status: 'not_started', candidates: [] } });
    discoveryV2Api.triggerDiscovery.mockResolvedValue({ data: {} });
    discoveryV2Api.getDevices.mockImplementation((params = {}) => {
      if (params.casting_method === 'hdmi') {
        return Promise.resolve({
          data: [
            {
              id: 'proj-hdmi-local',
              name: 'proj-hdmi-local',
              friendly_name: 'Local HDMI Projector',
              casting_method: 'hdmi',
              resolution: [1920, 1080],
            },
          ],
        });
      }
      return Promise.resolve({ data: [] });
    });
  });

  test('selecting an HDMI projector creates an HDMI Step session', async () => {
    renderStructuredLighting();

    const projectorSelect = await screen.findByLabelText('Projector');
    fireEvent.mouseDown(projectorSelect);
    fireEvent.click(await screen.findByRole('option', { name: /local hdmi projector/i }));
    await waitFor(() => expect(structuredLightingApi.getHdmiPreflight).toHaveBeenCalledWith(
      expect.objectContaining({ projector_id: 'proj-hdmi-local' })
    ));
    await screen.findByText(/HDMI preflight: ready/i);

    fireEvent.click(screen.getByRole('button', { name: /create session/i }));

    await waitFor(() =>
      expect(structuredLightingApi.createSession).toHaveBeenCalledWith(
        expect.objectContaining({
          projector_device_id: 'proj-hdmi-local',
          presentation_mode: 'hdmi_step',
          pattern_set: 'gray_code',
          projector_width: 3840,
          projector_height: 2160,
        })
      )
    );
    await waitFor(() => expect(structuredLightingApi.listSessions).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(structuredLightingApi.getStatus).toHaveBeenCalledTimes(2));
  });

  test('HDMI preflight defaults are used to start the worker', async () => {
    renderStructuredLighting();

    const projectorSelect = await screen.findByLabelText('Projector');
    fireEvent.mouseDown(projectorSelect);
    fireEvent.click(await screen.findByRole('option', { name: /local hdmi projector/i }));

    await screen.findByText(/HDMI preflight: ready/i);
    fireEvent.click(screen.getByRole('button', { name: /start worker/i }));

    await waitFor(() =>
      expect(structuredLightingApi.startWorker).toHaveBeenCalledWith(
        expect.objectContaining({
          base_url: window.location.origin,
          projector_screen_x: 3840,
          projector_screen_y: 0,
          projector_width: 3840,
          projector_height: 2160,
          min_frame_delta: 0,
          max_capture_attempts: 1,
        })
      )
    );
  });
});
