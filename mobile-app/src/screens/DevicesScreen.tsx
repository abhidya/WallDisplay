import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { colors } from '../theme';
import type { DeviceSummary, HealthResponse } from '../types/api';
import { NanoDlnaApiClient } from '../services/api';

interface DevicesScreenProps {
  client: NanoDlnaApiClient;
}

function describeDevice(device: DeviceSummary): string {
  return (
    (typeof device.friendly_name === 'string' && device.friendly_name) ||
    (typeof device.device_name === 'string' && device.device_name) ||
    (typeof device.name === 'string' && device.name) ||
    `Device ${String(device.id ?? 'unknown')}`
  );
}

export function DevicesScreen({ client }: DevicesScreenProps) {
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthPayload, devicePayload] = await Promise.all([
        client.getHealth(),
        client.listDevices(),
      ]);
      setHealth(healthPayload);
      setDevices(devicePayload);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load devices.');
    } finally {
      setLoading(false);
    }
  }, [client]);

  const discover = useCallback(async () => {
    setDiscovering(true);
    setError(null);
    try {
      await client.discoverDevices();
      await load();
    } catch (discoverError) {
      setError(
        discoverError instanceof Error ? discoverError.message : 'Device discovery failed.',
      );
    } finally {
      setDiscovering(false);
    }
  }, [client, load]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <Panel
        title="Device control"
        subtitle="This screen reuses the current discovery and inventory endpoints already used by the web dashboard."
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
        </View>
        <Text style={styles.metaLine}>
          Health: {health?.status ?? 'unknown'}  •  Devices: {devices.length}
        </Text>
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Inventory"
        subtitle="Playback state and streaming details surface here first before deeper mobile controls are added."
      >
        {devices.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No devices returned by the backend yet.</Text>
        ) : null}

        {devices.map((device) => (
          <View key={String(device.id ?? describeDevice(device))} style={styles.deviceCard}>
            <Text style={styles.deviceName}>{describeDevice(device)}</Text>
            <Text style={styles.detailText}>
              State: {String(device.playback_state ?? 'unknown')}
            </Text>
            {device.current_media_title || device.current_video ? (
              <Text style={styles.detailText}>
                Media: {String(device.current_media_title ?? device.current_video)}
              </Text>
            ) : null}
            {device.location ? (
              <Text style={styles.detailText}>Location: {String(device.location)}</Text>
            ) : null}
            {device.streaming_url ? (
              <Text style={styles.detailText}>
                Stream: {String(device.streaming_url)}
              </Text>
            ) : null}
          </View>
        ))}
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
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  deviceName: {
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
