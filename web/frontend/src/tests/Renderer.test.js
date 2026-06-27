import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Renderer from '../pages/Renderer';
import { rendererApi } from '../services/api';

jest.mock('../services/api', () => ({
  rendererApi: {
    listProjectors: jest.fn(),
    listScenes: jest.fn(),
    listRenderers: jest.fn(),
    listHdmiDisplays: jest.fn(),
    setProjectorTarget: jest.fn(),
    startProjectorMode: jest.fn(),
    identifyProjector: jest.fn(),
    setProjectorPowerState: jest.fn(),
    stopRenderer: jest.fn(),
    startRenderer: jest.fn(),
    pauseRenderer: jest.fn(),
    resumeRenderer: jest.fn(),
    getRendererStatus: jest.fn(),
    startProjector: jest.fn(),
    discoverAirPlayDevices: jest.fn(),
    listAirPlayDevices: jest.fn(),
    getAllAirPlayDevices: jest.fn(),
  },
}));

const renderRenderer = () => render(
  <BrowserRouter>
    <Renderer />
  </BrowserRouter>
);

const hdmiProjector = {
  id: 'proj-hdmi-local',
  name: 'Local HDMI Projector',
  sender: 'hdmi',
  target_name: 'hdmi_display_0',
  content_modes: ['identify', 'overlay', 'blank', 'scene'],
  runtime_status: {
    status: 'idle',
    sender_status: {
      type: 'hdmi',
      connection_state: 'attached',
      projection_state: 'idle',
      power_state: 'unknown',
    },
  },
};

const hdmiDisplay = {
  id: 'hdmi_display_0',
  index: 0,
  name: 'Primary display',
  x: 0,
  y: 0,
  width: 1920,
  height: 1080,
  is_primary: true,
  attached: true,
};

describe('Renderer HDMI panel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    rendererApi.listProjectors.mockResolvedValue({
      data: { data: { projectors: [hdmiProjector] } },
    });
    rendererApi.listScenes.mockResolvedValue({
      data: { data: { scenes: [{ id: 'blank', name: 'Blank' }] } },
    });
    rendererApi.listRenderers.mockResolvedValue({
      data: { data: { renderers: [] } },
    });
    rendererApi.listHdmiDisplays.mockResolvedValue({
      data: { data: { displays: [hdmiDisplay] } },
    });
    rendererApi.setProjectorTarget.mockResolvedValue({ data: { success: true } });
    rendererApi.startProjectorMode.mockResolvedValue({ data: { success: true } });
    rendererApi.setProjectorPowerState.mockResolvedValue({ data: { success: true } });
  });

  test('loads display targets and sends HDMI control actions', async () => {
    renderRenderer();

    expect(await screen.findByText(/connection: attached/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /save target/i }));
    await waitFor(() =>
      expect(rendererApi.setProjectorTarget).toHaveBeenCalledWith('proj-hdmi-local', 'hdmi_display_0')
    );

    const startModeButton = screen.getByRole('button', { name: /start mode/i });
    await waitFor(() => expect(startModeButton).not.toBeDisabled());
    fireEvent.click(startModeButton);
    await waitFor(() =>
      expect(rendererApi.startProjectorMode).toHaveBeenCalledWith(
        'proj-hdmi-local',
        'blank',
        expect.objectContaining({
          background_color: 'black',
        })
      )
    );

    const markOffButton = screen.getByRole('button', { name: /mark off/i });
    await waitFor(() => expect(markOffButton).not.toBeDisabled());
    fireEvent.click(markOffButton);
    await waitFor(() =>
      expect(rendererApi.setProjectorPowerState).toHaveBeenCalledWith('proj-hdmi-local', 'manual_off')
    );
    await waitFor(() => expect(rendererApi.listProjectors).toHaveBeenCalledTimes(4));
  });
});
