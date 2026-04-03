import { useCallback, useEffect, useMemo, useState } from 'react';

import { createServiceModules } from '../../services/api.ts';
import type { AppMode } from '../../control-plane/localState.ts';
import type { JsonRecord } from '../../types/api.ts';

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

function asArray(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((item) => item && typeof item === 'object' && !Array.isArray(item)) as JsonRecord[]
    : [];
}

export interface ProjectionAnimationController {
  actionLoading: boolean;
  actionMessage: string | null;
  animationLists: JsonRecord[];
  animations: JsonRecord[];
  deleteAnimationList: (animationListId: number | string) => Promise<void>;
  editAnimationList: (animationList: JsonRecord) => void;
  error: string | null;
  listDraft: {
    id: string;
    name: string;
    animation_ids: string[];
    auto_advance_seconds: string;
    shuffle: boolean;
  };
  loading: boolean;
  refresh: () => Promise<void>;
  resetListDraft: () => void;
  saveAnimationList: () => Promise<void>;
  setAutoAdvanceSeconds: (value: string) => void;
  setListName: (value: string) => void;
  toggleAnimation: (animationId: string) => void;
  toggleShuffle: (value: boolean) => void;
}

interface UseProjectionAnimationControllerOptions {
  apiBaseUrl: string;
  appMode: AppMode;
}

const emptyDraft = {
  id: '',
  name: '',
  animation_ids: [] as string[],
  auto_advance_seconds: '12',
  shuffle: false,
};

export function useProjectionAnimationController(
  options: UseProjectionAnimationControllerOptions,
): ProjectionAnimationController {
  const services = useMemo(() => createServiceModules(options.apiBaseUrl), [options.apiBaseUrl]);
  const [animations, setAnimations] = useState<JsonRecord[]>([]);
  const [animationLists, setAnimationLists] = useState<JsonRecord[]>([]);
  const [listDraft, setListDraft] = useState(emptyDraft);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (options.appMode !== 'remote') {
      setAnimations([]);
      setAnimationLists([]);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [animationsPayload, listsPayload] = await Promise.all([
        services.projectionApi.listAnimations(),
        services.projectionApi.listAnimationLists(),
      ]);
      setAnimations(asArray(asRecord(animationsPayload)?.animations ?? animationsPayload));
      setAnimationLists(
        asArray(asRecord(listsPayload)?.animation_lists ?? listsPayload),
      );
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : 'Failed to load projection animations.',
      );
    } finally {
      setLoading(false);
    }
  }, [options.appMode, services]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const resetListDraft = useCallback(() => {
    setListDraft(emptyDraft);
  }, []);

  const saveAnimationList = useCallback(async () => {
    if (options.appMode !== 'remote') {
      setError('Projection animation management is remote-only in this slice.');
      return;
    }
    if (!listDraft.name.trim()) {
      setError('Animation list name is required.');
      return;
    }
    if (!listDraft.animation_ids.length) {
      setError('Select at least one animation.');
      return;
    }

    setActionLoading(true);
    setError(null);
    setActionMessage(null);
    try {
      const payload = {
        name: listDraft.name.trim(),
        animation_ids: listDraft.animation_ids,
        auto_advance_seconds: Number(listDraft.auto_advance_seconds || 12),
        shuffle: listDraft.shuffle,
      };
      const response = listDraft.id
        ? await services.projectionApi.updateAnimationList(listDraft.id, payload)
        : await services.projectionApi.createAnimationList(payload);
      const saved = response as JsonRecord;
      setActionMessage(`Saved animation list: ${String(saved.name ?? payload.name)}`);
      resetListDraft();
      await refresh();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Failed to save animation list.');
    } finally {
      setActionLoading(false);
    }
  }, [listDraft, options.appMode, refresh, resetListDraft, services]);

  const deleteAnimationList = useCallback(
    async (animationListId: number | string) => {
      setActionLoading(true);
      setError(null);
      setActionMessage(null);
      try {
        await services.projectionApi.deleteAnimationList(animationListId);
        setActionMessage(`Deleted animation list ${String(animationListId)}.`);
        if (String(listDraft.id) === String(animationListId)) {
          resetListDraft();
        }
        await refresh();
      } catch (deleteError) {
        setError(
          deleteError instanceof Error ? deleteError.message : 'Failed to delete animation list.',
        );
      } finally {
        setActionLoading(false);
      }
    },
    [listDraft.id, refresh, resetListDraft, services],
  );

  const editAnimationList = useCallback((animationList: JsonRecord) => {
    setListDraft({
      id: String(animationList.id ?? ''),
      name: String(animationList.name ?? ''),
      animation_ids: Array.isArray(animationList.animation_ids)
        ? animationList.animation_ids.map((item) => String(item))
        : [],
      auto_advance_seconds: String(animationList.auto_advance_seconds ?? 12),
      shuffle: Boolean(animationList.shuffle),
    });
  }, []);

  const toggleAnimation = useCallback((animationId: string) => {
    setListDraft((current) => ({
      ...current,
      animation_ids: current.animation_ids.includes(animationId)
        ? current.animation_ids.filter((item) => item !== animationId)
        : [...current.animation_ids, animationId],
    }));
  }, []);

  const setListName = useCallback((value: string) => {
    setListDraft((current) => ({ ...current, name: value }));
  }, []);

  const setAutoAdvanceSeconds = useCallback((value: string) => {
    setListDraft((current) => ({ ...current, auto_advance_seconds: value }));
  }, []);

  const toggleShuffle = useCallback((value: boolean) => {
    setListDraft((current) => ({ ...current, shuffle: value }));
  }, []);

  return {
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
  };
}
