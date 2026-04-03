import { useCallback, useEffect, useMemo, useState } from 'react';

import { NanoDlnaApiClient } from '../../services/api';
import type {
  MediaChannelSummary,
  MediaDirectorySummary,
  MediaListSummary,
  PhotoSummary,
  VideoSummary,
} from '../../types/api';

export interface MediaController {
  actionMessage: string | null;
  channels: MediaChannelSummary[];
  directories: MediaDirectorySummary[];
  error: string | null;
  lists: MediaListSummary[];
  loading: boolean;
  photos: PhotoSummary[];
  playingVideoId: number | string | null;
  videos: VideoSummary[];
  load: () => Promise<void>;
  playVideo: (videoId: number | string) => Promise<void>;
}

interface UseMediaControllerOptions {
  selectedDeviceId: number | string | null;
}

export function useMediaController(
  client: NanoDlnaApiClient,
  options: UseMediaControllerOptions,
): MediaController {
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [photos, setPhotos] = useState<PhotoSummary[]>([]);
  const [directories, setDirectories] = useState<MediaDirectorySummary[]>([]);
  const [lists, setLists] = useState<MediaListSummary[]>([]);
  const [channels, setChannels] = useState<MediaChannelSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [playingVideoId, setPlayingVideoId] = useState<number | string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        videosPayload,
        photosPayload,
        directoriesPayload,
        listsPayload,
        channelsPayload,
      ] = await Promise.all([
        client.listVideos(),
        client.listPhotos(),
        client.listMediaDirectories(),
        client.listMediaLists(),
        client.listMediaChannels(),
      ]);

      setVideos(videosPayload);
      setPhotos(photosPayload);
      setDirectories(directoriesPayload);
      setLists(listsPayload);
      setChannels(channelsPayload);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load media inventory.');
    } finally {
      setLoading(false);
    }
  }, [client]);

  const playVideo = useCallback(
    async (videoId: number | string) => {
      if (options.selectedDeviceId === null || options.selectedDeviceId === undefined) {
        setError('Select a device in the Devices tab before starting playback.');
        return;
      }

      setPlayingVideoId(videoId);
      setError(null);
      setActionMessage(null);
      try {
        const response = await client.playVideoOnDevice(options.selectedDeviceId, videoId);
        setActionMessage(response.message ?? 'Playback started.');
      } catch (playError) {
        setError(playError instanceof Error ? playError.message : 'Failed to start playback.');
      } finally {
        setPlayingVideoId(null);
      }
    },
    [client, options.selectedDeviceId],
  );

  useEffect(() => {
    void load();
  }, [load]);

  return useMemo(
    () => ({
      actionMessage,
      channels,
      directories,
      error,
      lists,
      load,
      loading,
      photos,
      playVideo,
      playingVideoId,
      videos,
    }),
    [
      actionMessage,
      channels,
      directories,
      error,
      lists,
      load,
      loading,
      photos,
      playVideo,
      playingVideoId,
      videos,
    ],
  );
}
