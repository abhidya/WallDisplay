import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import SceneControl from '../pages/SceneControl';
import {
  api,
  discoveryV2Api,
  mappingsApi,
  mediaLibraryApi,
  photoApi,
  photoListApi,
  projectionApi,
  rendererApi,
  videoApi,
} from '../services/api';

jest.mock('../services/api', () => ({
  api: {
    get: jest.fn(),
    post: jest.fn(),
  },
  discoveryV2Api: {
    getDevices: jest.fn(),
  },
  mappingsApi: {
    listScenes: jest.fn(),
    getScene: jest.fn(),
    updateScene: jest.fn(),
    listRanks: jest.fn(),
    createRank: jest.fn(),
    updateRank: jest.fn(),
    listSceneControlPresets: jest.fn(),
    getSceneControlPreset: jest.fn(),
    createSceneControlPreset: jest.fn(),
    updateSceneControlPreset: jest.fn(),
    deleteSceneControlPreset: jest.fn(),
    projectScene: jest.fn(),
    stopSceneProjection: jest.fn(),
  },
  mediaLibraryApi: {
    listDirectories: jest.fn(),
    listMediaLists: jest.fn(),
    listMediaChannels: jest.fn(),
  },
  photoApi: {
    getPhotos: jest.fn(),
  },
  photoListApi: {
    listPhotoLists: jest.fn(),
  },
  projectionApi: {
    listAnimations: jest.fn(),
    listAnimationLists: jest.fn(),
  },
  rendererApi: {
    listProjectors: jest.fn(),
  },
  videoApi: {
    getVideos: jest.fn(),
  },
}));

const scene = {
  id: 1,
  name: 'Kitchen Scene',
  canvas_width: 1280,
  canvas_height: 720,
  mask_mode: 'luminance',
  masks: [],
  groups: [],
  render_settings: {},
};

function mockWorkspace({ projectors = [], devices = [] } = {}) {
  jest.clearAllMocks();
  window.localStorage.clear();
  mappingsApi.listScenes.mockResolvedValue({ data: [scene] });
  mappingsApi.getScene.mockResolvedValue({ data: scene });
  mappingsApi.listRanks.mockResolvedValue({ data: [] });
  mappingsApi.listSceneControlPresets.mockResolvedValue({ data: [] });
  videoApi.getVideos.mockResolvedValue({ data: { videos: [] } });
  photoApi.getPhotos.mockResolvedValue({ data: { photos: [] } });
  mediaLibraryApi.listDirectories.mockResolvedValue({ data: [] });
  mediaLibraryApi.listMediaLists.mockResolvedValue({ data: [] });
  mediaLibraryApi.listMediaChannels.mockResolvedValue({ data: [] });
  photoListApi.listPhotoLists.mockResolvedValue({ data: [] });
  projectionApi.listAnimations.mockResolvedValue({ data: { animations: [] } });
  projectionApi.listAnimationLists.mockResolvedValue({ data: { animation_lists: [] } });
  rendererApi.listProjectors.mockResolvedValue({ data: { data: { projectors } } });
  discoveryV2Api.getDevices.mockResolvedValue({ data: { data: { devices } } });
  api.get.mockResolvedValue({ data: { brightness: 100 } });
  api.post.mockResolvedValue({ data: { brightness: 75 } });
}

describe('SceneControl projection runtime', () => {
  test('launches a selected mapping scene to HDMI through the scene projection API', async () => {
    mockWorkspace({
      projectors: [{ id: 'proj-hdmi-local', name: 'Local HDMI', sender: 'hdmi', target_name: 'hdmi_display_0' }],
    });
    mappingsApi.projectScene.mockResolvedValue({
      data: {
        status: 'launched',
        transport: 'hdmi',
        target_id: 'proj-hdmi-local',
        scene_id: 1,
      },
    });

    render(<SceneControl />);

    const launchButton = await screen.findByRole('button', { name: /^launch$/i });
    await waitFor(() => expect(launchButton).not.toBeDisabled());
    fireEvent.click(launchButton);

    expect(await screen.findByText('Launched scene on Local HDMI.')).toBeInTheDocument();
    await waitFor(() => {
      expect(mappingsApi.projectScene).toHaveBeenCalledWith(1, {
        target_type: 'hdmi',
        target_id: 'proj-hdmi-local',
        overlay_base_url: expect.stringMatching(/^http/),
        controls_hidden: true,
      });
    });
  });

  test('launches DLNA through the same API and stops by cast session id', async () => {
    mockWorkspace({
      devices: [{ id: 'dlna-living-room', friendly_name: 'Living Room TV', hostname: '10.0.0.24' }],
    });
    mappingsApi.projectScene.mockResolvedValue({
      data: {
        status: 'launched',
        transport: 'dlna',
        target_id: 'dlna-living-room',
        scene_id: 1,
        cast_session: { session_id: 'cast-session-1' },
      },
    });
    mappingsApi.stopSceneProjection.mockResolvedValue({ data: { status: 'stopped' } });

    render(<SceneControl />);

    const launchButton = await screen.findByRole('button', { name: /^launch$/i });
    await waitFor(() => expect(launchButton).not.toBeDisabled());
    fireEvent.click(launchButton);

    expect(await screen.findByText('Launched scene on Living Room TV.')).toBeInTheDocument();
    await waitFor(() => {
      expect(mappingsApi.projectScene).toHaveBeenCalledWith(1, expect.objectContaining({
        target_type: 'dlna',
        target_id: 'dlna-living-room',
      }));
    });

    const stopButton = screen.getByRole('button', { name: /^stop$/i });
    await waitFor(() => expect(stopButton).not.toBeDisabled());
    fireEvent.click(stopButton);

    expect(await screen.findByText('Stopped scene projection.')).toBeInTheDocument();
    await waitFor(() => {
      expect(mappingsApi.stopSceneProjection).toHaveBeenCalledWith({
        target_type: 'dlna',
        target_id: 'cast-session-1',
      });
    });
  });
});
