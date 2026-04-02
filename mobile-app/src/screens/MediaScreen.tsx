import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { colors } from '../theme';
import type { VideoSummary } from '../types/api';
import { NanoDlnaApiClient } from '../services/api';

interface MediaScreenProps {
  client: NanoDlnaApiClient;
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

export function MediaScreen({ client }: MediaScreenProps) {
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setVideos(await client.listVideos());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load videos.');
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <Panel
        title="Media library shell"
        subtitle="The mobile rewrite starts by reusing the indexed video library rather than rebuilding ingestion logic on-device."
      >
        <ActionButton
          label={loading ? 'Refreshing...' : 'Refresh videos'}
          onPress={() => void load()}
          disabled={loading}
        />
        <Text style={styles.metaLine}>Videos returned: {videos.length}</Text>
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Video inventory"
        subtitle="Next iterations can add device-targeted playback actions, thumbnails, and queue management."
      >
        {videos.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No videos are indexed yet.</Text>
        ) : null}

        {videos.slice(0, 20).map((video) => (
          <View key={String(video.id ?? describeVideo(video))} style={styles.videoCard}>
            <Text style={styles.videoTitle}>{describeVideo(video)}</Text>
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
        ))}
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  metaLine: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: '600',
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
  videoCard: {
    gap: 6,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  videoTitle: {
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
