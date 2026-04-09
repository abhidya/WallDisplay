import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { emulatorConnectionNotes } from '../data/features';
import {
  useSettingsController,
} from '../features/settings/useSettingsController';
import type { ProjectorRedirectRule } from '../features/settings/helpers.ts';
import type { ControlPlaneClient } from '../control-plane/client';
import type { AppMode } from '../control-plane/localState';
import { colors } from '../theme';
import type { JsonRecord } from '../types/api';

interface SettingsScreenProps {
  apiBaseUrl: string;
  appMode: AppMode;
  client: ControlPlaneClient;
  hydrated: boolean;
  onApplyApiBaseUrl: (value: string) => void;
  onApplyAppMode: (mode: AppMode) => void;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

function renderRuleLabel(rule: ProjectorRedirectRule): string {
  return rule.name || rule.client_ip || rule.id;
}

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

export function SettingsScreen({
  apiBaseUrl,
  appMode,
  client,
  hydrated,
  onApplyApiBaseUrl,
  onApplyAppMode,
}: SettingsScreenProps) {
  const {
    actionMessage,
    adminError,
    adminLoading,
    diagnosticsLoading,
    draftValue,
    error,
    globalApiConfigs,
    health,
    incidentDetailLoading,
    loading,
    normalized,
    projectorRedirect,
    recentProjectorRequests,
    refreshConnection,
    refreshRemoteAdmin,
    saveRemoteAdmin,
    selectedIncidentDetail,
    selectedIncidentId,
    serviceDiagnostics,
    setDraftValue,
    setSelectedIncidentId,
    toggleProjectorRedirectEnabled,
    unifiedDiscovery,
    updateGlobalApiConfig,
    updateProjectorRedirectRule,
    addProjectorRedirectRule,
    removeProjectorRedirectRule,
  } = useSettingsController(client, { apiBaseUrl, appMode });

  const recentIncidents = Array.isArray(serviceDiagnostics?.recent_incidents)
    ? serviceDiagnostics.recent_incidents
    : [];
  const currentRun = asRecord(serviceDiagnostics?.current_run);
  const relatedLogs = Array.isArray(selectedIncidentDetail?.related_logs)
    ? selectedIncidentDetail.related_logs
    : [];
  const selectedIncident = asRecord(selectedIncidentDetail?.incident);

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Panel
        title="Control-plane mode"
        subtitle="Local mode keeps the app useful with no backend. Remote mode preserves the existing FastAPI adapter for fallback and migration."
      >
        <View style={styles.modeRow}>
          {(['local', 'remote'] as AppMode[]).map((mode) => {
            const active = mode === appMode;
            return (
              <Pressable
                key={mode}
                accessibilityRole="button"
                onPress={() => onApplyAppMode(mode)}
                style={[styles.modeCard, active && styles.modeCardActive]}
              >
                <Text style={[styles.modeTitle, active && styles.modeTitleActive]}>{mode}</Text>
                <Text style={styles.modeBody}>
                  {mode === 'local'
                    ? 'On-device control plane, saved config, local-safe workflows, and no backend requirement.'
                    : 'Use the existing FastAPI control plane through the migration adapter.'}
                </Text>
              </Pressable>
            );
          })}
        </View>
        {!hydrated ? (
          <Text style={styles.noteText}>Restoring saved control-plane preferences…</Text>
        ) : null}
      </Panel>

      <Panel
        title="Remote fallback target"
        subtitle="Keep the backend URL ready for remote mode. The app normalizes the value to an /api endpoint."
      >
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          onChangeText={setDraftValue}
          placeholder="http://127.0.0.1:8000/api"
          placeholderTextColor={colors.mutedText}
          returnKeyType="done"
          style={styles.input}
          value={draftValue}
        />
        <Text style={styles.normalizedLabel}>Normalized: {normalized}</Text>
        <View style={styles.actionsRow}>
          <ActionButton label="Apply base URL" onPress={() => onApplyApiBaseUrl(draftValue)} />
          <ActionButton
            label={loading ? 'Checking...' : appMode === 'local' ? 'Check local mode' : 'Test remote mode'}
            onPress={() => void refreshConnection()}
            disabled={loading}
            variant="secondary"
          />
        </View>
        {actionMessage ? <Text style={styles.successText}>{actionMessage}</Text> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Control-plane diagnostics"
        subtitle="Use the active mode to confirm local readiness or remote connectivity before running device, media, or operations workflows."
      >
        <View style={styles.metricGrid}>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(health?.status, 'unknown')}</Text>
            <Text style={styles.metricLabel}>Health</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(appMode)}</Text>
            <Text style={styles.metricLabel}>Mode</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(unifiedDiscovery?.online_devices)}</Text>
            <Text style={styles.metricLabel}>Devices</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(unifiedDiscovery?.active_sessions)}</Text>
            <Text style={styles.metricLabel}>Sessions</Text>
          </View>
        </View>
        <Text style={styles.noteText}>
          Registered backends:{' '}
          {formatValue(unifiedDiscovery?.backends ? Object.keys(unifiedDiscovery.backends).length : 0)}
        </Text>
      </Panel>

      <Panel
        title="Remote backend admin"
        subtitle="This mobile slice now surfaces key backend settings, projector redirect rules, and service diagnostics from the legacy web Settings page."
      >
        <View style={styles.actionsRow}>
          <ActionButton
            label={adminLoading ? 'Refreshing...' : 'Refresh remote admin'}
            onPress={() => void refreshRemoteAdmin(true)}
            disabled={appMode !== 'remote' || adminLoading}
            variant="secondary"
          />
          <ActionButton
            label={adminLoading ? 'Saving...' : 'Save remote settings'}
            onPress={() => void saveRemoteAdmin()}
            disabled={appMode !== 'remote' || adminLoading}
          />
        </View>
        {appMode !== 'remote' ? (
          <Text style={styles.noteText}>
            Switch to remote mode to inspect or change backend-owned admin settings.
          </Text>
        ) : null}
        {adminError ? <Text style={styles.errorText}>{adminError}</Text> : null}
      </Panel>

      <Panel
        title="Global API configs"
        subtitle="A compact mobile editor for the highest-value API config fields used by overlay and transit widgets."
      >
        {[
          ['weather_api_key', 'Weather API key'],
          ['transit_stop_id', 'Transit stop ID'],
          ['timezone', 'Timezone'],
        ].map(([key, label]) => (
          <View key={key} style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>{label}</Text>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              onChangeText={(value) => updateGlobalApiConfig(key, value)}
              placeholder={label}
              placeholderTextColor={colors.mutedText}
              style={styles.input}
              value={String(globalApiConfigs[key] ?? '')}
            />
          </View>
        ))}
      </Panel>

      <Panel
        title="Projector redirect"
        subtitle="Edit the backend’s projector redirect rules and inspect recent matched requests."
      >
        <View style={styles.switchRow}>
          <Text style={styles.fieldLabel}>Enable projector auto-redirect</Text>
          <Switch
            value={projectorRedirect.enabled}
            onValueChange={toggleProjectorRedirectEnabled}
          />
        </View>

        <View style={styles.actionsRow}>
          <ActionButton
            label="Add rule"
            onPress={() => addProjectorRedirectRule()}
            disabled={appMode !== 'remote'}
            variant="secondary"
          />
        </View>

        {projectorRedirect.rules.map((rule) => (
          <View key={rule.id} style={styles.ruleCard}>
            <View style={styles.ruleHeader}>
              <Text style={styles.ruleTitle}>{renderRuleLabel(rule)}</Text>
              <Pressable
                accessibilityRole="button"
                onPress={() => removeProjectorRedirectRule(rule.id)}
                style={styles.ruleDelete}
              >
                <Text style={styles.ruleDeleteText}>Remove</Text>
              </Pressable>
            </View>
            <View style={styles.switchRow}>
              <Text style={styles.noteText}>Rule enabled</Text>
              <Switch
                value={rule.enabled}
                onValueChange={(enabled) => updateProjectorRedirectRule(rule.id, { enabled })}
              />
            </View>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              onChangeText={(value) => updateProjectorRedirectRule(rule.id, { name: value })}
              placeholder="Rule name"
              placeholderTextColor={colors.mutedText}
              style={styles.input}
              value={rule.name}
            />
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              onChangeText={(value) => updateProjectorRedirectRule(rule.id, { client_ip: value })}
              placeholder="Client IP"
              placeholderTextColor={colors.mutedText}
              style={styles.input}
              value={rule.client_ip}
            />
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              onChangeText={(value) => updateProjectorRedirectRule(rule.id, { target_path: value })}
              placeholder="Redirect target path"
              placeholderTextColor={colors.mutedText}
              style={styles.input}
              value={rule.target_path}
            />
          </View>
        ))}

        <Text style={styles.sectionTitle}>Recent projector requests</Text>
        {recentProjectorRequests.length === 0 ? (
          <Text style={styles.emptyText}>No recent projector client requests recorded yet.</Text>
        ) : null}
        {recentProjectorRequests.slice(0, 8).map((item, index) => (
          <View key={`${String(item.timestamp ?? index)}-${index}`} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{formatValue(item.client_ip, 'Unknown client')}</Text>
            <Text style={styles.detailText}>
              {formatValue(item.method, 'GET')} {formatValue(item.path, '/')}
              {item.query ? `?${String(item.query)}` : ''}
            </Text>
            <Text style={styles.detailText}>
              Rule: {formatValue(item.matched_rule_name)} • Redirect:{' '}
              {item.redirected ? formatValue(item.redirect_target) : 'no'}
            </Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="Service diagnostics"
        subtitle="Track current uptime, recent restart incidents, and nearby logs from the backend diagnostics service."
      >
        <View style={styles.metricGrid}>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(currentRun?.status, 'unknown')}</Text>
            <Text style={styles.metricLabel}>Backend status</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{formatValue(currentRun?.uptime_seconds, '—')}</Text>
            <Text style={styles.metricLabel}>Uptime seconds</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{String(recentIncidents.length)}</Text>
            <Text style={styles.metricLabel}>Recent incidents</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>
              {formatValue(Array.isArray(serviceDiagnostics?.supervisor_events) ? serviceDiagnostics?.supervisor_events.length : 0)}
            </Text>
            <Text style={styles.metricLabel}>Supervisor events</Text>
          </View>
        </View>

        {diagnosticsLoading ? <Text style={styles.noteText}>Refreshing diagnostics…</Text> : null}

        <Text style={styles.sectionTitle}>Recent incidents</Text>
        {recentIncidents.length === 0 ? (
          <Text style={styles.emptyText}>No restart incidents recorded yet.</Text>
        ) : null}
        {recentIncidents.map((incident, index) => {
          const incidentId = String(incident.incident_id ?? `${index}`);
          const selected = incidentId === selectedIncidentId;
          return (
            <Pressable
              key={incidentId}
              accessibilityRole="button"
              onPress={() => setSelectedIncidentId(incidentId)}
              style={[styles.selectionCard, selected && styles.selectionCardActive]}
            >
              <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                {formatValue(incident.failure_message ?? incident.reason, 'Restart incident')}
              </Text>
              <Text style={styles.detailText}>
                Failed at: {formatValue(incident.failed_at)}
              </Text>
              <Text style={styles.detailText}>
                Duration: {formatValue(incident.duration_seconds)}
              </Text>
            </Pressable>
          );
        })}

        <Text style={styles.sectionTitle}>Selected incident detail</Text>
        {incidentDetailLoading ? (
          <Text style={styles.noteText}>Loading incident detail…</Text>
        ) : selectedIncident ? (
          <View style={styles.itemCard}>
            <Text style={styles.itemTitle}>
              {formatValue(selectedIncident.failure_message ?? selectedIncident.reason)}
            </Text>
            <Text style={styles.detailText}>
              Failed at: {formatValue(selectedIncident.failed_at)}
            </Text>
            <Text style={styles.detailText}>
              Recovered at: {formatValue(selectedIncident.recovered_at)}
            </Text>
            <Text style={styles.detailText}>
              Source: {formatValue(selectedIncident.failure_source)}
            </Text>
            <Text style={styles.codeBlock}>
              {formatValue(
                selectedIncident.traceback,
                'No traceback was captured before the restart.',
              )}
            </Text>
          </View>
        ) : (
          <Text style={styles.emptyText}>Pick a restart incident to inspect traceback and nearby logs.</Text>
        )}

        <Text style={styles.sectionTitle}>Nearby logs</Text>
        {relatedLogs.length === 0 ? (
          <Text style={styles.emptyText}>No related log window captured for this incident yet.</Text>
        ) : null}
        {relatedLogs.slice(0, 6).map((entry, index) => (
          <View key={`${String(entry.timestamp ?? index)}-${index}`} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{formatValue(entry.log_file, 'Log')}</Text>
            <Text style={styles.detailText}>{formatValue(entry.timestamp)}</Text>
            <Text style={styles.codeBlock}>{formatValue(entry.text)}</Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="Connection notes"
        subtitle="Remote fallback still matters because simulator, emulator, and physical hardware resolve localhost differently."
      >
        {emulatorConnectionNotes.map((note) => (
          <View key={note} style={styles.noteRow}>
            <View style={styles.noteDot} />
            <Text style={styles.noteText}>{note}</Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="Execution lane"
        subtitle="This iteration now includes device parity, media parity, operations diagnostics, and backend admin visibility inside the mobile app."
      >
        <Text style={styles.commandText}>
          Source of truth: .omx/plans/prd-local-control-plane-mobile-rewrite.md
        </Text>
      </Panel>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: 16,
    paddingBottom: 16,
  },
  modeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  modeCard: {
    minWidth: 180,
    flexGrow: 1,
    backgroundColor: colors.elevatedPanel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
    gap: 6,
  },
  modeCardActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentMuted,
  },
  modeTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    textTransform: 'capitalize',
  },
  modeTitleActive: {
    color: colors.accent,
  },
  modeBody: {
    color: colors.mutedText,
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
  actionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  normalizedLabel: {
    color: colors.accent,
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
  metricGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  metricCard: {
    minWidth: 110,
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
    textTransform: 'capitalize',
  },
  metricLabel: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: '600',
  },
  noteRow: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'flex-start',
  },
  noteDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    backgroundColor: colors.accent,
    marginTop: 6,
  },
  noteText: {
    flex: 1,
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  commandText: {
    color: colors.text,
    fontFamily: 'Courier',
    fontSize: 13,
    lineHeight: 20,
  },
  fieldGroup: {
    gap: 8,
  },
  fieldLabel: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '600',
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  ruleCard: {
    gap: 10,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.elevatedPanel,
  },
  ruleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  ruleTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    flex: 1,
  },
  ruleDelete: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.danger,
  },
  ruleDeleteText: {
    color: colors.danger,
    fontSize: 12,
    fontWeight: '700',
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
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
  detailText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
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
