import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { useLogsController } from '../features/logs/useLogsController';
import type { AppMode } from '../control-plane/localState';
import { colors } from '../theme';
import type { JsonRecord } from '../types/api';

interface LogsScreenProps {
  apiBaseUrl: string;
  appMode: AppMode;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

function describeLog(log: JsonRecord): string {
  return String(log.message ?? 'Log entry');
}

export function LogsScreen({ apiBaseUrl, appMode }: LogsScreenProps) {
  const {
    error,
    levels,
    loading,
    logs,
    search,
    selectedSource,
    setSearch,
    setSelectedSource,
    sources,
    stats,
    tail,
    refresh,
  } = useLogsController({ apiBaseUrl, appMode });

  if (appMode === 'local') {
    return (
      <Panel
        title="Logs"
        subtitle="The aggregated log viewer is remote-only because the backend owns the log aggregation service."
      >
        <Text style={styles.noteText}>
          Switch to remote mode to inspect backend/frontend log history, source stats, and tailed source output.
        </Text>
      </Panel>
    );
  }

  return (
    <>
      <Panel
        title="Logs"
        subtitle="A compact mobile log viewer for backend/frontend aggregated logs."
      >
        <View style={styles.actionsRow}>
          <ActionButton
            label={loading ? 'Refreshing...' : 'Refresh logs'}
            onPress={() => void refresh()}
            disabled={loading}
          />
        </View>
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Filters"
        subtitle="Filter the aggregated log feed by source and search term."
      >
        <TextInput
          onChangeText={setSearch}
          placeholder="Search logs..."
          placeholderTextColor={colors.mutedText}
          style={styles.input}
          value={search}
        />
        <Text style={styles.sectionTitle}>Sources</Text>
        <View style={styles.selectionGrid}>
          {sources.map((source) => {
            const selected = source === selectedSource;
            return (
              <Pressable
                key={source}
                accessibilityRole="button"
                onPress={() => setSelectedSource(source)}
                style={[styles.selectionCard, selected && styles.selectionCardActive]}
              >
                <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                  {source}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={styles.detailText}>Levels: {levels.join(' • ') || '—'}</Text>
      </Panel>

      <Panel
        title="Log stats"
        subtitle="High-level backend aggregation stats from `/api/logs/stats`."
      >
        <View style={styles.metricGrid}>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(stats?.total_logs, '0')}</Text>
            <Text style={styles.metricLabel}>Total logs</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(stats?.recent_logs_1h, '0')}</Text>
            <Text style={styles.metricLabel}>Recent 1h</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(stats?.active_websockets, '0')}</Text>
            <Text style={styles.metricLabel}>Active websockets</Text>
          </View>
        </View>
      </Panel>

      <Panel
        title="Recent logs"
        subtitle="Recent aggregated log entries from the selected source/history view."
      >
        {logs.length === 0 ? <Text style={styles.emptyText}>No logs returned yet.</Text> : null}
        {logs.slice(0, 20).map((log, index) => (
          <View key={`${String(log.timestamp ?? index)}-${index}`} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{formatValue(log.level, 'INFO')}</Text>
            <Text style={styles.detailText}>
              {formatValue(log.source)} • {formatValue(log.logger_name)}
            </Text>
            <Text style={styles.detailText}>{describeLog(log)}</Text>
          </View>
        ))}
      </Panel>

      <Panel
        title={`Tail: ${selectedSource || 'source'}`}
        subtitle="Recent tailed output from the selected log source."
      >
        {tail.length === 0 ? <Text style={styles.emptyText}>No tailed logs available.</Text> : null}
        {tail.slice(0, 20).map((log, index) => (
          <View key={`${String(log.timestamp ?? index)}-${index}`} style={styles.itemCard}>
            <Text style={styles.detailText}>
              {formatValue(log.timestamp)} • {formatValue(log.level)}
            </Text>
            <Text style={styles.codeBlock}>{describeLog(log)}</Text>
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
  errorText: {
    color: colors.danger,
    fontSize: 13,
    lineHeight: 18,
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
  sectionTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  selectionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  selectionCard: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 999,
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
    fontSize: 13,
    fontWeight: '600',
  },
  selectionTitleActive: {
    color: colors.accent,
  },
  detailText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  metricGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metricCard: {
    minWidth: 100,
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
  codeBlock: {
    color: colors.text,
    fontSize: 12,
    lineHeight: 18,
    fontFamily: 'Courier',
    backgroundColor: colors.elevatedPanel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 12,
  },
});
