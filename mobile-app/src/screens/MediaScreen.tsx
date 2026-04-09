import { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { type ControlPlaneClient } from '../control-plane/client';
import type { AppMode } from '../control-plane/localState';
import { useMediaController } from '../features/media/useMediaController';
import { colors } from '../theme';
import type {
  MediaChannelSummary,
  MediaDirectorySummary,
  MediaListSummary,
  PhotoSummary,
  VideoSummary,
} from '../types/api';

interface MediaScreenProps {
  appMode: AppMode;
  client: ControlPlaneClient;
  selectedDeviceId: number | string | null;
  selectedDeviceLabel: string | null;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

function describeVideo(video: VideoSummary): string {
  return (
    (typeof video.title === 'string' && video.title) ||
    (typeof video.name === 'string' && video.name) ||
    (typeof video.file_path === 'string' && video.file_path) ||
    (typeof video.path === 'string' && video.path) ||
    `Video ${String(video.id ?? 'unknown')}`
  );
}

function describePhoto(photo: PhotoSummary): string {
  return (
    (typeof photo.name === 'string' && photo.name) ||
    (typeof photo.file_name === 'string' && photo.file_name) ||
    `Photo ${String(photo.id ?? 'unknown')}`
  );
}

function describeDirectory(directory: MediaDirectorySummary): string {
  return (
    (typeof directory.name === 'string' && directory.name) ||
    (typeof directory.path === 'string' && directory.path) ||
    `Directory ${String(directory.id ?? 'unknown')}`
  );
}

function describeList(list: MediaListSummary): string {
  return (
    (typeof list.name === 'string' && list.name) ||
    `List ${String(list.id ?? 'unknown')}`
  );
}

function describeChannel(channel: MediaChannelSummary): string {
  return (
    (typeof channel.name === 'string' && channel.name) ||
    `Channel ${String(channel.id ?? 'unknown')}`
  );
}

export function MediaScreen({
  appMode,
  client,
  selectedDeviceId,
  selectedDeviceLabel,
}: MediaScreenProps) {
  const {
    actionLoadingKey,
    actionMessage,
    advanceChannel,
    channels,
    createMediaChannel,
    createMediaList,
    createPhotoList,
    createDirectory,
    createPhoto,
    createVideo,
    deleteMediaChannel,
    deleteDirectory,
    deleteMediaList,
    deletePhoto,
    deletePhotoList,
    deleteVideo,
    directories,
    error,
    lists,
    load,
    loading,
    photos,
    photoLists,
    playVideo,
    playingVideoId,
    scanDirectory,
    uploadPhoto,
    uploadVideo,
    videos,
  } = useMediaController(client, { selectedDeviceId });

  const metricCards = useMemo(
    () => [
      { label: 'Videos', value: videos.length },
      { label: 'Photos', value: photos.length },
      { label: 'Directories', value: directories.length },
      { label: 'Lists', value: lists.length },
      { label: 'Channels', value: channels.length },
    ],
    [channels.length, directories.length, lists.length, photos.length, videos.length],
  );

  return (
    <>
      <Panel
        title="Media inventory"
        subtitle={
          appMode === 'local'
            ? 'Local mode keeps a lightweight on-device media inventory so operators can still test playback flows without the backend.'
            : 'Remote mode still connects indexed media and media-library structures to the selected playback target.'
        }
      >
        <View style={styles.actionsWrap}>
          <ActionButton
            label={loading ? 'Refreshing...' : 'Refresh media'}
            onPress={() => void load()}
            disabled={loading}
          />
          {appMode === 'remote' ? (
            <>
              <ActionButton
                label="Upload video"
                onPress={() => void uploadVideo()}
                disabled={loading}
                variant="secondary"
              />
              <ActionButton
                label="Upload photo"
                onPress={() => void uploadPhoto()}
                disabled={loading}
                variant="secondary"
              />
            </>
          ) : null}
        </View>
        <View style={styles.metricGrid}>
          {metricCards.map((metric) => (
            <View key={metric.label} style={styles.metricCard}>
              <Text style={styles.metricValue}>{String(metric.value)}</Text>
              <Text style={styles.metricLabel}>{metric.label}</Text>
            </View>
          ))}
        </View>
        <Text style={styles.selectionLine}>
          Playback target:{' '}
          {selectedDeviceLabel
            ? `${selectedDeviceLabel} (${String(selectedDeviceId)})`
            : 'Select a device in Devices first'}
        </Text>
        {actionMessage ? <Text style={styles.successText}>{actionMessage}</Text> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Video inventory"
        subtitle="Operators can dispatch indexed videos to the currently selected device without leaving the separate mobile app."
      >
        {videos.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No videos are indexed yet.</Text>
        ) : null}

        {videos.slice(0, 20).map((video) => {
          const videoId = video.id;
          const cardKey = String(video.id ?? describeVideo(video));
          const playDisabled =
            selectedDeviceId === null ||
            selectedDeviceId === undefined ||
            videoId === null ||
            videoId === undefined;
          const playLoading = String(playingVideoId) === String(videoId);
          return (
            <View key={cardKey} style={styles.itemCard}>
              <View style={styles.itemHeader}>
                <Text style={styles.itemTitle}>{describeVideo(video)}</Text>
                <View style={styles.inlineActions}>
                  <ActionButton
                    label={playLoading ? 'Starting...' : 'Play on target'}
                    onPress={() => {
                      if (videoId !== null && videoId !== undefined) {
                        void playVideo(videoId);
                      }
                    }}
                    disabled={playDisabled || playLoading}
                  />
                  {appMode === 'remote' && videoId !== null && videoId !== undefined ? (
                    <ActionButton
                      label="Delete"
                      onPress={() => void deleteVideo(videoId)}
                      disabled={actionLoadingKey === `delete-video-${String(videoId)}`}
                      variant="secondary"
                    />
                  ) : null}
                </View>
              </View>
              {video.duration ? (
                <Text style={styles.detailText}>Duration: {String(video.duration)}</Text>
              ) : null}
              {video.mime_type ? (
                <Text style={styles.detailText}>Type: {String(video.mime_type)}</Text>
              ) : null}
              {video.file_path || video.path ? (
                <Text style={styles.detailText}>
                  Source: {String(video.file_path ?? video.path)}
                </Text>
              ) : null}
            </View>
          );
        })}
        {appMode === 'remote' ? (
          <View style={styles.actionsWrap}>
            <ActionButton
              label="Create quick video"
              onPress={() =>
                void createVideo({
                  name: `Mobile video ${videos.length + 1}`,
                  path: `/tmp/mobile-video-${videos.length + 1}.mp4`,
                })
              }
              disabled={loading}
              variant="secondary"
            />
          </View>
        ) : null}
      </Panel>

      <Panel
        title="Photos and library structures"
        subtitle={
          appMode === 'local'
            ? 'Local mode exposes a persisted media shell first; richer backend-synced library features stay available in remote mode.'
            : 'Read-first parity for photos, directories, playlists, and channels uses the existing FastAPI media-library endpoints.'
        }
      >
        <Text style={styles.sectionTitle}>Photos</Text>
        {photos.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No photos are indexed yet.</Text>
        ) : null}
        {photos.slice(0, 6).map((photo) => (
          <View key={String(photo.id ?? describePhoto(photo))} style={styles.itemCard}>
            <View style={styles.itemHeader}>
              <Text style={styles.itemTitle}>{describePhoto(photo)}</Text>
              {appMode === 'remote' && photo.id !== null && photo.id !== undefined ? (
                <ActionButton
                  label="Delete"
                  onPress={() => {
                    const photoId = photo.id;
                    if (photoId !== null && photoId !== undefined) {
                      void deletePhoto(photoId);
                    }
                  }}
                  disabled={actionLoadingKey === `delete-photo-${String(photo.id)}`}
                  variant="secondary"
                />
              ) : null}
            </View>
            <Text style={styles.detailText}>Category: {formatValue(photo.category)}</Text>
            <Text style={styles.detailText}>Resolution: {formatValue(photo.resolution)}</Text>
            <Text style={styles.detailText}>Format: {formatValue(photo.format)}</Text>
          </View>
        ))}
        {appMode === 'remote' ? (
          <View style={styles.actionsWrap}>
            <ActionButton
              label="Create quick photo"
              onPress={() =>
                void createPhoto({
                  name: `Mobile photo ${photos.length + 1}`,
                  path: `/tmp/mobile-photo-${photos.length + 1}.png`,
                  category: 'background',
                })
              }
              disabled={loading}
              variant="secondary"
            />
          </View>
        ) : null}

        <Text style={styles.sectionTitle}>Media directories</Text>
        {directories.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No media directories configured.</Text>
        ) : null}
        {directories.slice(0, 6).map((directory) => (
          <View key={String(directory.id ?? describeDirectory(directory))} style={styles.itemCard}>
            <View style={styles.itemHeader}>
              <Text style={styles.itemTitle}>{describeDirectory(directory)}</Text>
              <ActionButton
                label={
                  actionLoadingKey === `scan-directory-${String(directory.id)}`
                    ? 'Scanning...'
                    : 'Scan'
                }
                onPress={() => {
                  if (directory.id !== null && directory.id !== undefined) {
                    void scanDirectory(directory.id);
                  }
                }}
                disabled={
                  directory.id === null ||
                  directory.id === undefined ||
                  actionLoadingKey === `scan-directory-${String(directory.id)}`
                }
                variant="secondary"
              />
              {appMode === 'remote' && directory.id !== null && directory.id !== undefined ? (
                <ActionButton
                  label="Delete"
                  onPress={() => {
                    const directoryId = directory.id;
                    if (directoryId !== null && directoryId !== undefined) {
                      void deleteDirectory(directoryId);
                    }
                  }}
                  disabled={actionLoadingKey === `delete-directory-${String(directory.id)}`}
                  variant="secondary"
                />
              ) : null}
            </View>
            <Text style={styles.detailText}>Category: {formatValue(directory.category)}</Text>
            <Text style={styles.detailText}>Enabled: {formatValue(directory.enabled)}</Text>
            <Text style={styles.detailText}>Scan mode: {formatValue(directory.scan_mode)}</Text>
          </View>
        ))}
        {appMode === 'remote' ? (
          <View style={styles.actionsWrap}>
            <ActionButton
              label="Create quick directory"
              onPress={() =>
                void createDirectory({
                  name: `Mobile dir ${directories.length + 1}`,
                  path: `/tmp/mobile-media-${directories.length + 1}`,
                  category: 'background',
                })
              }
              disabled={loading}
              variant="secondary"
            />
          </View>
        ) : null}

        <Text style={styles.sectionTitle}>Media lists</Text>
        {lists.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No media lists configured.</Text>
        ) : null}
        {lists.slice(0, 6).map((list) => (
          <View key={String(list.id ?? describeList(list))} style={styles.itemCard}>
            <View style={styles.itemHeader}>
              <Text style={styles.itemTitle}>{describeList(list)}</Text>
              {appMode === 'remote' && list.id !== null && list.id !== undefined ? (
                <ActionButton
                  label="Delete"
                  onPress={() => {
                    const listId = list.id;
                    if (listId !== null && listId !== undefined) {
                      void deleteMediaList(listId);
                    }
                  }}
                  disabled={actionLoadingKey === `delete-media-list-${String(list.id)}`}
                  variant="secondary"
                />
              ) : null}
            </View>
            <Text style={styles.detailText}>Category: {formatValue(list.category)}</Text>
            <Text style={styles.detailText}>
              Playback mode: {formatValue(list.playback_mode)}
            </Text>
          </View>
        ))}
        {appMode === 'remote' ? (
          <View style={styles.actionsWrap}>
            <ActionButton
              label="Create quick media list"
              onPress={() =>
                void createMediaList({
                  name: `Mobile list ${lists.length + 1}`,
                  category: 'background',
                  video_ids: videos
                    .slice(0, 3)
                    .map((video) => video.id)
                    .filter((value) => value !== null && value !== undefined),
                  playback_mode: 'sequence',
                  shuffle: false,
                  loop: true,
                })
              }
              disabled={loading}
              variant="secondary"
            />
          </View>
        ) : null}

        <Text style={styles.sectionTitle}>Media channels</Text>
        {channels.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No media channels configured.</Text>
        ) : null}
        {channels.slice(0, 6).map((channel) => (
          <View key={String(channel.id ?? describeChannel(channel))} style={styles.itemCard}>
            <View style={styles.itemHeader}>
              <Text style={styles.itemTitle}>{describeChannel(channel)}</Text>
              <View style={styles.inlineActions}>
                <ActionButton
                  label={
                    actionLoadingKey === `advance-channel-${String(channel.id)}`
                      ? 'Advancing...'
                      : 'Advance'
                  }
                  onPress={() => {
                    if (channel.id !== null && channel.id !== undefined) {
                      void advanceChannel(channel.id);
                    }
                  }}
                  disabled={
                    channel.id === null ||
                    channel.id === undefined ||
                    actionLoadingKey === `advance-channel-${String(channel.id)}`
                  }
                  variant="secondary"
                />
                {appMode === 'remote' && channel.id !== null && channel.id !== undefined ? (
                  <ActionButton
                    label="Delete"
                    onPress={() => {
                      const channelId = channel.id;
                      if (channelId !== null && channelId !== undefined) {
                        void deleteMediaChannel(channelId);
                      }
                    }}
                    disabled={actionLoadingKey === `delete-media-channel-${String(channel.id)}`}
                    variant="secondary"
                  />
                ) : null}
              </View>
            </View>
            <Text style={styles.detailText}>
              List ID: {formatValue(channel.media_list_id)}
            </Text>
            <Text style={styles.detailText}>
              Current video: {formatValue(channel.current_video_id)}
            </Text>
            <Text style={styles.detailText}>
              Current index: {formatValue(channel.current_index)}
            </Text>
          </View>
        ))}
        {appMode === 'remote' ? (
          <View style={styles.actionsWrap}>
            <ActionButton
              label="Create quick channel"
              onPress={() =>
                void createMediaChannel({
                  name: `Mobile channel ${channels.length + 1}`,
                  media_list_id: lists[0]?.id ?? '',
                  current_index: 0,
                })
              }
              disabled={loading || lists.length === 0}
              variant="secondary"
            />
          </View>
        ) : null}

        <Text style={styles.sectionTitle}>Photo lists</Text>
        {photoLists.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No photo lists configured.</Text>
        ) : null}
        {photoLists.slice(0, 6).map((list) => (
          <View key={String(list.id ?? 'photo-list')} style={styles.itemCard}>
            <View style={styles.itemHeader}>
              <Text style={styles.itemTitle}>{formatValue(list.name, 'Photo list')}</Text>
              {appMode === 'remote' && list.id !== null && list.id !== undefined ? (
                <ActionButton
                  label="Delete"
                  onPress={() => void deletePhotoList(String(list.id))}
                  disabled={actionLoadingKey === `delete-photo-list-${String(list.id)}`}
                  variant="secondary"
                />
              ) : null}
            </View>
            <Text style={styles.detailText}>
              Photos: {Array.isArray(list.photo_ids) ? list.photo_ids.length : 0}
            </Text>
            <Text style={styles.detailText}>
              Playback mode: {formatValue(list.playback_mode)}
            </Text>
          </View>
        ))}
        {appMode === 'remote' ? (
          <View style={styles.actionsWrap}>
            <ActionButton
              label="Create quick photo list"
              onPress={() =>
                void createPhotoList({
                  name: `Mobile photo list ${photoLists.length + 1}`,
                  category: 'background',
                  photo_ids: photos
                    .slice(0, 3)
                    .map((photo) => photo.id)
                    .filter((value) => value !== null && value !== undefined),
                  playback_mode: 'sequence',
                  shuffle: false,
                  loop: true,
                })
              }
              disabled={loading}
              variant="secondary"
            />
          </View>
        ) : null}
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  actionsWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metricGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metricCard: {
    minWidth: 90,
    flexGrow: 1,
    backgroundColor: colors.elevatedPanel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
    gap: 4,
  },
  metricValue: {
    color: colors.accent,
    fontSize: 20,
    fontWeight: '700',
  },
  metricLabel: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: '600',
  },
  selectionLine: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  successText: {
    color: colors.success,
    fontSize: 13,
    lineHeight: 18,
  },
  errorText: {
    color: colors.danger,
    fontSize: 13,
    lineHeight: 18,
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  itemCard: {
    gap: 6,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  inlineActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  itemTitle: {
    flex: 1,
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  detailText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
});
