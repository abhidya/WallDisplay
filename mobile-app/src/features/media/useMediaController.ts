import { useCallback, useEffect, useMemo, useState } from 'react';

import { type ControlPlaneClient } from '../../control-plane/client';
import { createServiceModules } from '../../services/api.ts';
import type {
  JsonRecord,
  MediaChannelSummary,
  MediaDirectorySummary,
  MediaListSummary,
  PhotoSummary,
  VideoSummary,
} from '../../types/api';

async function pickWebFile(accept: string): Promise<File | null> {
  if (typeof document === 'undefined') {
    return null;
  }

  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    input.onchange = () => resolve(input.files?.[0] ?? null);
    input.click();
  });
}

export interface MediaController {
  actionLoadingKey: string | null;
  actionMessage: string | null;
  channels: MediaChannelSummary[];
  directories: MediaDirectorySummary[];
  error: string | null;
  lists: MediaListSummary[];
  loading: boolean;
  photos: PhotoSummary[];
  photoLists: JsonRecord[];
  playingVideoId: number | string | null;
  videos: VideoSummary[];
  createMediaList: (payload: JsonRecord) => Promise<void>;
  createMediaChannel: (payload: JsonRecord) => Promise<void>;
  deleteMediaList: (listId: number | string) => Promise<void>;
  deleteMediaChannel: (channelId: number | string) => Promise<void>;
  createVideo: (payload: JsonRecord) => Promise<void>;
  deleteVideo: (videoId: number | string) => Promise<void>;
  uploadVideo: () => Promise<void>;
  createPhoto: (payload: JsonRecord) => Promise<void>;
  deletePhoto: (photoId: number | string) => Promise<void>;
  uploadPhoto: () => Promise<void>;
  createDirectory: (payload: JsonRecord) => Promise<void>;
  deleteDirectory: (directoryId: number | string) => Promise<void>;
  createPhotoList: (payload: JsonRecord) => Promise<void>;
  deletePhotoList: (listId: number | string) => Promise<void>;
  advanceChannel: (channelId: number | string) => Promise<void>;
  load: () => Promise<void>;
  playVideo: (videoId: number | string) => Promise<void>;
  scanDirectory: (directoryId: number | string) => Promise<void>;
}

interface UseMediaControllerOptions {
  apiBaseUrl: string;
  selectedDeviceId: number | string | null;
}

