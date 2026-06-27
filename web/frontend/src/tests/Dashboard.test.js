import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Dashboard from '../pages/Dashboard';
import { deviceApi, videoApi } from '../services/api';

jest.mock('../services/api', () => ({
  deviceApi: {
    getDevices: jest.fn(),
    pauseVideo: jest.fn(),
    stopVideo: jest.fn(),
  },
  videoApi: {
    getVideos: jest.fn(),
  },
}));

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

const renderDashboard = () => render(
  <BrowserRouter>
    <Dashboard />
  </BrowserRouter>
);

const devices = [
  {
    id: 1,
    friendly_name: 'Projector A',
    status: 'connected',
    type: 'dlna',
    is_playing: true,
  },
  {
    id: 2,
    friendly_name: 'Projector B',
    status: 'idle',
    type: 'airplay',
    is_playing: false,
  },
];

const videos = [
  {
    id: 7,
    name: 'Reef Loop',
    duration: 125,
  },
];

describe('Dashboard user workflow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    deviceApi.getDevices.mockResolvedValue({ data: { devices } });
    videoApi.getVideos.mockResolvedValue({ data: { videos } });
    deviceApi.pauseVideo.mockResolvedValue({ data: { ok: true } });
    deviceApi.stopVideo.mockResolvedValue({ data: { ok: true } });
  });

  test('loads dashboard summaries from the shared API service', async () => {
    renderDashboard();

    expect(await screen.findByText('Projector A')).toBeInTheDocument();
    expect(screen.getByText('Projector B')).toBeInTheDocument();
    expect(screen.getByText('Reef Loop')).toBeInTheDocument();
    expect(deviceApi.getDevices).toHaveBeenCalledTimes(1);
    expect(videoApi.getVideos).toHaveBeenCalledTimes(1);
  });

  test('quick action buttons route to primary workflows', async () => {
    renderDashboard();
    await screen.findByText('Projector A');

    fireEvent.click(screen.getByRole('button', { name: /view all devices/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/devices');

    fireEvent.click(screen.getByRole('button', { name: /^add$/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/videos/add');
  });

  test('pauses a playing device and refreshes the dashboard state', async () => {
    renderDashboard();
    await screen.findByText('Projector A');

    fireEvent.click(screen.getByRole('button', { name: /pause projector a/i }));

    await waitFor(() => expect(deviceApi.pauseVideo).toHaveBeenCalledWith(1));
    await waitFor(() => expect(deviceApi.getDevices).toHaveBeenCalledTimes(2));
  });

  test('does not show pause for playing HDMI devices', async () => {
    deviceApi.getDevices.mockResolvedValue({
      data: {
        devices: [
          {
            id: 6,
            friendly_name: 'HDMI Projector',
            name: 'proj-hdmi-local',
            status: 'connected',
            type: 'hdmi',
            casting_method: 'hdmi',
            is_playing: true,
          },
        ],
      },
    });
    videoApi.getVideos.mockResolvedValue({ data: { videos: [] } });

    renderDashboard();
    await screen.findByText('HDMI Projector');

    expect(screen.queryByRole('button', { name: /pause hdmi projector/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /stop hdmi projector/i }));
    await waitFor(() => expect(deviceApi.stopVideo).toHaveBeenCalledWith(6));
    await waitFor(() => expect(deviceApi.getDevices).toHaveBeenCalledTimes(2));
  });

  test('shows a retry state when the dashboard cannot load', async () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    deviceApi.getDevices.mockRejectedValueOnce(new Error('Network error'));

    renderDashboard();

    expect(await screen.findByText('Retry')).toBeInTheDocument();
    expect(screen.getByText(/failed to load data/i)).toBeInTheDocument();

    errorSpy.mockRestore();
  });
});
