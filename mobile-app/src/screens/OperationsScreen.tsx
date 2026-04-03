import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { useOperationsController } from '../features/operations/useOperationsController';
import { NanoDlnaApiClient } from '../services/api';
import { colors } from '../theme';
import type {
  MappingSceneSummary,
  OverlayConfigSummary,
  ProjectionConfigSummary,
  RendererProjectorSummary,
  RendererSceneSummary,
  SceneControlPresetSummary,
  SceneRankSummary,
  StreamingSessionSummary,
} from '../types/api';

interface OperationsScreenProps {
  client: NanoDlnaApiClient;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

function describeSession(session: StreamingSessionSummary): string {
  return (
    (typeof session.consumer_id === 'string' && session.consumer_id) ||
    (typeof session.device_name === 'string' && session.device_name) ||
    session.session_id ||
    'Session'
  );
}

function describeProjector(projector: RendererProjectorSummary): string {
  return (
    (typeof projector.name === 'string' && projector.name) ||
    projector.id ||
    'Projector'
  );
}

function describeScene(scene: RendererSceneSummary): string {
  return (
    (typeof scene.name === 'string' && scene.name) ||
    scene.id ||
    'Scene'
  );
}

function describeOverlayConfig(config: OverlayConfigSummary): string {
  return (
    (typeof config.name === 'string' && config.name) ||
    `Overlay ${String(config.id ?? 'unknown')}`
  );
}

function describeMappingScene(scene: MappingSceneSummary): string {
  return (
    (typeof scene.name === 'string' && scene.name) ||
    `Mapping scene ${String(scene.id ?? 'unknown')}`
  );
}

function describeSceneRank(rank: SceneRankSummary): string {
  return (
    (typeof rank.name === 'string' && rank.name) ||
    `Rank ${String(rank.id ?? 'unknown')}`
  );
}

function describeSceneControlPreset(preset: SceneControlPresetSummary): string {
  return (
    (typeof preset.name === 'string' && preset.name) ||
    `Preset ${String(preset.id ?? 'unknown')}`
  );
}

function describeProjectionConfig(config: ProjectionConfigSummary): string {
  return (
    (typeof config.name === 'string' && config.name) ||
    `Projection ${String(config.id ?? 'unknown')}`
  );
}

export function OperationsScreen({ client }: OperationsScreenProps) {
  const {
    actionLoadingKey,
    actionMessage,
    analytics,
    error,
    loading,
    load,
    launchSelectedProjection,
    mappingScenes,
    overlayConfigs,
    overlayStatus,
    projectors,
    projectionConfigs,
    recentProjectionSession,
    rendererScenes,
    renderers,
    runOverlaySync,
    runRendererPause,
    runRendererResume,
    runRendererStartDefault,
    runRendererStartWithScene,
    runRendererStop,
    sceneControlPresets,
    sceneRanks,
    selectProjectionConfig,
    selectProjector,
    selectScene,
    selectedProjectionConfigId,
    selectedProjectorId,
    selectedSceneId,
    sessions,
  } = useOperationsController(client);

  const metricCards = [
    {
      label: 'Active sessions',
      value: analytics?.active_sessions ?? analytics?.session_count ?? 0,
    },
    { label: 'Overlay sessions', value: analytics?.overlay_sessions ?? 0 },
    { label: 'Bandwidth Mbps', value: analytics?.total_bandwidth_mbps ?? 'n/a' },
    { label: 'Projectors', value: projectors.length },
    { label: 'Scenes', value: rendererScenes.length },
    { label: 'Mappings', value: mappingScenes.length },
    { label: 'Projection configs', value: projectionConfigs.length },
  ];

  const actionsBusy = loading || actionLoadingKey !== null;

  return (
    <>
      <Panel
        title="Operations and diagnostics"
        subtitle="The mobile rewrite now acts as an operator console for runtime visibility plus high-value renderer, overlay, mapping, and projection actions."
      >
        <View style={styles.actionsWrap}>
          <ActionButton
            label={loading ? 'Refreshing...' : 'Refresh operations'}
            onPress={() => void load()}
            disabled={loading}
          />
          <ActionButton
            label={actionLoadingKey === 'overlay-sync' ? 'Syncing...' : 'Trigger overlay sync'}
            onPress={() => void runOverlaySync()}
            disabled={loading || actionLoadingKey === 'overlay-sync'}
            variant="secondary"
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
        {actionMessage ? <Text style={styles.successText}>{actionMessage}</Text> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Renderer control"
        subtitle="Choose a projector and scene, then start default or explicit scene playback without leaving the mobile operator app."
      >
        <Text style={styles.sectionTitle}>Projectors</Text>
        <View style={styles.selectionGrid}>
          {projectors.length === 0 && !loading ? (
            <Text style={styles.emptyText}>No projectors configured.</Text>
          ) : null}
          {projectors.map((projector) => {
            const projectorId = projector.id ?? null;
            const selected = projectorId !== null && projectorId === selectedProjectorId;
            return (
              <Pressable
                key={String(projector.id ?? describeProjector(projector))}
                accessibilityRole="button"
                onPress={() => selectProjector(projectorId)}
                style={[styles.selectionCard, selected && styles.selectionCardActive]}
              >
                <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                  {describeProjector(projector)}
                </Text>
                <Text style={styles.detailText}>Type: {formatValue(projector.type)}</Text>
                <Text style={styles.detailText}>Host: {formatValue(projector.host)}</Text>
                <Text style={styles.detailText}>Default scene: {formatValue(projector.scene)}</Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.sectionTitle}>Scenes</Text>
        <View style={styles.selectionGrid}>
          {rendererScenes.length === 0 && !loading ? (
            <Text style={styles.emptyText}>No renderer scenes available.</Text>
          ) : null}
          {rendererScenes.map((scene) => {
            const sceneId = scene.id ?? null;
            const selected = sceneId !== null && sceneId === selectedSceneId;
            return (
              <Pressable
                key={String(scene.id ?? describeScene(scene))}
                accessibilityRole="button"
                onPress={() => selectScene(sceneId)}
                style={[styles.selectionCard, selected && styles.selectionCardActive]}
              >
                <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                  {describeScene(scene)}
                </Text>
                <Text style={styles.detailText}>
                  {formatValue(scene.description, 'No description')}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.metaLine}>
          Active selection: {formatValue(selectedProjectorId)} • Scene: {formatValue(selectedSceneId)}
        </Text>

        <View style={styles.actionsWrap}>
          <ActionButton
            label={actionLoadingKey === 'start-projector-default' ? 'Starting...' : 'Start default'}
            onPress={() => void runRendererStartDefault()}
            disabled={actionsBusy}
          />
          <ActionButton
            label={actionLoadingKey === 'start-renderer-scene' ? 'Starting...' : 'Start selected scene'}
            onPress={() => void runRendererStartWithScene()}
            disabled={actionsBusy}
            variant="secondary"
          />
          <ActionButton
            label={actionLoadingKey === 'pause-renderer' ? 'Pausing...' : 'Pause'}
            onPress={() => void runRendererPause()}
            disabled={actionsBusy}
            variant="secondary"
          />
          <ActionButton
            label={actionLoadingKey === 'resume-renderer' ? 'Resuming...' : 'Resume'}
            onPress={() => void runRendererResume()}
            disabled={actionsBusy}
            variant="secondary"
          />
          <ActionButton
            label={actionLoadingKey === 'stop-renderer' ? 'Stopping...' : 'Stop'}
            onPress={() => void runRendererStop()}
            disabled={actionsBusy}
            variant="secondary"
          />
        </View>

        <Text style={styles.sectionTitle}>Active renderers</Text>
        {renderers.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No active renderers.</Text>
        ) : null}
        {renderers.slice(0, 8).map((renderer, index) => (
          <View key={`${renderer.projector ?? 'renderer'}-${index}`} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{formatValue(renderer.projector, 'Renderer')}</Text>
            <Text style={styles.detailText}>Scene: {formatValue(renderer.scene)}</Text>
            <Text style={styles.detailText}>Status: {formatValue(renderer.status)}</Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="Overlay runtime"
        subtitle="Overlay sync and runtime status stay backend-driven, with mobile acting as a thin operator console."
      >
        <Text style={styles.detailText}>Brightness: {formatValue(overlayStatus?.brightness)}</Text>
        <Text style={styles.detailText}>
          Last sync event: {formatValue(overlayStatus?.sync?.event_id)}
        </Text>
        <Text style={styles.detailText}>
          Sync source: {formatValue(overlayStatus?.sync?.triggered_by)}
        </Text>
        <Text style={styles.detailText}>Server time: {formatValue(overlayStatus?.server_time)}</Text>

        <Text style={styles.sectionTitle}>Overlay configs</Text>
        {overlayConfigs.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No overlay configs found.</Text>
        ) : null}
        {overlayConfigs.slice(0, 6).map((config) => (
          <View key={String(config.id ?? describeOverlayConfig(config))} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{describeOverlayConfig(config)}</Text>
            <Text style={styles.detailText}>Background: {formatValue(config.background_type)}</Text>
            <Text style={styles.detailText}>Video ID: {formatValue(config.video_id)}</Text>
            <Text style={styles.detailText}>
              Mapping scene ID: {formatValue(config.mapping_scene_id)}
            </Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="Streaming sessions"
        subtitle="Session inventory comes from `/api/streaming/sessions` so operators can track active consumers and runtime state on mobile."
      >
        {sessions.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No active streaming sessions.</Text>
        ) : null}
        {sessions.slice(0, 8).map((session) => (
          <View key={session.session_id ?? describeSession(session)} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{describeSession(session)}</Text>
            <Text style={styles.detailText}>Type: {formatValue(session.stream_type)}</Text>
            <Text style={styles.detailText}>Device: {formatValue(session.device_name)}</Text>
            <Text style={styles.detailText}>Status: {formatValue(session.status)}</Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="Mappings and scene control"
        subtitle="Expose mapping inventory and reusable scene-control assets on mobile before attempting desktop-grade authoring flows."
      >
        <Text style={styles.sectionTitle}>Mapping scenes</Text>
        {mappingScenes.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No mapping scenes found.</Text>
        ) : null}
        {mappingScenes.slice(0, 6).map((scene) => (
          <View key={String(scene.id ?? describeMappingScene(scene))} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{describeMappingScene(scene)}</Text>
            <Text style={styles.detailText}>
              Canvas: {formatValue(scene.canvas_width)} × {formatValue(scene.canvas_height)}
            </Text>
            <Text style={styles.detailText}>Mask mode: {formatValue(scene.mask_mode)}</Text>
            <Text style={styles.detailText}>
              Masks: {Array.isArray(scene.masks) ? scene.masks.length : 0} • Groups:{' '}
              {Array.isArray(scene.groups) ? scene.groups.length : 0}
            </Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>Scene ranks</Text>
        {sceneRanks.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No scene ranks found.</Text>
        ) : null}
        {sceneRanks.slice(0, 4).map((rank) => (
          <View key={String(rank.id ?? describeSceneRank(rank))} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{describeSceneRank(rank)}</Text>
            <Text style={styles.detailText}>Orientation: {formatValue(rank.orientation)}</Text>
            <Text style={styles.detailText}>Gap px: {formatValue(rank.gap_px)}</Text>
            <Text style={styles.detailText}>
              Scenes: {Array.isArray(rank.scene_ids) ? rank.scene_ids.length : 0}
            </Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>Scene-control presets</Text>
        {sceneControlPresets.length === 0 && !loading ? (
          <Text style={styles.emptyText}>No scene-control presets found.</Text>
        ) : null}
        {sceneControlPresets.slice(0, 4).map((preset) => (
          <View key={String(preset.id ?? describeSceneControlPreset(preset))} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{describeSceneControlPreset(preset)}</Text>
            <Text style={styles.detailText}>Rank ID: {formatValue(preset.rank_id)}</Text>
            <Text style={styles.detailText}>
              Scenes: {Array.isArray(preset.scene_ids) ? preset.scene_ids.length : 0}
            </Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="Projection launchpad"
        subtitle="Projection configs remain backend-owned, while mobile provides selection, launch, and recent-session visibility."
      >
        <Text style={styles.sectionTitle}>Projection configs</Text>
        <View style={styles.selectionGrid}>
          {projectionConfigs.length === 0 && !loading ? (
            <Text style={styles.emptyText}>No projection configs found.</Text>
          ) : null}
          {projectionConfigs.map((config) => {
            const configId = config.id ?? null;
            const selected =
              configId !== null && String(configId) === String(selectedProjectionConfigId);
            return (
              <Pressable
                key={String(config.id ?? describeProjectionConfig(config))}
                accessibilityRole="button"
                onPress={() => selectProjectionConfig(configId)}
                style={[styles.selectionCard, selected && styles.selectionCardActive]}
              >
                <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                  {describeProjectionConfig(config)}
                </Text>
                <Text style={styles.detailText}>
                  Zones: {Array.isArray(config.zones) ? config.zones.length : 0}
                </Text>
                <Text style={styles.detailText}>
                  Mask: {formatValue(config.mask_data?.name ?? config.mask_data?.id)}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <View style={styles.actionsWrap}>
          <ActionButton
            label={actionLoadingKey === 'launch-projection' ? 'Launching...' : 'Launch selected projection'}
            onPress={() => void launchSelectedProjection()}
            disabled={actionsBusy}
          />
        </View>

        {recentProjectionSession ? (
          <View style={styles.itemCard}>
            <Text style={styles.itemTitle}>Recent launched session</Text>
            <Text style={styles.detailText}>Session ID: {formatValue(recentProjectionSession.id)}</Text>
            <Text style={styles.detailText}>Mask ID: {formatValue(recentProjectionSession.maskId)}</Text>
            <Text style={styles.detailText}>
              Zones: {Array.isArray(recentProjectionSession.zones) ? recentProjectionSession.zones.length : 0}
            </Text>
            <Text style={styles.detailText}>
              Created: {formatValue(recentProjectionSession.created_at)}
            </Text>
          </View>
        ) : null}
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
    fontSize: 22,
    fontWeight: '700',
  },
  metricLabel: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: '600',
  },
  metaLine: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: '600',
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
});
