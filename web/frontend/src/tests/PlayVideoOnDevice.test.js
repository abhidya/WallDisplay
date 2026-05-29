import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import PlayVideoOnDevice, { isPlayableDeviceStatus } from '../pages/PlayVideoOnDevice';
import { deviceApi, videoApi } from '../services/api';

jest.mock('../services/api', () => ({
  deviceApi: {
    getDevices: jest.fn(),
    playVideo: jest.fn(),
  },
  videoApi: {
    getVideo: jest.fn(),
  },
}));

const renderPlayVideo = () => render(
  <MemoryRouter initialEntries={['/videos/7/play']}>
    <Routes>
      <Route path="/videos/:id/play" element={<PlayVideoOnDevice />} />
    </Routes>
  </MemoryRouter>
);

describe('isPlayableDeviceStatus', () => {
  test.each([
    [{ status: 'connected' }],
    [{ status: 'online' }],
    [{ derived_status: 'ready' }],
    [{ availability: 'available', status: 'offline' }],
    [{ status: 'connected', availability: 'offline' }],
    [{ status: 'connected', derived_status: 'degraded' }],
  ])('accepts playable status shape %#', (device) => {
    expect(isPlayableDeviceStatus(device)).toBe(true);
  });

  test.each([
    [{ status: 'offline' }],
    [{ status: 'disconnected' }],
    [{ availability: 'unavailable' }],
    [{}],
  ])('rejects non-playable status shape %#', (device) => {
    expect(isPlayableDeviceStatus(device)).toBe(false);
  });
});

describe('PlayVideoOnDevice workflow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    videoApi.getVideo.mockResolvedValue({
      data: { id: 7, name: 'Reef Loop', duration: 125, format: 'mp4' },
    });
    deviceApi.playVideo.mockResolvedValue({ data: { ok: true } });
  });

  test('keeps legacy connected devices playable even when derived availability is offline', async () => {
    deviceApi.getDevices.mockResolvedValue({
      data: {
        devices: [
          {
            id: 3,
            friendly_name: 'Legacy Projector',
            status: 'connected',
            availability: 'offline',
            type: 'dlna',
            hostname: 'projector.local',
          },
        ],
      },
    });

    renderPlayVideo();

    expect(await screen.findByText('Legacy Projector')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /play on selected device/i }));

    await waitFor(() => expect(deviceApi.playVideo).toHaveBeenCalledWith(3, '7', true, false));
    expect(await screen.findByText(/playing reef loop on legacy projector/i)).toBeInTheDocument();
  });

  test('shows a no-playable-device warning when every device is unavailable', async () => {
    deviceApi.getDevices.mockResolvedValue({
      data: {
        devices: [
          {
            id: 4,
            friendly_name: 'Offline Projector',
            status: 'offline',
            availability: 'unavailable',
            type: 'dlna',
          },
        ],
      },
    });

    renderPlayVideo();

    expect(await screen.findByText(/no playable devices available/i)).toBeInTheDocument();
    expect(screen.queryByText('Offline Projector')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /play on selected device/i })).toBeDisabled();
  });
});