export function useMediaController(
  client: ControlPlaneClient,
  options: UseMediaControllerOptions,
): MediaController {
  const services = useMemo(() => createServiceModules(options.apiBaseUrl), [options.apiBaseUrl]);
  const [actionLoadingKey, setActionLoadingKey] = useState<string | null>(null);
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [photos, setPhotos] = useState<PhotoSummary[]>([]);
  const [directories, setDirectories] = useState<MediaDirectorySummary[]>([]);
  const [lists, setLists] = useState<MediaListSummary[]>([]);
  const [channels, setChannels] = useState<MediaChannelSummary[]>([]);
  const [photoLists, setPhotoLists] = useState<JsonRecord[]>([]);
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
        photoListsPayload,
      ] = await Promise.all([
        client.listVideos(),
        client.listPhotos(),
        client.listMediaDirectories(),
        client.listMediaLists(),
        client.listMediaChannels(),
        services.photoListApi.listPhotoLists(),
      ]);

      setVideos(videosPayload);
      setPhotos(photosPayload);
      setDirectories(directoriesPayload);
      setLists(listsPayload);
      setChannels(channelsPayload);
      setPhotoLists(Array.isArray(photoListsPayload) ? photoListsPayload : []);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load media inventory.');
    } finally {
      setLoading(false);
    }
  }, [client, services]);

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

  const runRemoteMutation = useCallback(
    async (
      actionKey: string,
      handler: () => Promise<unknown>,
      successMessage: string,
    ) => {
      setActionLoadingKey(actionKey);
      setError(null);
      setActionMessage(null);
      try {
        await handler();
        setActionMessage(successMessage);
        await load();
      } catch (mutationError) {
        setError(
          mutationError instanceof Error ? mutationError.message : 'Media mutation failed.',
        );
      } finally {
        setActionLoadingKey(null);
      }
    },
    [load],
  );

  const createMediaList = useCallback(
    async (payload: JsonRecord) => {
      await runRemoteMutation(
        'create-media-list',
        () => services.mediaLibraryApi.createMediaList(payload),
        'Media list saved.',
      );
    },
    [runRemoteMutation, services],
  );

  const createVideo = useCallback(
    async (payload: JsonRecord) => {
      await runRemoteMutation(
        'create-video',
        () => services.videoApi.createVideo(payload),
        'Video saved.',
      );
    },
    [runRemoteMutation, services],
  );

  const deleteVideo = useCallback(
    async (videoId: number | string) => {
      await runRemoteMutation(
        `delete-video-${String(videoId)}`,
        () => services.videoApi.deleteVideo(videoId),
        `Deleted video ${String(videoId)}.`,
      );
    },
    [runRemoteMutation, services],
  );

  const uploadVideo = useCallback(async () => {
    const file = await pickWebFile('video/*');
    if (!file) {
      setError('No video file selected.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', file.name.replace(/\.[^.]+$/, ''));

    await runRemoteMutation(
      'upload-video',
      () => services.videoApi.uploadVideo(formData),
      `Uploaded video ${file.name}.`,
    );
  }, [runRemoteMutation, services]);

  const createPhoto = useCallback(
    async (payload: JsonRecord) => {
      await runRemoteMutation(
        'create-photo',
        () => services.photoApi.createPhoto(payload),
        'Photo saved.',
      );
    },
    [runRemoteMutation, services],
  );

  const deletePhoto = useCallback(
    async (photoId: number | string) => {
      await runRemoteMutation(
        `delete-photo-${String(photoId)}`,
        () => services.photoApi.deletePhoto(photoId),
        `Deleted photo ${String(photoId)}.`,
      );
    },
    [runRemoteMutation, services],
  );

  const uploadPhoto = useCallback(async () => {
    const file = await pickWebFile('image/*');
    if (!file) {
      setError('No photo file selected.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    await runRemoteMutation(
      'upload-photo',
      () => services.photoApi.uploadPhoto(formData),
      `Uploaded photo ${file.name}.`,
    );
  }, [runRemoteMutation, services]);

  const createDirectory = useCallback(
    async (payload: JsonRecord) => {
      await runRemoteMutation(
        'create-directory',
        () => services.mediaLibraryApi.createDirectory(payload),
        'Media directory saved.',
      );
    },
    [runRemoteMutation, services],
  );

  const deleteDirectory = useCallback(
    async (directoryId: number | string) => {
      await runRemoteMutation(
        `delete-directory-${String(directoryId)}`,
        () => services.mediaLibraryApi.deleteDirectory(directoryId),
        `Deleted directory ${String(directoryId)}.`,
      );
    },
    [runRemoteMutation, services],
  );

  const createMediaChannel = useCallback(
    async (payload: JsonRecord) => {
      await runRemoteMutation(
        'create-media-channel',
        () => services.mediaLibraryApi.createMediaChannel(payload),
        'Media channel saved.',
      );
    },
    [runRemoteMutation, services],
  );

  const deleteMediaList = useCallback(
    async (listId: number | string) => {
      await runRemoteMutation(
        `delete-media-list-${String(listId)}`,
        () => services.mediaLibraryApi.deleteMediaList(listId),
        `Deleted media list ${String(listId)}.`,
      );
    },
    [runRemoteMutation, services],
  );

  const deleteMediaChannel = useCallback(
    async (channelId: number | string) => {
      await runRemoteMutation(
        `delete-media-channel-${String(channelId)}`,
        () => services.mediaLibraryApi.deleteMediaChannel(channelId),
        `Deleted media channel ${String(channelId)}.`,
      );
    },
    [runRemoteMutation, services],
  );

  const createPhotoList = useCallback(
    async (payload: JsonRecord) => {
      await runRemoteMutation(
        'create-photo-list',
        () => services.photoListApi.createPhotoList(payload),
        'Photo list saved.',
      );
    },
    [runRemoteMutation, services],
  );

  const deletePhotoList = useCallback(
    async (listId: number | string) => {
      await runRemoteMutation(
        `delete-photo-list-${String(listId)}`,
        () => services.photoListApi.deletePhotoList(listId),
        `Deleted photo list ${String(listId)}.`,
      );
    },
    [runRemoteMutation, services],
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
      photoLists,
      playVideo,
      playingVideoId,
      createVideo,
      deleteVideo,
      uploadVideo,
      createPhoto,
      deletePhoto,
      uploadPhoto,
      createDirectory,
      deleteDirectory,
      createMediaList,
      createMediaChannel,
      deleteMediaList,
      deleteMediaChannel,
      createPhotoList,
      deletePhotoList,
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
      photoLists,
      playVideo,
      playingVideoId,
      createVideo,
      deleteVideo,
      uploadVideo,
      createPhoto,
      deletePhoto,
      uploadPhoto,
      createDirectory,
      deleteDirectory,
      createMediaList,
      createMediaChannel,
      deleteMediaList,
      deleteMediaChannel,
      createPhotoList,
      deletePhotoList,
      scanDirectory,
      videos,
    ],
  );
}
