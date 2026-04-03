import { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { useMediaController } from '../features/media/useMediaController';
import { NanoDlnaApiClient } from '../services/api';
import { colors } from '../theme';
import type {
  MediaChannelSummary,
  MediaDirectorySummary,
  MediaListSummary,
  PhotoSummary,
  VideoSummary,
} from '../types/api';

interface MediaScreenProps {
  client: NanoDlnaApiClient;
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
  client,
  selectedDeviceId,
  selectedDeviceLabel,
}: MediaScreenProps) {
  const {
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
        subtitle="This mobile slice now connects indexed media and media-library structures to the selected playback target from the Devices tab."
      >
        <View style={styles.actionsWrap}>
          <ActionButton
            label={loading ? 'Refreshing...' : 'Refresh media'}
            onPress={() => void load()}
            disabled={loading}
          />
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
                <ActionButton
                  label={playLoading ? 'Starting...' : 'Play on target'}
                  onPress={() => {
                    if (videoId !== null && videoId !== undefined) {
                      void playVideo(videoId);
                    }
                  }}
                  disabled={playDisabled || playLoading}
                />
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
      </Panel>

      <Panel
        title="Photos and library structures"
        subtitle="Read-first parity for photos, directories, playlists, and channels uses the existing FastAPI media-library endpoints."
      >
        <Text style={styles.sectionTitle}>Photos</Text>
        {photos.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No photos are indexed yet.</Text>
        ) : null}
        {photos.slice(0, 6).map((photo) => (
          <View key={String(photo.id ?? describePhoto(photo))} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{describePhoto(photo)}</Text>
            <Text style={styles.detailText}>Category: {formatValue(photo.category)}</Text>
            <Text style={styles.detailText}>Resolution: {formatValue(photo.resolution)}</Text>
            <Text style={styles.detailText}>Format: {formatValue(photo.format)}</Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>Media directories</Text>
        {directories.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No media directories configured.</Text>
        ) : null}
        {directories.slice(0, 6).map((directory) => (
          <View key={String(directory.id ?? describeDirectory(directory))} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{describeDirectory(directory)}</Text>
            <Text style={styles.detailText}>Category: {formatValue(directory.category)}</Text>
            <Text style={styles.detailText}>Enabled: {formatValue(directory.enabled)}</Text>
            <Text style={styles.detailText}>Scan mode: {formatValue(directory.scan_mode)}</Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>Media lists</Text>
        {lists.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No media lists configured.</Text>
        ) : null}
        {lists.slice(0, 6).map((list) => (
          <View key={String(list.id ?? describeList(list))} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{describeList(list)}</Text>
            <Text style={styles.detailText}>Category: {formatValue(list.category)}</Text>
            <Text style={styles.detailText}>
              Playback mode: {formatValue(list.playback_mode)}
            </Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>Media channels</Text>
        {channels.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No media channels configured.</Text>
        ) : null}
        {channels.slice(0, 6).map((channel) => (
          <View key={String(channel.id ?? describeChannel(channel))} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{describeChannel(channel)}</Text>
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
