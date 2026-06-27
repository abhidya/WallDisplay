import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import DeviceDetail from '../pages/DeviceDetail';
import { deviceApi } from '../services/api';

jest.mock('../services/api', () => ({
  deviceApi: {
    getDevice: jest.fn(),
    pauseVideo: jest.fn(),
    stopVideo: jest.fn(),
  },
}));

const renderDeviceDetail = () => render(
  <MemoryRouter initialEntries={['/devices/6']}>
    <Routes>
      <Route path="/devices/:id" element={<DeviceDetail />} />
    </Routes>
  </MemoryRouter>
);

describe('DeviceDetail HDMI controls', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    deviceApi.getDevice.mockResolvedValue({
      data: {
        id: 6,
        name: 'proj-hdmi-local',
        friendly_name: 'HDMI Projector',
        type: 'hdmi',
        casting_method: 'hdmi',
        hostname: '\\\\.\\DISPLAY5',
        status: 'connected',
        availability: 'online',
        manager_status: 'connected',
        is_playing: true,
        current_video: 'http://127.0.0.1:8088/backend-static/hdmi_video_player.html',
        seconds_since_seen: 0,
        reconnect_count: 0,
        degraded_count: 0,
        offline_count: 0,
        active_overlay_cast: false,
        hdmi_target_name: '\\\\.\\DISPLAY5',
        hdmi_connection_state: 'attached',
        hdmi_projection_state: 'projecting',
        hdmi_power_state: 'manual_on',
        config: {
          casting_method: 'hdmi',
          managed_by: 'renderer_config',
          renderer_projector_id: 'proj-hdmi-local',
        },
      },
    });
  });

  test('shows HDMI state and hides unsupported pause action', async () => {
    renderDeviceDetail();

    expect(await screen.findByText('HDMI Projector')).toBeInTheDocument();
    expect(screen.getByText('HDMI Projection')).toBeInTheDocument();
    expect(screen.getByText('projecting')).toBeInTheDocument();
    expect(screen.getByText('HDMI Target')).toBeInTheDocument();
    expect(screen.getAllByText('\\\\.\\DISPLAY5').length).toBeGreaterThan(0);
    expect(screen.getByText('HDMI Connection')).toBeInTheDocument();
    expect(screen.getByText('attached')).toBeInTheDocument();
    expect(screen.getByText('HDMI Power')).toBeInTheDocument();
    expect(screen.getByText('manual_on')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /pause/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /stop/i })).toBeInTheDocument();
  });
});
