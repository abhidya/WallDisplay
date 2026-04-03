import { Image, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { useDepthProcessingController } from '../features/depth/useDepthProcessingController';
import type { AppMode } from '../control-plane/localState';
import { colors } from '../theme';

interface DepthProcessingScreenProps {
  apiBaseUrl: string;
  appMode: AppMode;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

export function DepthProcessingScreen({
  apiBaseUrl,
  appMode,
}: DepthProcessingScreenProps) {
  const {
    actionMessage,
    createProjection,
    currentDepthId,
    deleteDepthMap,
    depthPreviewUrl,
    error,
    exportMasks,
    loading,
    overlayAlpha,
    projectionConfigId,
    projectionDeviceId,
    projectionPageUrl,
    segmentDepthMap,
    segmentationMethod,
    segmentationPreviewUrl,
    segmentationResult,
    selectedSegments,
    setOverlayAlpha,
    setProjectionDeviceId,
    setSegmentationMethod,
    setThresholds,
    setNumBands,
    setNumClusters,
    thresholds,
    numBands,
    numClusters,
    toggleSegment,
    uploadDepthMap,
  } = useDepthProcessingController({ apiBaseUrl, appMode });

  if (appMode === 'local') {
    return (
      <Panel
        title="Depth processing"
        subtitle="Depth upload/segmentation depends on remote backend processing, so this slice is currently remote-only."
      >
        <Text style={styles.noteText}>
          Switch to remote mode to upload a depth map, segment it, export masks, and create a projection page from the existing backend service.
        </Text>
      </Panel>
    );
  }

  const segments = Array.isArray(segmentationResult?.segments)
    ? segmentationResult.segments
        .map((item) => Number(item))
        .filter((item) => Number.isFinite(item))
    : [];

  return (
    <>
      <Panel
        title="Depth processing"
        subtitle="Mobile now exposes a compact operator workflow for the backend depth-processing service."
      >
        <View style={styles.actionsRow}>
          <ActionButton
            label={loading ? 'Working...' : 'Upload depth map'}
            onPress={() => void uploadDepthMap()}
            disabled={loading}
          />
          <ActionButton
            label={loading ? 'Working...' : 'Delete current'}
            onPress={() => void deleteDepthMap()}
            disabled={loading || !currentDepthId}
            variant="secondary"
          />
        </View>
        <Text style={styles.detailText}>Depth ID: {formatValue(currentDepthId, 'None loaded')}</Text>
        {actionMessage ? <Text style={styles.successText}>{actionMessage}</Text> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Segmentation controls"
        subtitle="Configure the depth segmentation method before creating mask previews or projection surfaces."
      >
        <View style={styles.fieldGroup}>
          <Text style={styles.fieldLabel}>Method</Text>
          <TextInput
            onChangeText={setSegmentationMethod}
            style={styles.input}
            value={segmentationMethod}
          />
        </View>
        <View style={styles.row}>
          <View style={styles.halfField}>
            <Text style={styles.fieldLabel}>Clusters</Text>
            <TextInput
              keyboardType="numeric"
              onChangeText={setNumClusters}
              style={styles.input}
              value={numClusters}
            />
          </View>
          <View style={styles.halfField}>
            <Text style={styles.fieldLabel}>Bands</Text>
            <TextInput
              keyboardType="numeric"
              onChangeText={setNumBands}
              style={styles.input}
              value={numBands}
            />
          </View>
        </View>
        <View style={styles.fieldGroup}>
          <Text style={styles.fieldLabel}>Thresholds</Text>
          <TextInput
            onChangeText={setThresholds}
            style={styles.input}
            value={thresholds}
          />
        </View>
        <View style={styles.fieldGroup}>
          <Text style={styles.fieldLabel}>Overlay alpha</Text>
          <TextInput
            keyboardType="decimal-pad"
            onChangeText={setOverlayAlpha}
            style={styles.input}
            value={overlayAlpha}
          />
        </View>
        <View style={styles.actionsRow}>
          <ActionButton
            label={loading ? 'Working...' : 'Segment depth map'}
            onPress={() => void segmentDepthMap()}
            disabled={loading || !currentDepthId}
          />
          <ActionButton
            label="Export masks"
            onPress={exportMasks}
            disabled={loading || selectedSegments.length === 0}
            variant="secondary"
          />
        </View>
      </Panel>

      <Panel
        title="Preview"
        subtitle="The preview URLs come directly from the depth service port."
      >
        {depthPreviewUrl ? (
          <Image source={{ uri: depthPreviewUrl }} style={styles.previewImage} resizeMode="contain" />
        ) : (
          <Text style={styles.emptyText}>Upload a depth map to see a preview.</Text>
        )}
        {segmentationPreviewUrl ? (
          <Image
            source={{ uri: segmentationPreviewUrl }}
            style={styles.previewImage}
            resizeMode="contain"
          />
        ) : null}
      </Panel>

      <Panel
        title="Segments"
        subtitle="Select segments to export masks or create a projection."
      >
        {segments.length === 0 ? (
          <Text style={styles.emptyText}>No segmentation result yet.</Text>
        ) : null}
        <View style={styles.segmentGrid}>
          {segments.map((segmentId) => {
            const selected = selectedSegments.includes(segmentId);
            return (
              <Pressable
                key={String(segmentId)}
                accessibilityRole="button"
                onPress={() => toggleSegment(segmentId)}
                style={[styles.segmentChip, selected && styles.segmentChipActive]}
              >
                <Text style={[styles.segmentChipLabel, selected && styles.segmentChipLabelActive]}>
                  Segment {segmentId}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={styles.detailText}>
          Segment count: {formatValue(segmentationResult?.segment_count, String(segments.length))}
        </Text>
      </Panel>

      <Panel
        title="Projection creation"
        subtitle="Create a simple projection page from the first selected segment using the remote depth service."
      >
        <View style={styles.fieldGroup}>
          <Text style={styles.fieldLabel}>Device ID</Text>
          <TextInput
            keyboardType="numeric"
            onChangeText={setProjectionDeviceId}
            style={styles.input}
            value={projectionDeviceId}
          />
        </View>
        <View style={styles.actionsRow}>
          <ActionButton
            label={loading ? 'Working...' : 'Create projection'}
            onPress={() => void createProjection()}
            disabled={loading || !currentDepthId || selectedSegments.length === 0}
          />
        </View>
        <Text style={styles.detailText}>
          Projection config ID: {formatValue(projectionConfigId)}
        </Text>
        <Text style={styles.detailText}>
          Projection page: {formatValue(projectionPageUrl)}
        </Text>
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  actionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  detailText: {
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
  noteText: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  fieldGroup: {
    gap: 8,
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  halfField: {
    minWidth: 120,
    flexGrow: 1,
    gap: 8,
  },
  fieldLabel: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '600',
  },
  input: {
    backgroundColor: colors.elevatedPanel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    color: colors.text,
    fontSize: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  previewImage: {
    width: '100%',
    height: 240,
    borderRadius: 12,
    backgroundColor: colors.elevatedPanel,
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  segmentGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  segmentChip: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.elevatedPanel,
  },
  segmentChipActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentMuted,
  },
  segmentChipLabel: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '600',
  },
  segmentChipLabelActive: {
    color: colors.accent,
  },
});
