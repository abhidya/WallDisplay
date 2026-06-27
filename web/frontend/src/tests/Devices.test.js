import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Devices from '../pages/Devices';
import { deviceApi } from '../services/api';

jest.mock('../services/api', () => ({
  deviceApi: {
    getDevices: jest.fn(),
    getDiscoveryStatus: jest.fn(),
    setDiscoveryInterval: jest.fn(),
    pauseDiscovery: jest.fn(),
    resumeDiscovery: jest.fn(),
    enableAutoMode: jest.fn(),
    createDevice: jest.fn(),
    deleteDevice: jest.fn(),
    discoverDevices: jest.fn(),
    stopVideo: jest.fn(),
    pauseVideo: jest.fn(),
  },
}));

const renderDevices = () => render(
  <BrowserRouter>
    <Devices />
  </BrowserRouter>
);

const devices = [
  {
    id: 1,
    name: 'tranScreen-83924',
    friendly_name: 'tranScreen-83924',
    type: 'transcreen',
    status: 'disconnected',
    availability: 'offline',
    is_playing: false,
    seconds_since_seen: 900,
    reconnect_count: 0,
    degraded_count: 0,
    offline_count: 1,
    hostname: '10.0.0.45',
    config: { casting_method: 'transcreen' },
  },
  {
    id: 2,
    name: 'proj-hdmi-local',
    friendly_name: 'HDMI Projector',
    type: 'hdmi',
    casting_method: 'hdmi',
    status: 'connected',
    manager_status: 'connected',
    availability: 'online',
    is_playing: true,
    current_video: 'http://127.0.0.1:8088/backend-static/hdmi_video_player.html',
    seconds_since_seen: 0,
    reconnect_count: 0,
    degraded_count: 0,
    offline_count: 0,
    hostname: '\\\\.\\DISPLAY5',
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
];

describe('Devices HDMI dashboard card', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    deviceApi.getDevices.mockResolvedValue({ data: { devices } });
    deviceApi.getDiscoveryStatus.mockResolvedValue({ data: { running: true, interval: 10 } });
  });

  test('renders local HDMI projector state from the Devices API', async () => {
    renderDevices();

    const heading = await screen.findByText('HDMI Projector');
    const card = heading.closest('.MuiCard-root');

    expect(within(card).getByText('Type: hdmi')).toBeInTheDocument();
    expect(within(card).getByText('projecting')).toBeInTheDocument();
    expect(within(card).getByText('local HDMI')).toBeInTheDocument();
    expect(within(card).getByText('attached')).toBeInTheDocument();
    expect(within(card).getByText('power: manual_on')).toBeInTheDocument();
    expect(within(card).getByText(/Target: \\\\.\\DISPLAY5/)).toBeInTheDocument();
    expect(within(card).getByText('managed')).toBeInTheDocument();
    expect(within(card).queryByRole('button', { name: /pause/i })).not.toBeInTheDocument();
    expect(within(card).getByRole('button', { name: /stop/i })).toBeInTheDocument();
  });

  test('filters the device list by HDMI casting method', async () => {
    renderDevices();

    expect(await screen.findByText('tranScreen-83924')).toBeInTheDocument();

    const castingMethodControl = screen.getAllByText('Casting Method')[0].closest('.MuiFormControl-root');
    fireEvent.mouseDown(within(castingMethodControl).getByRole('combobox'));
    fireEvent.click(await screen.findByRole('option', { name: 'HDMI' }));

    await waitFor(() => expect(screen.queryByText('tranScreen-83924')).not.toBeInTheDocument());
    expect(screen.getByText('HDMI Projector')).toBeInTheDocument();
  });
});
