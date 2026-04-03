import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { useOverlayProjectionController } from '../features/overlay/useOverlayProjectionController';
import type { AppMode } from '../control-plane/localState';
import { colors } from '../theme';
import type { JsonRecord } from '../types/api';

interface OverlayProjectionScreenProps {
  apiBaseUrl: string;
  appMode: AppMode;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

function describeConfig(config: JsonRecord): string {
  return String(config.name ?? config.id ?? 'Overlay config');
}

function describeScene(scene: JsonRecord): string {
  return String(scene.name ?? scene.id ?? 'Mapping scene');
}

function describeDevice(device: JsonRecord): string {
  return String(device.friendly_name ?? device.name ?? device.id ?? 'Device');
}

export function OverlayProjectionScreen({
  apiBaseUrl,
  appMode,
}: OverlayProjectionScreenProps) {
  const {
    actionLoading,
    actionMessage,
    brightness,
    castDevices,
    castLoading,
    castSessions,
    configs,
    createConfig,
    deleteConfig,
    error,
    exportDurationSeconds,
    exportProjection,
    loading,
    mappings,
    refresh,
    selectedCastDeviceId,
    selectedConfigId,
    selectedMappingId,
    selectedVideoId,
    setBrightnessValue,
    setExportDurationSeconds,
    setSelectedCastDeviceId,
    setSelectedConfigId,
    setSelectedMappingId,
    setSelectedVideoId,
    startCast,
    stopCast,
    syncOverlays,
    videos,
  } = useOverlayProjectionController({ apiBaseUrl, appMode });

  if (appMode === 'local') {
    return (
      <Panel
        title="Overlay projection"
        subtitle="Overlay projection stays remote-only in this slice because the backend owns config persistence, export rendering, and DLNA cast relays."
      >
        <Text style={styles.noteText}>
          Switch to remote mode to manage overlay configs, trigger exports, sync overlays, and control overlay cast sessions.
        </Text>
      </Panel>
    );
  }

  return (
    <>
      <Panel
        title="Overlay projection"
        subtitle="A compact mobile operator slice for overlay configs, projection export, sync, and cast-session control."
      >
        <View style={styles.actionsRow}>
          <ActionButton
            label={loading ? 'Refreshing...' : 'Refresh'}
            onPress={() => void refresh()}
            disabled={loading}
          />
          <ActionButton
            label={actionLoading ? 'Working...' : 'Create config'}
            onPress={() => void createConfig()}
            disabled={actionLoading}
            variant="secondary"
          />
          <ActionButton
            label="Sync overlays"
            onPress={() => void syncOverlays()}
            disabled={actionLoading}
            variant="secondary"
          />
        </View>
        {actionMessage ? <Text style={styles.successText}>{actionMessage}</Text> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Source selection"
        subtitle="Choose a video/mapping source and an overlay config to drive export or cast actions."
      >
        <Text style={styles.sectionTitle}>Videos</Text>
        <View style={styles.selectionGrid}>
          {videos.slice(0, 6).map((video) => {
            const selected = String(video.id) === selectedVideoId;
            return (
              <Pressable
                key={String(video.id ?? describeConfig(video))}
                accessibilityRole="button"
                onPress={() => setSelectedVideoId(String(video.id ?? ''))}
                style={[styles.selectionCard, selected && styles.selectionCardActive]}
              >
                <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                  {formatValue(video.name ?? video.title, 'Video')}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.sectionTitle}>Mapping scenes</Text>
        <View style={styles.selectionGrid}>
          {mappings.slice(0, 6).map((scene) => {
            const selected = String(scene.id) === selectedMappingId;
            return (
              <Pressable
                key={String(scene.id ?? describeScene(scene))}
                accessibilityRole="button"
                onPress={() => setSelectedMappingId(String(scene.id ?? ''))}
                style={[styles.selectionCard, selected && styles.selectionCardActive]}
              >
                <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                  {describeScene(scene)}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.sectionTitle}>Overlay configs</Text>
        {configs.length === 0 ? (
          <Text style={styles.emptyText}>No overlay configs available yet.</Text>
        ) : null}
        {configs.slice(0, 8).map((config) => {
          const configId = String(config.id ?? '');
          const selected = configId === selectedConfigId;
          return (
            <View key={configId || describeConfig(config)} style={styles.itemCard}>
              <Pressable
                accessibilityRole="button"
                onPress={() => setSelectedConfigId(configId)}
                style={[styles.selectionCard, selected && styles.selectionCardActive]}
              >
                <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                  {describeConfig(config)}
                </Text>
                <Text style={styles.detailText}>
                  Background: {formatValue(config.background_type)}
                </Text>
                <Text style={styles.detailText}>
                  Widgets: {Array.isArray(config.widgets) ? config.widgets.length : 0}
                </Text>
              </Pressable>
              {config.id !== null && config.id !== undefined ? (
                <View style={styles.actionsRow}>
                  <ActionButton
                    label="Delete"
                    onPress={() => void deleteConfig(config.id as string | number)}
                    disabled={actionLoading}
                    variant="secondary"
                  />
                </View>
              ) : null}
            </View>
          );
        })}
      </Panel>

      <Panel
        title="Export and cast"
        subtitle="Generate MP4 exports and start/stop DLNA projector casts for the selected overlay config."
      >
        <Text style={styles.fieldLabel}>Brightness</Text>
        <TextInput
          keyboardType="numeric"
          onChangeText={setBrightnessValue}
          style={styles.input}
          value={String(brightness)}
        />
        <Text style={styles.fieldLabel}>Export duration seconds</Text>
        <TextInput
          keyboardType="numeric"
          onChangeText={setExportDurationSeconds}
          style={styles.input}
          value={exportDurationSeconds}
        />
        <Text style={styles.sectionTitle}>Cast devices</Text>
        <View style={styles.selectionGrid}>
          {castDevices.slice(0, 6).map((device) => {
            const deviceId = String(device.id ?? '');
            const selected = deviceId === selectedCastDeviceId;
            return (
              <Pressable
                key={deviceId || describeDevice(device)}
                accessibilityRole="button"
                onPress={() => setSelectedCastDeviceId(deviceId)}
                style={[styles.selectionCard, selected && styles.selectionCardActive]}
              >
                <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                  {describeDevice(device)}
                </Text>
                <Text style={styles.detailText}>
                  Online: {formatValue(device.is_online)}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <View style={styles.actionsRow}>
          <ActionButton
            label={actionLoading ? 'Exporting...' : 'Export MP4'}
            onPress={() => void exportProjection()}
            disabled={actionLoading || !selectedConfigId}
          />
          <ActionButton
            label={castLoading ? 'Casting...' : 'Start cast'}
            onPress={() => void startCast()}
            disabled={castLoading || !selectedConfigId || !selectedCastDeviceId}
            variant="secondary"
          />
        </View>
      </Panel>

      <Panel
        title="Overlay cast sessions"
        subtitle="Inspect active sessions and stop any running relay from the mobile app."
      >
        {castSessions.length === 0 ? (
          <Text style={styles.emptyText}>No overlay cast sessions returned yet.</Text>
        ) : null}
        {castSessions.map((session) => (
          <View key={String(session.session_id ?? describeConfig(session))} style={styles.itemCard}>
            <Text style={styles.itemTitle}>
              {formatValue(session.device_id, 'Device')} • config {formatValue(session.config_id)}
            </Text>
            <Text style={styles.detailText}>
              Status: {formatValue(session.status)} • Step: {formatValue(session.current_step)}
            </Text>
            <Text style={styles.detailText}>
              Clients: {formatValue(session.active_clients, '0')} • Speed:{' '}
              {formatValue(
                session.ffmpeg_speed !== null && session.ffmpeg_speed !== undefined
                  ? `${Number(session.ffmpeg_speed).toFixed(2)}x`
                  : null,
              )}
            </Text>
            <Text style={styles.detailText}>
              Relay: {formatValue(session.relay_url)}
            </Text>
            {session.session_id ? (
              <View style={styles.actionsRow}>
                <ActionButton
                  label="Stop"
                  onPress={() => void stopCast(String(session.session_id))}
                  disabled={castLoading}
                  variant="secondary"
                />
              </View>
            ) : null}
          </View>
        ))}
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
  noteText: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
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
  sectionTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  selectionGrid: {
    gap: 10,
  },
  selectionCard: {
    gap: 6,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.elevatedPanel,
  },
  selectionCardActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentMuted,
  },
  selectionTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  selectionTitleActive: {
    color: colors.accent,
  },
  detailText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  itemCard: {
    gap: 6,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  itemTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
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
});
