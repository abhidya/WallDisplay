import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { useDevicesController } from '../features/devices/useDevicesController';
import { NanoDlnaApiClient } from '../services/api';
import { colors } from '../theme';
import type { DeviceSummary } from '../types/api';

interface DevicesScreenProps {
  client: NanoDlnaApiClient;
  selectedDeviceId?: number | string | null;
  onSelectDevice?: (deviceId: number | string | null, label: string | null) => void;
}

function describeDevice(device: DeviceSummary): string {
  return (
    (typeof device.friendly_name === 'string' && device.friendly_name) ||
    (typeof device.device_name === 'string' && device.device_name) ||
    (typeof device.name === 'string' && device.name) ||
    `Device ${String(device.id ?? 'unknown')}`
  );
}

function describeStatus(device: DeviceSummary): string {
  return (
    (typeof device.derived_status === 'string' && device.derived_status) ||
    (typeof device.status === 'string' && device.status) ||
    (typeof device.playback_state === 'string' && device.playback_state) ||
    'unknown'
  );
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

function statusTone(status: string): keyof typeof statusColors {
  const normalized = status.toLowerCase();
  if (
    normalized.includes('play') ||
    normalized.includes('connected') ||
    normalized.includes('online') ||
    normalized.includes('ready')
  ) {
    return 'success';
  }
  if (
    normalized.includes('pause') ||
    normalized.includes('idle') ||
    normalized.includes('degraded')
  ) {
    return 'warning';
  }
  if (
    normalized.includes('offline') ||
    normalized.includes('error') ||
    normalized.includes('fail')
  ) {
    return 'danger';
  }
  return 'neutral';
}

const statusColors = {
  success: colors.success,
  warning: colors.warning,
  danger: colors.danger,
  neutral: colors.accent,
};

export function DevicesScreen({
  client,
  selectedDeviceId: sharedSelectedDeviceId,
  onSelectDevice,
}: DevicesScreenProps) {
  const {
    actionLoadingKey,
    actionMessage,
    activeDeviceId,
    controlMode,
    discoveryBackends,
    unifiedDiscoveryCapabilities,
    unifiedDiscoveryStatus,
    detailLoading,
    devices,
    discovering,
    discoveryPaused,
    discoveryStatus,
    error,
    health,
    loading,
    selectedDevice,
    selectedDeviceId,
    selectDevice,
    load,
    discover,
    refreshSelectedDevice,
    runDiscoveryBackendToggle,
    runDiscoveryToggle,
    runSelectedDeviceAction,
  } = useDevicesController(client, {
    sharedSelectedDeviceId,
    onSelectionChange: onSelectDevice,
  });

  const selectedSummary =
    devices.find((device) => String(device.id) === String(selectedDeviceId)) ?? null;
  const currentStatus = describeStatus(selectedDevice ?? selectedSummary ?? {});
  const currentTone = statusTone(currentStatus);
  const capabilitySummary =
    unifiedDiscoveryCapabilities?.casting_methods?.slice(0, 4).join(', ') ?? '—';

  return (
    <>
      <Panel
        title="Device control"
        subtitle="This screen now expands the mobile rewrite into a real operator view for discovery, runtime state, and per-device actions."
      >
        <View style={styles.actions}>
          <ActionButton
            label={loading ? 'Refreshing...' : 'Refresh devices'}
            onPress={() => void load()}
            disabled={loading}
          />
          <ActionButton
            label={discovering ? 'Discovering...' : 'Run discovery'}
            onPress={() => void discover()}
            disabled={discovering}
            variant="secondary"
          />
          <ActionButton
            label={discoveryPaused ? 'Resume loop' : 'Pause loop'}
            onPress={() => void runDiscoveryToggle()}
            disabled={actionLoadingKey === 'pause-discovery' || actionLoadingKey === 'resume-discovery'}
            variant="secondary"
          />
        </View>
        <Text style={styles.metaLine}>
          Health: {health?.status ?? 'unknown'}  •  Devices: {devices.length}  •  Discovery:{' '}
          {discoveryPaused ? 'paused' : 'running'}
        </Text>
        <Text style={styles.discoveryLine}>
          Authority: {formatValue(discoveryStatus?.authority)}  •  Unified running:{' '}
          {formatValue(discoveryStatus?.unified_running)}
        </Text>
        {actionMessage ? <Text style={styles.successText}>{actionMessage}</Text> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Unified discovery"
        subtitle="The mobile app also reads the shared `/api/v2/discovery` control plane so operators can see backend health and capability coverage."
      >
        <View style={styles.keyValueGrid}>
          <View style={styles.keyValueItem}>
            <Text style={styles.keyLabel}>System running</Text>
            <Text style={styles.keyValue}>
              {formatValue(unifiedDiscoveryStatus?.discovery_running)}
            </Text>
          </View>
          <View style={styles.keyValueItem}>
            <Text style={styles.keyLabel}>Online devices</Text>
            <Text style={styles.keyValue}>{formatValue(unifiedDiscoveryStatus?.online_devices)}</Text>
          </View>
          <View style={styles.keyValueItem}>
            <Text style={styles.keyLabel}>Active sessions</Text>
            <Text style={styles.keyValue}>{formatValue(unifiedDiscoveryStatus?.active_sessions)}</Text>
          </View>
          <View style={styles.keyValueItem}>
            <Text style={styles.keyLabel}>Casting methods</Text>
            <Text style={styles.keyValue}>{capabilitySummary}</Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Registered backends</Text>
        {discoveryBackends.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No discovery backend status returned.</Text>
        ) : null}
        {discoveryBackends.map((backend) => (
          <View key={String(backend.name ?? 'backend')} style={styles.backendCard}>
            <View style={styles.deviceCardHeader}>
              <Text style={styles.deviceName}>{formatValue(backend.name, 'Backend')}</Text>
              <View
                style={[
                  styles.statusBadge,
                  {
                    borderColor: backend.active ? colors.success : colors.warning,
                  },
                ]}
              >
                <Text
                  style={[
                    styles.statusBadgeLabel,
                    {
                      color: backend.active ? colors.success : colors.warning,
                    },
                  ]}
                >
                  {backend.active ? 'active' : 'idle'}
                </Text>
              </View>
            </View>
            <Text style={styles.detailText}>Enabled: {formatValue(backend.enabled)}</Text>
            <Text style={styles.detailText}>Healthy: {formatValue(backend.healthy)}</Text>
            {backend.last_seen ? (
              <Text style={styles.detailText}>Last seen: {backend.last_seen}</Text>
            ) : null}
            {backend.name ? (
              <View style={styles.actions}>
                <ActionButton
                  label={
                    actionLoadingKey ===
                    `${backend.enabled ? 'disable' : 'enable'}-backend-${backend.name}`
                      ? backend.enabled
                        ? 'Disabling...'
                        : 'Enabling...'
                      : backend.enabled
                        ? 'Disable backend'
                        : 'Enable backend'
                  }
                  onPress={() =>
                    void runDiscoveryBackendToggle(
                      backend.name ?? '',
                      typeof backend.enabled === 'boolean' ? backend.enabled : null,
                    )
                  }
                  disabled={
                    actionLoadingKey !== null &&
                    actionLoadingKey !==
                      `${backend.enabled ? 'disable' : 'enable'}-backend-${backend.name}`
                  }
                  variant="secondary"
                />
              </View>
            ) : null}
          </View>
        ))}
      </Panel>

      <Panel
        title="Inventory"
        subtitle="Tap a device to inspect richer detail and operator actions without leaving the separate mobile app."
      >
        {devices.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No devices returned by the backend yet.</Text>
        ) : null}

        {devices.map((device) => {
          const selected = String(device.id) === String(selectedDeviceId);
          const deviceStatus = describeStatus(device);
          const tone = statusTone(deviceStatus);
          return (
            <Pressable
              key={String(device.id ?? describeDevice(device))}
              accessibilityRole="button"
              onPress={() => selectDevice(device.id ?? null)}
              style={[styles.deviceCard, selected && styles.selectedDeviceCard]}
            >
              <View style={styles.deviceCardHeader}>
                <Text style={styles.deviceName}>{describeDevice(device)}</Text>
                <View style={[styles.statusBadge, { borderColor: statusColors[tone] }]}>
                  <Text style={[styles.statusBadgeLabel, { color: statusColors[tone] }]}>
                    {deviceStatus}
                  </Text>
                </View>
              </View>
              <Text style={styles.detailText}>Type: {formatValue(device.type)}</Text>
              <Text style={styles.detailText}>Host: {formatValue(device.hostname)}</Text>
              <Text style={styles.detailText}>
                Playback: {device.is_playing ? 'playing' : 'idle'}
              </Text>
              {device.current_media_title || device.current_video ? (
                <Text style={styles.detailText}>
                  Media: {String(device.current_media_title ?? device.current_video)}
                </Text>
              ) : null}
            </Pressable>
          );
        })}
      </Panel>

      <Panel
        title={selectedSummary ? `Selected device: ${describeDevice(selectedSummary)}` : 'Device detail'}
        subtitle="The first parity slice focuses on status, control mode, and safe playback/runtime actions using the existing backend routes."
      >
        {selectedSummary === null ? (
          <Text style={styles.emptyText}>Select a device from the inventory to inspect it.</Text>
        ) : (
          <>
            <View style={styles.deviceCardHeader}>
              <Text style={styles.sectionTitle}>Runtime state</Text>
              <View style={[styles.statusBadge, { borderColor: statusColors[currentTone] }]}>
                <Text style={[styles.statusBadgeLabel, { color: statusColors[currentTone] }]}>
                  {currentStatus}
                </Text>
              </View>
            </View>

            <View style={styles.keyValueGrid}>
              <View style={styles.keyValueItem}>
                <Text style={styles.keyLabel}>Availability</Text>
                <Text style={styles.keyValue}>{formatValue(selectedDevice?.availability)}</Text>
              </View>
              <View style={styles.keyValueItem}>
                <Text style={styles.keyLabel}>Control mode</Text>
                <Text style={styles.keyValue}>{formatValue(controlMode?.mode)}</Text>
              </View>
              <View style={styles.keyValueItem}>
                <Text style={styles.keyLabel}>Host</Text>
                <Text style={styles.keyValue}>{formatValue(selectedDevice?.hostname)}</Text>
              </View>
              <View style={styles.keyValueItem}>
                <Text style={styles.keyLabel}>Manufacturer</Text>
                <Text style={styles.keyValue}>{formatValue(selectedDevice?.manufacturer)}</Text>
              </View>
              <View style={styles.keyValueItem}>
                <Text style={styles.keyLabel}>Playback position</Text>
                <Text style={styles.keyValue}>{formatValue(selectedDevice?.playback_position)}</Text>
              </View>
              <View style={styles.keyValueItem}>
                <Text style={styles.keyLabel}>Streaming URL</Text>
                <Text style={styles.keyValue}>{formatValue(selectedDevice?.streaming_url)}</Text>
              </View>
              <View style={styles.keyValueItem}>
                <Text style={styles.keyLabel}>Seen seconds ago</Text>
                <Text style={styles.keyValue}>
                  {formatValue(selectedDevice?.seconds_since_seen)}
                </Text>
              </View>
              <View style={styles.keyValueItem}>
                <Text style={styles.keyLabel}>Overlay cast</Text>
                <Text style={styles.keyValue}>
                  {formatValue(selectedDevice?.overlay_cast_status ?? selectedDevice?.active_overlay_cast)}
                </Text>
              </View>
              <View style={styles.keyValueItem}>
                <Text style={styles.keyLabel}>Updated at</Text>
                <Text style={styles.keyValue}>{formatValue(selectedDevice?.updated_at)}</Text>
              </View>
              <View style={styles.keyValueItem}>
                <Text style={styles.keyLabel}>Location</Text>
                <Text style={styles.keyValue}>{formatValue(selectedDevice?.location)}</Text>
              </View>
            </View>

            {controlMode?.reason ? (
              <Text style={styles.noteText}>
                Control reason: {controlMode.reason}
                {controlMode.expires_at ? ` • Expires: ${controlMode.expires_at}` : ''}
              </Text>
            ) : null}

            <View style={styles.actions}>
              <ActionButton
                label={detailLoading ? 'Refreshing detail...' : 'Refresh detail'}
                onPress={() => void refreshSelectedDevice()}
                disabled={detailLoading}
                variant="secondary"
              />
              <ActionButton
                label="Manual mode"
                onPress={() =>
                  activeDeviceId !== null && activeDeviceId !== undefined
                    ? void runSelectedDeviceAction('manual-mode', (deviceId) =>
                        client.enableManualMode(deviceId, {
                          reason: 'mobile_operator',
                          expiresIn: 1800,
                        }),
                      )
                    : undefined
                }
                disabled={
                  activeDeviceId === null ||
                  activeDeviceId === undefined ||
                  actionLoadingKey === 'manual-mode'
                }
              />
              <ActionButton
                label="Auto mode"
                onPress={() =>
                  activeDeviceId !== null && activeDeviceId !== undefined
                    ? void runSelectedDeviceAction('auto-mode', (deviceId) =>
                        client.enableAutoMode(deviceId),
                      )
                    : undefined
                }
                disabled={
                  activeDeviceId === null ||
                  activeDeviceId === undefined ||
                  actionLoadingKey === 'auto-mode'
                }
                variant="secondary"
              />
              <ActionButton
                label="Pause playback"
                onPress={() =>
                  activeDeviceId !== null && activeDeviceId !== undefined
                    ? void runSelectedDeviceAction('pause-playback', (deviceId) =>
                        client.pauseDevicePlayback(deviceId),
                      )
                    : undefined
                }
                disabled={
                  activeDeviceId === null ||
                  activeDeviceId === undefined ||
                  actionLoadingKey === 'pause-playback'
                }
                variant="secondary"
              />
              <ActionButton
                label="Stop playback"
                onPress={() =>
                  activeDeviceId !== null && activeDeviceId !== undefined
                    ? void runSelectedDeviceAction('stop-playback', (deviceId) =>
                        client.stopDevicePlayback(deviceId),
                      )
                    : undefined
                }
                disabled={
                  activeDeviceId === null ||
                  activeDeviceId === undefined ||
                  actionLoadingKey === 'stop-playback'
                }
                variant="secondary"
              />
            </View>

            <Text style={styles.noteText}>
              Mobile stays thin here: device discovery, control mode, and playback actions still
              flow through the shared FastAPI runtime rather than duplicating business logic on-device.
            </Text>
          </>
        )}
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metaLine: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: '600',
  },
  discoveryLine: {
    color: colors.mutedText,
    fontSize: 12,
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
  deviceCard: {
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    backgroundColor: colors.elevatedPanel,
  },
  selectedDeviceCard: {
    borderColor: colors.accent,
    backgroundColor: colors.accentMuted,
  },
  deviceCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
  },
  deviceName: {
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
  statusBadge: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
    backgroundColor: colors.background,
  },
  statusBadgeLabel: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  sectionTitle: {
    flex: 1,
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  keyValueGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  keyValueItem: {
    minWidth: 140,
    flexGrow: 1,
    gap: 4,
    backgroundColor: colors.elevatedPanel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 12,
  },
  keyLabel: {
    color: colors.mutedText,
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  keyValue: {
    color: colors.text,
    fontSize: 13,
    lineHeight: 18,
  },
  noteText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  backendCard: {
    gap: 6,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
});
