import { Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { useProjectionAnimationController } from '../features/projection/useProjectionAnimationController';
import type { AppMode } from '../control-plane/localState';
import { colors } from '../theme';
import type { JsonRecord } from '../types/api';

interface ProjectionAnimationScreenProps {
  apiBaseUrl: string;
  appMode: AppMode;
}

function formatValue(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  return String(value);
}

function describeAnimation(animation: JsonRecord): string {
  return String(animation.name ?? animation.id ?? 'Animation');
}

function describeAnimationList(animationList: JsonRecord): string {
  return String(animationList.name ?? animationList.id ?? 'Animation list');
}

export function ProjectionAnimationScreen({
  apiBaseUrl,
  appMode,
}: ProjectionAnimationScreenProps) {
  const {
    actionLoading,
    actionMessage,
    animationLists,
    animations,
    deleteAnimationList,
    editAnimationList,
    error,
    listDraft,
    loading,
    refresh,
    resetListDraft,
    saveAnimationList,
    setAutoAdvanceSeconds,
    setListName,
    toggleAnimation,
    toggleShuffle,
  } = useProjectionAnimationController({ apiBaseUrl, appMode });

  if (appMode === 'local') {
    return (
      <Panel
        title="Projection animation"
        subtitle="Projection animation library and list management are currently remote-only because the backend owns the animation catalog."
      >
        <Text style={styles.noteText}>
          Switch to remote mode to inspect the animation library and manage reusable animation lists.
        </Text>
      </Panel>
    );
  }

  return (
    <>
      <Panel
        title="Projection animation"
        subtitle="Mobile now exposes a compact version of the backend animation library and list editor."
      >
        <View style={styles.actionsRow}>
          <ActionButton
            label={loading ? 'Refreshing...' : 'Refresh library'}
            onPress={() => void refresh()}
            disabled={loading}
          />
          <ActionButton
            label={actionLoading ? 'Saving...' : 'Save animation list'}
            onPress={() => void saveAnimationList()}
            disabled={actionLoading}
            variant="secondary"
          />
          <ActionButton
            label="Reset draft"
            onPress={resetListDraft}
            disabled={actionLoading}
            variant="secondary"
          />
        </View>
        <View style={styles.metricGrid}>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{String(animations.length)}</Text>
            <Text style={styles.metricLabel}>Animations</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricValue}>{String(animationLists.length)}</Text>
            <Text style={styles.metricLabel}>Animation lists</Text>
          </View>
        </View>
        {actionMessage ? <Text style={styles.successText}>{actionMessage}</Text> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </Panel>

      <Panel
        title="Animation list draft"
        subtitle="Create or edit reusable animation lists for later use in projection/mapping workflows."
      >
        <TextInput
          onChangeText={setListName}
          placeholder="Animation list name"
          placeholderTextColor={colors.mutedText}
          style={styles.input}
          value={listDraft.name}
        />
        <TextInput
          keyboardType="numeric"
          onChangeText={setAutoAdvanceSeconds}
          placeholder="Auto advance seconds"
          placeholderTextColor={colors.mutedText}
          style={styles.input}
          value={listDraft.auto_advance_seconds}
        />
        <View style={styles.switchRow}>
          <Text style={styles.fieldLabel}>Shuffle</Text>
          <Switch value={listDraft.shuffle} onValueChange={toggleShuffle} />
        </View>
        <Text style={styles.detailText}>
          Selected animations: {listDraft.animation_ids.length}
        </Text>
      </Panel>

      <Panel
        title="Animation library"
        subtitle="Select animations to include in the current list draft."
      >
        {animations.length === 0 ? (
          <Text style={styles.emptyText}>No projection animations returned yet.</Text>
        ) : null}
        {animations.map((animation) => {
          const animationId = String(animation.id ?? '');
          const selected = listDraft.animation_ids.includes(animationId);
          return (
            <Pressable
              key={animationId || describeAnimation(animation)}
              accessibilityRole="button"
              onPress={() => toggleAnimation(animationId)}
              style={[styles.selectionCard, selected && styles.selectionCardActive]}
            >
              <Text style={[styles.selectionTitle, selected && styles.selectionTitleActive]}>
                {describeAnimation(animation)}
              </Text>
              <Text style={styles.detailText}>{formatValue(animation.description)}</Text>
              <Text style={styles.detailText}>
                Inputs:{' '}
                {Array.isArray(animation.dataInputs)
                  ? animation.dataInputs.join(' • ')
                  : formatValue(animation.dataInputs, 'none')}
              </Text>
            </Pressable>
          );
        })}
      </Panel>

      <Panel
        title="Saved animation lists"
        subtitle="Edit or remove existing backend animation lists from the mobile app."
      >
        {animationLists.length === 0 ? (
          <Text style={styles.emptyText}>No animation lists saved yet.</Text>
        ) : null}
        {animationLists.map((animationList) => (
          <View key={String(animationList.id ?? describeAnimationList(animationList))} style={styles.itemCard}>
            <Text style={styles.itemTitle}>{describeAnimationList(animationList)}</Text>
            <Text style={styles.detailText}>
              Auto advance: {formatValue(animationList.auto_advance_seconds)}
            </Text>
            <Text style={styles.detailText}>
              Animations:{' '}
              {Array.isArray(animationList.animation_ids)
                ? animationList.animation_ids.length
                : 0}
            </Text>
            <View style={styles.actionsRow}>
              <ActionButton
                label="Edit"
                onPress={() => editAnimationList(animationList)}
                disabled={actionLoading}
                variant="secondary"
              />
              {animationList.id !== null && animationList.id !== undefined ? (
                <ActionButton
                  label="Delete"
                  onPress={() => void deleteAnimationList(animationList.id as string | number)}
                  disabled={actionLoading}
                  variant="secondary"
                />
              ) : null}
            </View>
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
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  fieldLabel: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '600',
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
});
