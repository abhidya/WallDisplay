import { useCallback, useEffect, useMemo, useState } from 'react';

import { NanoDlnaApiClient } from '../../services/api';
import type {
  JsonRecord,
  MediaChannelSummary,
  MediaDirectorySummary,
  MediaListSummary,
  PhotoSummary,
  VideoSummary,
} from '../../types/api';

export interface MediaController {
  actionLoadingKey: string | null;
  actionMessage: string | null;
  channels: MediaChannelSummary[];
  directories: MediaDirectorySummary[];
  error: string | null;
  lists: MediaListSummary[];
  loading: boolean;
  photos: PhotoSummary[];
  playingVideoId: number | string | null;
  videos: VideoSummary[];
  advanceChannel: (channelId: number | string) => Promise<void>;
  load: () => Promise<void>;
  playVideo: (videoId: number | string) => Promise<void>;
  scanDirectory: (directoryId: number | string) => Promise<void>;
}

interface UseMediaControllerOptions {
  selectedDeviceId: number | string | null;
}

export function useMediaController(
  client: NanoDlnaApiClient,
  options: UseMediaControllerOptions,
): MediaController {
  const [actionLoadingKey, setActionLoadingKey] = useState<string | null>(null);
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [photos, setPhotos] = useState<PhotoSummary[]>([]);
  const [directories, setDirectories] = useState<MediaDirectorySummary[]>([]);
  const [lists, setLists] = useState<MediaListSummary[]>([]);
  const [channels, setChannels] = useState<MediaChannelSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [playingVideoId, setPlayingVideoId] = useState<number | string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const describeActionMessage = (payload: JsonRecord, fallback: string): string => {
    if (typeof payload.message === 'string' && payload.message) {
      return payload.message;
    }
    if (typeof payload.status === 'string' && payload.status) {
      return payload.status;
    }
    if (typeof payload.detail === 'string' && payload.detail) {
      return payload.detail;
    }
    return fallback;
  };

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
      setActionLoadingKey(`play-video-${String(videoId)}`);
      setError(null);
      setActionMessage(null);
      try {
        const response = await client.playVideoOnDevice(options.selectedDeviceId, videoId);
        setActionMessage(response.message ?? 'Playback started.');
      } catch (playError) {
        setError(playError instanceof Error ? playError.message : 'Failed to start playback.');
      } finally {
        setPlayingVideoId(null);
        setActionLoadingKey(null);
      }
    },
    [client, options.selectedDeviceId],
  );

  const scanDirectory = useCallback(
    async (directoryId: number | string) => {
      setActionLoadingKey(`scan-directory-${String(directoryId)}`);
      setError(null);
      setActionMessage(null);
      try {
        const response = await client.scanMediaDirectory(directoryId);
        setActionMessage(describeActionMessage(response, 'Directory scan started.'));
        await load();
      } catch (scanError) {
        setError(scanError instanceof Error ? scanError.message : 'Failed to scan directory.');
      } finally {
        setActionLoadingKey(null);
      }
    },
    [client, load],
  );

  const advanceChannel = useCallback(
    async (channelId: number | string) => {
      setActionLoadingKey(`advance-channel-${String(channelId)}`);
      setError(null);
      setActionMessage(null);
      try {
        const response = await client.advanceMediaChannel(channelId);
        const nextVideoId =
          response.current_video_id !== null && response.current_video_id !== undefined
            ? ` Current video: ${String(response.current_video_id)}.`
            : '';
        setActionMessage(`Channel advanced.${nextVideoId}`);
        await load();
      } catch (advanceError) {
        setError(
          advanceError instanceof Error ? advanceError.message : 'Failed to advance channel.',
        );
      } finally {
        setActionLoadingKey(null);
      }
    },
    [client, load],
  );

  useEffect(() => {
    void load();
  }, [load]);

  return useMemo(
    () => ({
      actionLoadingKey,
      actionMessage,
      advanceChannel,
      channels,
      directories,
      error,
      lists,
      load,
      loading,
      photos,
      playVideo,
      playingVideoId,
      scanDirectory,
      videos,
    }),
    [
      actionLoadingKey,
      actionMessage,
      advanceChannel,
      channels,
      directories,
      error,
      lists,
      load,
      loading,
      photos,
      playVideo,
      playingVideoId,
      scanDirectory,
      videos,
    ],
  );
}
