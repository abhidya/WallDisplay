import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { currentProductAreas } from '../data/features';
import { colors } from '../theme';
import type { StreamingAnalytics } from '../types/api';
import { NanoDlnaApiClient } from '../services/api';

interface OperationsScreenProps {
  client: NanoDlnaApiClient;
}

export function OperationsScreen({ client }: OperationsScreenProps) {
  const [analytics, setAnalytics] = useState<StreamingAnalytics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAnalytics(await client.getStreamingAnalytics());
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : 'Failed to load analytics.',
      );
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
        title="Operations and diagnostics"
        subtitle="This tab keeps advanced backend capabilities visible while the mobile UX is being rewritten in stages."
      >
        <ActionButton
          label={loading ? 'Refreshing...' : 'Refresh analytics'}
          onPress={() => void load()}
          disabled={loading}
        />
        {analytics ? (
          <View style={styles.metricGrid}>
            <View style={styles.metricCard}>
              <Text style={styles.metricValue}>
                {String(analytics.active_sessions ?? analytics.session_count ?? 0)}
              </Text>
              <Text style={styles.metricLabel}>Active sessions</Text>
            </View>
            <View style={styles.metricCard}>
              <Text style={styles.metricValue}>
                {String(analytics.overlay_sessions ?? 0)}
              </Text>
              <Text style={styles.metricLabel}>Overlay sessions</Text>
            </View>
            <View style={styles.metricCard}>
              <Text style={styles.metricValue}>
                {String(analytics.total_bandwidth_mbps ?? 'n/a')}
              </Text>
              <Text style={styles.metricLabel}>Bandwidth Mbps</Text>
            </View>
          </View>
        ) : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Feature migration queue"
        subtitle="The existing platform already has broader capabilities than the first mobile pass."
      >
        {currentProductAreas.map((item) => (
          <View key={item.title} style={styles.featureCard}>
            <Text style={styles.featureTitle}>{item.title}</Text>
            <Text style={styles.featureDescription}>{item.description}</Text>
            <Text style={styles.endpointLine}>{item.endpoints.join('  •  ')}</Text>
          </View>
        ))}
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  metricGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metricCard: {
    minWidth: 120,
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
    fontSize: 22,
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
  featureCard: {
    gap: 6,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  featureTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  featureDescription: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  endpointLine: {
    color: colors.accent,
    fontSize: 12,
    lineHeight: 18,
  },
});
