import { StyleSheet, Text, View } from 'react-native';

import {
  currentProductAreas,
  mobileModules,
  mobileRewritePrinciples,
} from '../data/features';
import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { type ControlPlaneClient } from '../control-plane/client';
import type { AppMode } from '../control-plane/localState';
import { useOverviewController } from '../features/overview/useOverviewController';
import { colors } from '../theme';

interface OverviewScreenProps {
  appMode: AppMode;
  apiBaseUrl: string;
  client: ControlPlaneClient;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

export function OverviewScreen({ apiBaseUrl, appMode, client }: OverviewScreenProps) {
  const { devices, error, health, load, loading, projections, renderers, streaming, unifiedDiscovery } =
    useOverviewController(client);

  const summaryCards = [
    { label: 'Health', value: health?.status ?? 'unknown' },
    { label: 'Devices', value: devices.length },
    { label: 'Online devices', value: unifiedDiscovery?.online_devices ?? 'n/a' },
    { label: 'Active sessions', value: streaming?.active_sessions ?? streaming?.session_count ?? 0 },
    { label: 'Renderers', value: renderers.length },
    { label: 'Projection configs', value: projections.length },
  ];

  return (
    <>
      <Panel
        title="Rewrite target"
        subtitle="This mobile app now targets a local-first control plane with the backend retained only as a migration fallback."
      >
        <Text style={styles.body}>
          Local mode keeps the operator console usable with no backend server by moving workflow
          state, saved configuration, and local-safe control flows on-device. Remote mode keeps the
          existing FastAPI adapter available while the rewrite is still in flight.
        </Text>
        <Text style={styles.apiLine}>
          Active mode: {appMode} {appMode === 'remote' ? `• Fallback API: ${apiBaseUrl}` : ''}
        </Text>
      </Panel>

      <Panel
        title="Live backend summary"
        subtitle="Overview now summarizes whichever control-plane mode is active, so the app stays useful even when the backend is off."
      >
        <View style={styles.actionsRow}>
          <Text style={styles.metaLine}>
            Discovery running: {formatValue(unifiedDiscovery?.discovery_running)}
          </Text>
          <Text style={styles.metaLine}>
            Backends: {formatValue(unifiedDiscovery?.backends ? Object.keys(unifiedDiscovery.backends).length : 0)}
          </Text>
        </View>
        <View style={styles.metricGrid}>
          {summaryCards.map((card) => (
            <View key={card.label} style={styles.metricCard}>
              <Text style={styles.metricValue}>{String(card.value)}</Text>
              <Text style={styles.metricLabel}>{card.label}</Text>
            </View>
          ))}
        </View>
        <View style={styles.actionsRow}>
          <Text style={styles.body}>
            Bandwidth Mbps: {formatValue(streaming?.total_bandwidth_mbps, 'n/a')}
          </Text>
          <ActionButton
            label={loading ? 'Refreshing…' : 'Refresh'}
            onPress={() => void load()}
            disabled={loading}
            variant="secondary"
          />
        </View>
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Current product areas"
        subtitle="These are the main capabilities already present in the web + Python stack."
      >
        {currentProductAreas.map((item) => (
          <View key={item.title} style={styles.card}>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.body}>{item.description}</Text>
            <Text style={styles.endpointLine}>{item.endpoints.join('  •  ')}</Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="Mobile modules"
        subtitle="The current mobile rewrite focuses on operator workflows with live backend reuse."
      >
        {mobileModules.map((module) => (
          <View key={module.title} style={styles.card}>
            <Text style={styles.cardTitle}>{module.title}</Text>
            <Text style={styles.body}>{module.description}</Text>
            <Text style={styles.endpointLine}>{module.endpoints.join('  •  ')}</Text>
          </View>
        ))}
      </Panel>

      <Panel title="Rewrite rules">
        {mobileRewritePrinciples.map((principle) => (
          <View key={principle} style={styles.ruleRow}>
            <View style={styles.ruleDot} />
            <Text style={styles.ruleText}>{principle}</Text>
          </View>
        ))}
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  body: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  apiLine: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: '600',
  },
  actionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: 10,
  },
  metaLine: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: '600',
  },
  metricGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metricCard: {
    minWidth: 96,
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
  errorText: {
    color: colors.danger,
    fontSize: 13,
    lineHeight: 18,
  },
  card: {
    gap: 6,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  cardTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  endpointLine: {
    color: colors.accent,
    fontSize: 12,
    lineHeight: 18,
  },
  ruleRow: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'flex-start',
  },
  ruleDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    backgroundColor: colors.accent,
    marginTop: 6,
  },
  ruleText: {
    flex: 1,
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
});
