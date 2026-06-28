import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';

import PageHeader from '../components/PageHeader';
import StatusPanel from '../components/StatusPanel';
import {
  api,
  discoveryV2Api,
  mappingsApi,
  mediaLibraryApi,
  photoApi,
  photoListApi,
  projectionApi,
  rendererApi,
  videoApi,
} from '../services/api';

const SCENE_CONTROL_PRESET_KEY = 'nanoDlnaSceneControlPresetId';

function normalizeNumericIdList(values) {
  return (Array.isArray(values) ? values : [])
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function createRowEdit(group = {}) {
  return {
    layout_scope: group.layout_scope || 'scene',
    media_binding_type: group.media_binding_type || 'video',
    animation_id: group.animation_id || '',
    animation_list_id: group.animation_list_id || '',
    video_id: group.video_id || '',
    photo_id: group.photo_id || '',
    media_list_id: group.media_list_id || '',
    photo_list_id: group.photo_list_id || '',
    media_channel_id: group.media_channel_id || '',
    media_directory_id: group.media_directory_id || '',
    media_directory_ids: normalizeNumericIdList(group.media_directory_ids || []),
    direct_url: group.direct_url || '',
    auto_advance: group.auto_advance !== false,
    shuffle: Boolean(group.shuffle),
    visible: group.visible !== false,
    z_index: group.z_index || 0,
    color_a: group.color_a || '#b56a2d',
    color_b: group.color_b || '#6a7f58',
    transform_scale: group.transform?.scale || 1,
  };
}

function normalizeGroupName(name) {
  return String(name || '').trim().toLowerCase();
}

function averageCoverage(groups) {
  if (!groups?.length) {
    return 0;
  }
  return groups.reduce((sum, group) => sum + (group?._coverage || 0), 0) / groups.length;
}

function getMaskFileUrl(sceneId, maskId) {
  return `/api/mappings/scenes/${sceneId}/masks/${maskId}/file`;
}

async function loadMaskCoverage(url) {
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth || image.width;
      canvas.height = image.naturalHeight || image.height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        resolve(0);
        return;
      }
      ctx.drawImage(image, 0, 0);
      const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
      let covered = 0;
      for (let index = 0; index < data.length; index += 4) {
        const alpha = data[index + 3];
        const luminance = data[index] + data[index + 1] + data[index + 2];
        if (alpha > 0 && luminance > 0) {
          covered += 1;
        }
      }
      resolve(covered);
    };
    image.onerror = () => resolve(0);
    image.src = url;
  });
}

async function hydrateSceneWithCoverage(scene) {
  const masks = scene.masks || [];
  const coverageEntries = await Promise.all(
    masks.map(async (mask) => [mask.id, await loadMaskCoverage(getMaskFileUrl(scene.id, mask.id))]),
  );
  const coverageByMaskId = Object.fromEntries(coverageEntries);
  const sortedGroups = (scene.groups || [])
    .map((group) => ({
      ...group,
      _coverage: (group.mask_ids || []).reduce((sum, maskId) => sum + (coverageByMaskId[maskId] || 0), 0),
    }))
    .sort((a, b) => (b._coverage || 0) - (a._coverage || 0));
  const groupsById = Object.fromEntries(sortedGroups.map((group) => [group.id, group]));

  return {
    ...scene,
    _coverageByMaskId: coverageByMaskId,
    _sortedGroups: sortedGroups,
    _groupsById: groupsById,
  };
}

function createSmartGroupAssignments(hydratedScenes) {
  if (!hydratedScenes.length) {
    return {};
  }

  const canonicalScene = hydratedScenes[0];
  const canonicalGroups = canonicalScene._sortedGroups || [];
  const rows = canonicalGroups.map((group) => ({
    referenceName: normalizeGroupName(group.name),
    referenceCoverage: group._coverage || 0,
    groupsBySceneId: {
      [canonicalScene.id]: [group.id],
    },
  }));

  hydratedScenes.slice(1).forEach((scene) => {
    const remaining = [...(scene._sortedGroups || [])];

    rows.forEach((row) => {
      const exactNameIndex = remaining.findIndex((group) => normalizeGroupName(group.name) === row.referenceName);
      if (exactNameIndex >= 0) {
        const [match] = remaining.splice(exactNameIndex, 1);
        row.groupsBySceneId[scene.id] = [match.id];
      } else {
        row.groupsBySceneId[scene.id] = [];
      }
    });

    remaining.forEach((group) => {
      let bestRowIndex = -1;
      let bestScore = Number.POSITIVE_INFINITY;
      rows.forEach((row, rowIndex) => {
        if ((row.groupsBySceneId[scene.id] || []).length) {
          return;
        }
        const referenceCoverage = row.referenceCoverage || 1;
        const score = Math.abs((group._coverage || 0) - referenceCoverage) / referenceCoverage;
        if (score < bestScore) {
          bestScore = score;
          bestRowIndex = rowIndex;
        }
      });
      if (bestRowIndex >= 0) {
        rows[bestRowIndex].groupsBySceneId[scene.id] = [group.id];
      } else {
        rows.push({
          referenceName: normalizeGroupName(group.name),
          referenceCoverage: group._coverage || 0,
          groupsBySceneId: {
            [scene.id]: [group.id],
          },
        });
      }
    });
  });

  return Object.fromEntries(hydratedScenes.map((scene) => [
    scene.id,
    rows.map((row) => row.groupsBySceneId[scene.id] || []),
  ]));
}

function normalizeRendererProjectors(response) {
  const data = response?.data;
  if (Array.isArray(data?.data?.projectors)) {
    return data.data.projectors;
  }
  if (Array.isArray(data?.projectors)) {
    return data.projectors;
  }
  if (Array.isArray(data)) {
    return data;
  }
  return [];
}

function normalizeDiscoveryDevices(response) {
  const data = response?.data;
  if (Array.isArray(data?.data?.devices)) {
    return data.data.devices;
  }
  if (Array.isArray(data?.devices)) {
    return data.devices;
  }
  if (Array.isArray(data)) {
    return data;
  }
  return [];
}

function projectionTargetKey(target) {
  return `${target.type}:${target.id}`;
}

function createProjectionTargets(projectors, devices) {
  const hdmiTargets = projectors
    .filter((projector) => String(projector.sender || projector.sender_type || '').toLowerCase() === 'hdmi')
    .map((projector) => ({
      type: 'hdmi',
      id: String(projector.id),
      name: projector.name || projector.id,
      detail: projector.target_name ? `HDMI -> ${projector.target_name}` : 'HDMI',
    }));
  const dlnaTargets = devices.map((device) => ({
    type: 'dlna',
    id: String(device.id || device.device_id || device.name),
    name: device.friendly_name || device.name || device.id || device.device_id,
    detail: device.hostname || device.location || 'DLNA',
  }));
  return [...hdmiTargets, ...dlnaTargets].map((target) => ({
    ...target,
    key: projectionTargetKey(target),
  }));
}

function SceneControl() {
  const [scenes, setScenes] = useState([]);
  const [sceneRanks, setSceneRanks] = useState([]);
  const [sceneControlPresets, setSceneControlPresets] = useState([]);
  const [selectedSceneIds, setSelectedSceneIds] = useState([]);
  const [selectedScenes, setSelectedScenes] = useState([]);
  const [videos, setVideos] = useState([]);
  const [photos, setPhotos] = useState([]);
  const [mediaLists, setMediaLists] = useState([]);
  const [photoLists, setPhotoLists] = useState([]);
  const [mediaChannels, setMediaChannels] = useState([]);
  const [mediaDirectories, setMediaDirectories] = useState([]);
  const [projectionAnimations, setProjectionAnimations] = useState([]);
  const [animationLists, setAnimationLists] = useState([]);
  const [groupAssignments, setGroupAssignments] = useState({});
  const [rowEdits, setRowEdits] = useState({});
  const [dragState, setDragState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rankSaving, setRankSaving] = useState(false);
  const [presetSaving, setPresetSaving] = useState(false);
  const [presetLoading, setPresetLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [rankName, setRankName] = useState('');
  const [rankGapPx, setRankGapPx] = useState(0);
  const [presetName, setPresetName] = useState('');
  const [selectedPresetId, setSelectedPresetId] = useState('');
  const [pendingPresetPayload, setPendingPresetPayload] = useState(null);
  const [initialPresetHydrated, setInitialPresetHydrated] = useState(false);
  const [projectionTargets, setProjectionTargets] = useState([]);
  const [selectedProjectionTargetKey, setSelectedProjectionTargetKey] = useState('');
  const [selectedProjectionSceneId, setSelectedProjectionSceneId] = useState('');
  const [projectionStatus, setProjectionStatus] = useState(null);
  const [projectionLoading, setProjectionLoading] = useState(false);
  const [brightness, setBrightness] = useState(100);
  const [brightnessLoading, setBrightnessLoading] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([
      mappingsApi.listScenes(),
      mappingsApi.listRanks(),
      mappingsApi.listSceneControlPresets(),
      videoApi.getVideos(),
      photoApi.getPhotos(),
      mediaLibraryApi.listDirectories(),
      mediaLibraryApi.listMediaLists(),
      photoListApi.listPhotoLists(),
      mediaLibraryApi.listMediaChannels(),
      projectionApi.listAnimations(),
      projectionApi.listAnimationLists(),
    ]).then(([sceneRes, rankRes, presetRes, videoRes, photoRes, mediaDirectoryRes, mediaListRes, photoListRes, mediaChannelRes, animationRes, animationListRes]) => {
      if (!active) {
        return;
      }
      const nextScenes = sceneRes.data || [];
      setSceneRanks(rankRes.data || []);
      const nextPresets = presetRes.data || [];
      setSceneControlPresets(nextPresets);
      setScenes(nextScenes);
      setSelectedSceneIds(nextScenes.slice(0, 2).map((scene) => scene.id));
      const storedPresetId = window.localStorage.getItem(SCENE_CONTROL_PRESET_KEY) || '';
      if (storedPresetId && nextPresets.some((preset) => String(preset.id) === storedPresetId)) {
        setSelectedPresetId(storedPresetId);
      }
      setVideos(videoRes.data.videos || []);
      setPhotos(photoRes.data.photos || []);
      setMediaDirectories(mediaDirectoryRes.data || []);
      setMediaLists(mediaListRes.data || []);
      setPhotoLists(photoListRes.data || []);
      setMediaChannels(mediaChannelRes.data || []);
      setProjectionAnimations(animationRes.data?.animations || []);
      setAnimationLists(animationListRes.data?.animation_lists || []);
      setLoading(false);
    }).catch((err) => {
      console.error(err);
      if (!active) {
        return;
      }
      setError('Failed to load scene control workspace.');
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      rendererApi.listProjectors(),
      discoveryV2Api.getDevices({ casting_method: 'dlna' }),
      api.get('/overlay/brightness'),
    ]).then(([projectorResult, discoveryResult, brightnessResult]) => {
      if (!active) {
        return;
      }
      const nextTargets = createProjectionTargets(
        projectorResult.status === 'fulfilled' ? normalizeRendererProjectors(projectorResult.value) : [],
        discoveryResult.status === 'fulfilled' ? normalizeDiscoveryDevices(discoveryResult.value) : [],
      );
      setProjectionTargets(nextTargets);
      setSelectedProjectionTargetKey((current) => (
        current && nextTargets.some((target) => target.key === current)
          ? current
          : nextTargets[0]?.key || ''
      ));
      if (brightnessResult.status === 'fulfilled' && typeof brightnessResult.value?.data?.brightness === 'number') {
        setBrightness(brightnessResult.value.data.brightness);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    if (!selectedSceneIds.length) {
      setSelectedScenes([]);
      setRowEdits({});
      return undefined;
    }
    Promise.all(selectedSceneIds.map((sceneId) => mappingsApi.getScene(sceneId).then((response) => hydrateSceneWithCoverage(response.data))))
      .then((hydratedScenes) => {
        if (!active) {
          return;
        }
        setSelectedScenes(hydratedScenes);
        const shouldApplyPreset = pendingPresetPayload
          && Array.isArray(pendingPresetPayload.scene_ids)
          && pendingPresetPayload.scene_ids.length === selectedSceneIds.length
          && pendingPresetPayload.scene_ids.every((sceneId, index) => Number(sceneId) === Number(selectedSceneIds[index]));
        const nextAssignments = shouldApplyPreset
          ? pendingPresetPayload.group_assignments || {}
          : createSmartGroupAssignments(hydratedScenes);
        setGroupAssignments(nextAssignments);
        setRowEdits((current) => {
          const next = {};
          const rowCount = Math.max(0, ...Object.values(nextAssignments).map((assignments) => assignments?.length || 0));
          for (let index = 0; index < rowCount; index += 1) {
            const presetEdit = shouldApplyPreset ? pendingPresetPayload.row_edits?.[String(index)] : null;
            const seedGroup = hydratedScenes
              .flatMap((scene) => (nextAssignments[scene.id]?.[index] || []).map((groupId) => scene._groupsById?.[groupId]))
              .find(Boolean);
            next[index] = presetEdit ? createRowEdit(presetEdit) : (current[index] || createRowEdit(seedGroup));
          }
          return next;
        });
        if (shouldApplyPreset) {
          setPendingPresetPayload(null);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError('Failed to load selected scene details.');
        }
      });
    return () => {
      active = false;
    };
  }, [pendingPresetPayload, selectedSceneIds]);

  useEffect(() => {
    setSelectedProjectionSceneId((current) => {
      if (current && selectedSceneIds.some((sceneId) => String(sceneId) === String(current))) {
        return current;
      }
      return selectedSceneIds[0] ? String(selectedSceneIds[0]) : '';
    });
  }, [selectedSceneIds]);

  const selectedRank = useMemo(() => {
    if (!selectedSceneIds.length) {
      return null;
    }
    return sceneRanks.find((rank) => {
      const rankSceneIds = Array.isArray(rank.scene_ids) ? rank.scene_ids.map(Number) : [];
      return (
        rankSceneIds.length === selectedSceneIds.length
        && rankSceneIds.every((sceneId, index) => sceneId === Number(selectedSceneIds[index]))
      );
    }) || null;
  }, [sceneRanks, selectedSceneIds]);

  useEffect(() => {
    if (selectedRank) {
      setRankName(selectedRank.name || '');
      setRankGapPx(selectedRank.gap_px || 0);
    } else if (selectedSceneIds.length) {
      setRankName(`Rank ${selectedSceneIds.join('-')}`);
      setRankGapPx(0);
    } else {
      setRankName('');
      setRankGapPx(0);
    }
  }, [selectedRank, selectedSceneIds]);

  const selectedPreset = useMemo(() => (
    sceneControlPresets.find((preset) => String(preset.id) === String(selectedPresetId)) || null
  ), [sceneControlPresets, selectedPresetId]);

  const selectedProjectionTarget = useMemo(() => (
    projectionTargets.find((target) => target.key === selectedProjectionTargetKey) || null
  ), [projectionTargets, selectedProjectionTargetKey]);

  const applyPreset = useCallback(async (presetId) => {
    if (!presetId) {
      setSelectedPresetId('');
      setPresetName('');
      window.localStorage.removeItem(SCENE_CONTROL_PRESET_KEY);
      return;
    }
    try {
      setPresetLoading(true);
      setError('');
      setMessage('');
      const response = await mappingsApi.getSceneControlPreset(presetId);
      const preset = response.data;
      setSelectedPresetId(String(preset.id));
      setPresetName(preset.name || '');
      setPendingPresetPayload({
        scene_ids: (preset.scene_ids || []).map(Number),
        group_assignments: preset.group_assignments || {},
        row_edits: preset.row_edits || {},
      });
      setSelectedSceneIds((preset.scene_ids || []).map(Number));
      const linkedRank = preset.rank_id
        ? sceneRanks.find((rank) => Number(rank.id) === Number(preset.rank_id))
        : null;
      if (linkedRank) {
        setRankName(linkedRank.name || '');
        setRankGapPx(linkedRank.gap_px || 0);
      }
      setMessage(`Loaded preset "${preset.name}".`);
    } catch (err) {
      console.error(err);
      setError('Failed to load scene control preset.');
    } finally {
      setPresetLoading(false);
    }
  }, [sceneRanks]);

  useEffect(() => {
    if (selectedPreset) {
      setPresetName(selectedPreset.name || '');
      window.localStorage.setItem(SCENE_CONTROL_PRESET_KEY, String(selectedPreset.id));
    } else {
      if (selectedPresetId) {
        window.localStorage.setItem(SCENE_CONTROL_PRESET_KEY, String(selectedPresetId));
      } else {
        window.localStorage.removeItem(SCENE_CONTROL_PRESET_KEY);
      }
      if (!presetName && selectedSceneIds.length) {
        setPresetName(`Preset ${selectedSceneIds.join('-')}`);
      }
    }
  }, [selectedPreset, selectedPresetId, presetName, selectedSceneIds]);

  useEffect(() => {
    if (initialPresetHydrated || !selectedPresetId || !sceneControlPresets.length) {
      return;
    }
    setInitialPresetHydrated(true);
    applyPreset(selectedPresetId);
  }, [applyPreset, initialPresetHydrated, selectedPresetId, sceneControlPresets.length]);

  const alignedRows = useMemo(() => {
    const rowCount = Math.max(0, ...Object.values(groupAssignments).map((assignments) => assignments?.length || 0));
    return Array.from({ length: rowCount }, (_, index) => ({
      index,
      groups: selectedScenes.map((scene) => ({
        sceneId: scene.id,
        sceneName: scene.name,
        groups: (groupAssignments[scene.id]?.[index] || []).map((groupId) => scene._groupsById?.[groupId]).filter(Boolean),
      })),
    }));
  }, [groupAssignments, selectedScenes]);

  const updateRowEdit = (rowIndex, patch) => {
    setRowEdits((current) => ({
      ...current,
      [rowIndex]: {
        ...(current[rowIndex] || createRowEdit()),
        ...patch,
      },
    }));
  };

  const moveSelectedScene = (sceneId, direction) => {
    setSelectedSceneIds((current) => {
      const index = current.indexOf(sceneId);
      const targetIndex = index + direction;
      if (index < 0 || targetIndex < 0 || targetIndex >= current.length) {
        return current;
      }
      const next = [...current];
      [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
      return next;
    });
  };

  const buildPresetPayload = (rankId = selectedRank?.id || null) => ({
    name: presetName || `Preset ${selectedSceneIds.join('-')}`,
    scene_ids: selectedSceneIds.map(Number),
    group_assignments: Object.fromEntries(
      Object.entries(groupAssignments || {}).map(([sceneId, buckets]) => [String(sceneId), buckets || []]),
    ),
    row_edits: Object.fromEntries(
      Object.entries(rowEdits || {}).map(([rowIndex, rowEdit]) => [String(rowIndex), rowEdit || {}]),
    ),
    rank_id: rankId,
    preset_metadata: selectedPreset?.preset_metadata || {},
  });

  const storeSavedPreset = (savedPreset) => {
    setSceneControlPresets((current) => (
      selectedPreset
        ? current.map((preset) => (preset.id === savedPreset.id ? savedPreset : preset))
        : [savedPreset, ...current]
    ));
    setSelectedPresetId(String(savedPreset.id));
    setPresetName(savedPreset.name || '');
  };

  const persistRankDefinition = async () => {
    const payload = {
      name: rankName || `Rank ${selectedSceneIds.join('-')}`,
      orientation: 'horizontal',
      scene_ids: selectedSceneIds.map(Number),
      gap_px: Number(rankGapPx) || 0,
      rank_metadata: {},
    };
    const response = selectedRank
      ? await mappingsApi.updateRank(selectedRank.id, payload)
      : await mappingsApi.createRank(payload);
    const savedRank = response.data;
    setSceneRanks((current) => (
      selectedRank
        ? current.map((rank) => (rank.id === savedRank.id ? savedRank : rank))
        : [savedRank, ...current]
    ));
    return savedRank;
  };

  const persistRank = async () => {
    try {
      setRankSaving(true);
      setError('');
      setMessage('');
      const savedRank = await persistRankDefinition();
      setMessage(`Saved rank "${savedRank.name}".`);
    } catch (err) {
      console.error(err);
      setError('Failed to save scene rank.');
    } finally {
      setRankSaving(false);
    }
  };

  const persistPreset = async () => {
    try {
      setPresetSaving(true);
      setError('');
      setMessage('');
      const payload = buildPresetPayload();
      const response = selectedPreset
        ? await mappingsApi.updateSceneControlPreset(selectedPreset.id, payload)
        : await mappingsApi.createSceneControlPreset(payload);
      const savedPreset = response.data;
      storeSavedPreset(savedPreset);
      setMessage(`Saved preset "${savedPreset.name}".`);
    } catch (err) {
      console.error(err);
      setError('Failed to save scene control preset.');
    } finally {
      setPresetSaving(false);
    }
  };

  const deletePreset = async () => {
    if (!selectedPreset) {
      return;
    }
    try {
      setPresetSaving(true);
      setError('');
      setMessage('');
      await mappingsApi.deleteSceneControlPreset(selectedPreset.id);
      setSceneControlPresets((current) => current.filter((preset) => preset.id !== selectedPreset.id));
      setSelectedPresetId('');
      setPresetName('');
      window.localStorage.removeItem(SCENE_CONTROL_PRESET_KEY);
      setMessage(`Deleted preset "${selectedPreset.name}".`);
    } catch (err) {
      console.error(err);
      setError('Failed to delete scene control preset.');
    } finally {
      setPresetSaving(false);
    }
  };

  const persistAll = async () => {
    try {
      setSaving(true);
      setError('');
      setMessage('');
      const hasRankScopedRows = Object.values(rowEdits || {}).some((edit) => (edit?.layout_scope || 'scene') === 'rank');
      const savedRank = (hasRankScopedRows || selectedRank) && selectedSceneIds.length >= 2
        ? await persistRankDefinition()
        : null;
      await Promise.all(selectedScenes.map(async (scene) => {
        const groupsById = Object.fromEntries((scene.groups || []).map((group) => [group.id, group]));
        alignedRows.forEach((row) => {
          const targetIds = groupAssignments[scene.id]?.[row.index] || [];
          if (!targetIds.length) {
            return;
          }
          const edit = rowEdits[row.index];
          if (!edit) {
            return;
          }
          targetIds.forEach((targetId) => {
            const target = groupsById[targetId];
            if (!target) {
              return;
            }
            groupsById[target.id] = {
              ...groupsById[target.id],
              layout_scope: edit.layout_scope || 'scene',
              media_binding_type: edit.media_binding_type,
              animation_id: edit.animation_id || null,
              animation_list_id: edit.animation_list_id || null,
              video_id: edit.video_id ? Number(edit.video_id) : null,
              photo_id: edit.photo_id ? Number(edit.photo_id) : null,
              media_list_id: edit.media_list_id ? Number(edit.media_list_id) : null,
              photo_list_id: edit.photo_list_id ? Number(edit.photo_list_id) : null,
              media_channel_id: edit.media_channel_id ? Number(edit.media_channel_id) : null,
              media_directory_id: normalizeNumericIdList(edit.media_directory_ids || [edit.media_directory_id])[0] || null,
              media_directory_ids: normalizeNumericIdList(edit.media_directory_ids || []),
              direct_url: edit.direct_url || '',
              auto_advance: edit.auto_advance !== false,
              shuffle: Boolean(edit.shuffle),
              visible: edit.visible !== false,
              z_index: Number(edit.z_index) || 0,
              color_a: edit.color_a,
              color_b: edit.color_b,
              transform: {
                ...(groupsById[target.id].transform || {}),
                scale: Number(edit.transform_scale) || 1,
              },
            };
          });
        });

        await mappingsApi.updateScene(scene.id, {
          id: scene.id,
          name: scene.name,
          canvas_width: scene.canvas_width,
          canvas_height: scene.canvas_height,
          mask_mode: scene.mask_mode,
          masks: scene.masks || [],
          groups: (scene.groups || []).map((group) => groupsById[group.id] || group),
          render_settings: scene.render_settings || { background: '#000000' },
        });
      }));
      const refreshedScenes = await Promise.all(
        selectedSceneIds.map((sceneId) => mappingsApi.getScene(sceneId).then((response) => hydrateSceneWithCoverage(response.data))),
      );
      let syncedPreset = null;
      if (selectedPreset) {
        const presetResponse = await mappingsApi.updateSceneControlPreset(
          selectedPreset.id,
          buildPresetPayload(savedRank?.id || selectedRank?.id || null),
        );
        syncedPreset = presetResponse.data;
        storeSavedPreset(syncedPreset);
      }
      setSelectedScenes(refreshedScenes);
      setGroupAssignments((current) => current && Object.keys(current).length ? current : createSmartGroupAssignments(refreshedScenes));
      setMessage(
        syncedPreset
          ? `Saved ${selectedScenes.length} scenes, synced rank${savedRank ? ` "${savedRank.name}"` : ''}, and synced preset "${syncedPreset.name}".`
          : `Saved ${selectedScenes.length} scenes${savedRank ? ` and synced rank "${savedRank.name}"` : ''}.`,
      );
    } catch (err) {
      console.error(err);
      setError('Failed to save aligned scene groups.');
    } finally {
      setSaving(false);
    }
  };

  const moveGroupToRank = (sceneId, groupId, targetIndex) => {
    setGroupAssignments((current) => {
      const sceneAssignments = (current[sceneId] || []).map((bucket) => [...bucket]);
      const sourceIndex = sceneAssignments.findIndex((bucket) => bucket.includes(groupId));
      if (sourceIndex < 0) {
        return current;
      }
      sceneAssignments[sourceIndex] = sceneAssignments[sourceIndex].filter((id) => id !== groupId);
      while (sceneAssignments.length <= targetIndex) {
        sceneAssignments.push([]);
      }
      sceneAssignments[targetIndex] = [...sceneAssignments[targetIndex], groupId];
      return {
        ...current,
        [sceneId]: sceneAssignments,
      };
    });
  };

  const bubbleRanksUpFrom = (startIndex) => {
    setGroupAssignments((current) => Object.fromEntries(
      Object.entries(current).map(([sceneId, assignments]) => {
        const nextAssignments = (assignments || []).map((bucket) => [...bucket]);
        if (!nextAssignments[startIndex]) {
          return [sceneId, nextAssignments];
        }

        const bubbledIds = nextAssignments
          .slice(startIndex)
          .flatMap((bucket) => bucket || []);

        nextAssignments[startIndex] = Array.from(new Set(bubbledIds));
        for (let index = startIndex + 1; index < nextAssignments.length; index += 1) {
          nextAssignments[index] = [];
        }

        return [sceneId, nextAssignments];
      }),
    ));
    setMessage(`Merged rank ${startIndex + 1} with all ranks below it.`);
  };

  const autoAssignSimilar = () => {
    const nextAssignments = createSmartGroupAssignments(selectedScenes);
    setGroupAssignments(nextAssignments);
    setMessage('Auto-assigned groups by name first, then by size similarity.');
  };

  const launchProjection = async () => {
    if (!selectedProjectionSceneId || !selectedProjectionTarget) {
      setError('Select a scene and projection target first.');
      return;
    }
    try {
      setProjectionLoading(true);
      setError('');
      setMessage('');
      const response = await mappingsApi.projectScene(Number(selectedProjectionSceneId), {
        target_type: selectedProjectionTarget.type,
        target_id: selectedProjectionTarget.id,
        overlay_base_url: `${window.location.protocol}//${window.location.host}`,
        controls_hidden: true,
      });
      setProjectionStatus(response.data);
      setMessage(`Launched scene on ${selectedProjectionTarget.name}.`);
    } catch (err) {
      console.error(err);
      setError('Failed to launch scene projection.');
    } finally {
      setProjectionLoading(false);
    }
  };

  const stopProjection = async () => {
    const activeTransport = projectionStatus?.transport || selectedProjectionTarget?.type;
    const activeTargetId = activeTransport === 'dlna'
      ? projectionStatus?.cast_session?.session_id
      : selectedProjectionTarget?.id;
    if (!activeTransport || !activeTargetId) {
      setError('No active projection target to stop.');
      return;
    }
    try {
      setProjectionLoading(true);
      setError('');
      setMessage('');
      await mappingsApi.stopSceneProjection({
        target_type: activeTransport,
        target_id: activeTargetId,
      });
      setProjectionStatus(null);
      setMessage('Stopped scene projection.');
    } catch (err) {
      console.error(err);
      setError('Failed to stop scene projection.');
    } finally {
      setProjectionLoading(false);
    }
  };

  const updateBrightness = async (value) => {
    const nextBrightness = Math.max(0, Math.min(100, Number(value) || 0));
    setBrightness(nextBrightness);
    try {
      setBrightnessLoading(true);
      setError('');
      await api.post(`/overlay/brightness?brightness=${nextBrightness}`);
    } catch (err) {
      console.error(err);
      setError('Failed to update projection brightness.');
    } finally {
      setBrightnessLoading(false);
    }
  };

  if (loading) {
    return (
      <StatusPanel
        title="Loading Scene Control"
        message="Loading scenes, saved ranks, media bindings, and projection presets."
        loading
      />
    );
  }

  return (
    <Stack spacing={3}>
      <PageHeader
        title="Scene Control"
        subtitle="Batch-edit existing groups across multiple scenes, align ranks, and bind media without leaving the operations view."
        meta={(
          <>
            <Chip label={`${selectedSceneIds.length} selected`} color={selectedSceneIds.length ? 'primary' : 'default'} />
            <Chip label={`${scenes.length} scenes`} variant="outlined" />
            <Chip label={`${sceneRanks.length} ranks`} variant="outlined" />
          </>
        )}
      />

      {error ? <Alert severity="error">{error}</Alert> : null}
      {message ? <Alert severity="success">{message}</Alert> : null}

      <Grid container spacing={2}>
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Scenes</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              Select the mapping scenes you want to align and batch-edit.
            </Typography>
            <Stack spacing={1.25} sx={{ mb: 2 }}>
              <Typography variant="subtitle2">Project Scene</Typography>
              <FormControl fullWidth size="small">
                <InputLabel>Projection Scene</InputLabel>
                <Select
                  value={selectedProjectionSceneId}
                  label="Projection Scene"
                  onChange={(event) => setSelectedProjectionSceneId(event.target.value)}
                >
                  <MenuItem value="">None</MenuItem>
                  {selectedSceneIds.map((sceneId) => {
                    const scene = scenes.find((item) => item.id === sceneId);
                    if (!scene) {
                      return null;
                    }
                    return (
                      <MenuItem key={scene.id} value={String(scene.id)}>
                        {scene.name}
                      </MenuItem>
                    );
                  })}
                </Select>
              </FormControl>
              <FormControl fullWidth size="small">
                <InputLabel>Target</InputLabel>
                <Select
                  value={selectedProjectionTargetKey}
                  label="Target"
                  onChange={(event) => setSelectedProjectionTargetKey(event.target.value)}
                >
                  <MenuItem value="">No target</MenuItem>
                  {projectionTargets.map((target) => (
                    <MenuItem key={target.key} value={target.key}>
                      {target.name} ({target.type.toUpperCase()}) - {target.detail}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Stack direction="row" spacing={1}>
                <Button
                  variant="contained"
                  onClick={launchProjection}
                  disabled={projectionLoading || !selectedProjectionSceneId || !selectedProjectionTarget}
                >
                  {projectionLoading ? 'Working...' : 'Launch'}
                </Button>
                <Button
                  variant="outlined"
                  color="error"
                  onClick={stopProjection}
                  disabled={projectionLoading || (!projectionStatus && selectedProjectionTarget?.type === 'dlna')}
                >
                  Stop
                </Button>
              </Stack>
              {projectionStatus ? (
                <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap' }}>
                  <Chip label={projectionStatus.transport?.toUpperCase()} size="small" />
                  <Chip label={projectionStatus.status} size="small" variant="outlined" />
                </Stack>
              ) : null}
              <TextField
                label="Brightness"
                size="small"
                type="number"
                value={brightness}
                inputProps={{ min: 0, max: 100 }}
                onChange={(event) => setBrightness(event.target.value)}
                onBlur={(event) => updateBrightness(event.target.value)}
                disabled={brightnessLoading}
              />
              <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap' }}>
                {[0, 25, 75, 100].map((value) => (
                  <Button
                    key={value}
                    size="small"
                    variant={Number(brightness) === value ? 'contained' : 'outlined'}
                    onClick={() => updateBrightness(value)}
                    disabled={brightnessLoading}
                  >
                    {value}%
                  </Button>
                ))}
              </Stack>
              <Typography variant="subtitle2">Workspace Preset</Typography>
              <FormControl fullWidth size="small">
                <InputLabel>Saved Preset</InputLabel>
                <Select
                  value={selectedPresetId}
                  label="Saved Preset"
                  onChange={(event) => {
                    const nextPresetId = event.target.value;
                    if (!nextPresetId) {
                      setSelectedPresetId('');
                      setPresetName('');
                      window.localStorage.removeItem(SCENE_CONTROL_PRESET_KEY);
                      return;
                    }
                    applyPreset(nextPresetId);
                  }}
                >
                  <MenuItem value="">None</MenuItem>
                  {sceneControlPresets.map((preset) => (
                    <MenuItem key={preset.id} value={String(preset.id)}>
                      {preset.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                label="Preset Name"
                size="small"
                value={presetName}
                onChange={(event) => setPresetName(event.target.value)}
              />
              <Stack direction="row" spacing={1}>
                <Button variant="outlined" onClick={persistPreset} disabled={presetSaving || !selectedSceneIds.length}>
                  {selectedPreset ? 'Update Preset' : 'Save Preset'}
                </Button>
                <Button
                  variant="text"
                  onClick={() => {
                    setSelectedPresetId('');
                    setPresetName(`Preset ${selectedSceneIds.join('-')}`);
                    window.localStorage.removeItem(SCENE_CONTROL_PRESET_KEY);
                  }}
                >
                  New
                </Button>
                <Button variant="text" color="error" onClick={deletePreset} disabled={presetSaving || !selectedPreset}>
                  Delete
                </Button>
              </Stack>
              <Typography variant="subtitle2">Horizontal Rank</Typography>
              <TextField
                label="Rank Name"
                size="small"
                value={rankName}
                onChange={(event) => setRankName(event.target.value)}
              />
              <TextField
                label="Gap (px)"
                size="small"
                type="number"
                value={rankGapPx}
                onChange={(event) => setRankGapPx(event.target.value)}
              />
              <Stack spacing={0.75}>
                {selectedSceneIds.map((sceneId, index) => {
                  const scene = scenes.find((item) => item.id === sceneId);
                  if (!scene) {
                    return null;
                  }
                  return (
                    <Stack key={sceneId} direction="row" spacing={1} alignItems="center">
                      <Chip label={`${index + 1}`} size="small" />
                      <Typography variant="body2" sx={{ flex: 1 }}>{scene.name}</Typography>
                      <Button size="small" onClick={() => moveSelectedScene(sceneId, -1)} disabled={index === 0}>Left</Button>
                      <Button size="small" onClick={() => moveSelectedScene(sceneId, 1)} disabled={index === selectedSceneIds.length - 1}>Right</Button>
                    </Stack>
                  );
                })}
              </Stack>
              <Button variant="outlined" onClick={persistRank} disabled={rankSaving || selectedSceneIds.length < 2}>
                {selectedRank ? 'Update Rank' : 'Create Rank'}
              </Button>
            </Stack>
            <List dense>
              {scenes.map((scene) => (
                <ListItem key={scene.id} disablePadding>
                  <ListItemButton onClick={() => {
                    setSelectedSceneIds((current) => (
                      current.includes(scene.id)
                        ? current.filter((id) => id !== scene.id)
                        : [...current, scene.id]
                    ));
                  }}>
                    <Checkbox edge="start" checked={selectedSceneIds.includes(scene.id)} tabIndex={-1} disableRipple />
                    <ListItemText
                      primary={scene.name}
                      secondary={`${scene.masks?.length || 0} masks • ${scene.groups?.length || 0} groups${sceneRanks.find((rank) => (rank.scene_ids || []).map(Number).includes(scene.id)) ? ' • ranked' : ''}`}
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>

        <Grid item xs={12} md={9}>
          <Stack spacing={2}>
            <Paper sx={{ p: 2 }}>
              <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={2}>
                <Box>
                  <Typography variant="h6">Aligned Groups</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Each row targets the assigned group bucket at that rank in each selected scene.
                  </Typography>
                </Box>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                  <Button variant="outlined" onClick={autoAssignSimilar} disabled={!selectedScenes.length}>
                    Auto Assign Similar
                  </Button>
                  <Button variant="contained" onClick={persistAll} disabled={saving || !selectedScenes.length}>
                    {saving ? 'Saving...' : 'Save All Selected Scenes'}
                  </Button>
                </Stack>
              </Stack>
              {presetLoading ? (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Loading preset...
                </Typography>
              ) : null}
            </Paper>

            {!alignedRows.length ? (
              <Alert severity="info">Select one or more scenes with groups to start batch editing.</Alert>
            ) : (
              alignedRows.map((row) => {
                const edit = rowEdits[row.index] || createRowEdit();
                return (
                  <Card key={row.index} variant="outlined">
                    <CardContent>
                      <Stack spacing={2}>
                        <Box>
                          <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={1}>
                            <Typography variant="h6">Rank {row.index + 1}</Typography>
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => bubbleRanksUpFrom(row.index)}
                            >
                              Bubble Below Up
                            </Button>
                          </Stack>
                          <Grid container spacing={1} sx={{ mt: 1 }}>
                            {row.groups.map(({ sceneId, sceneName, groups }) => (
                              <Grid item xs={12} md={6} lg={4} key={`${sceneId}-${row.index}`}>
                                <Paper
                                  variant="outlined"
                                  onDragOver={(event) => event.preventDefault()}
                                  onDrop={(event) => {
                                    event.preventDefault();
                                    if (!dragState || dragState.sceneId !== sceneId) {
                                      return;
                                    }
                                    moveGroupToRank(sceneId, dragState.groupId, row.index);
                                    setDragState(null);
                                  }}
                                  sx={{
                                    p: 1.25,
                                    minHeight: 92,
                                    borderStyle: dragState?.sceneId === sceneId ? 'dashed' : 'solid',
                                  }}
                                >
                                  <Typography variant="caption" color="text.secondary">
                                    {sceneName}
                                  </Typography>
                                  {groups?.length ? (
                                    <Stack spacing={0.75} sx={{ mt: 0.5 }}>
                                      <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap' }}>
                                        {groups.map((group) => (
                                          <Box
                                            key={group.id}
                                            draggable
                                            onDragStart={() => setDragState({ sceneId, groupId: group.id })}
                                            onDragEnd={() => setDragState(null)}
                                            sx={{ display: 'inline-flex', cursor: 'grab' }}
                                          >
                                            <Chip
                                              label={group.name}
                                              variant="filled"
                                              sx={{ justifyContent: 'flex-start' }}
                                            />
                                          </Box>
                                        ))}
                                      </Stack>
                                      <Typography variant="body2" color="text.secondary">
                                        coverage {Math.round(averageCoverage(groups))}px avg
                                      </Typography>
                                    </Stack>
                                  ) : (
                                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                                      No group assigned
                                    </Typography>
                                  )}
                                </Paper>
                              </Grid>
                            ))}
                          </Grid>
                        </Box>

                        <Grid container spacing={2}>
                          <Grid item xs={12} md={4}>
                            <FormControl fullWidth>
                              <InputLabel>Layout Scope</InputLabel>
                              <Select
                                value={edit.layout_scope}
                                label="Layout Scope"
                                onChange={(event) => updateRowEdit(row.index, { layout_scope: event.target.value })}
                              >
                                <MenuItem value="scene">Scene</MenuItem>
                                <MenuItem value="rank">Rank</MenuItem>
                              </Select>
                            </FormControl>
                          </Grid>
                          <Grid item xs={12} md={4}>
                            <FormControl fullWidth>
                              <InputLabel>Media Binding</InputLabel>
                              <Select
                                value={edit.media_binding_type}
                                label="Media Binding"
                                onChange={(event) => updateRowEdit(row.index, { media_binding_type: event.target.value })}
                              >
                                <MenuItem value="video">Video</MenuItem>
                                <MenuItem value="animation">Animation</MenuItem>
                                <MenuItem value="animation_list">Animation List</MenuItem>
                                <MenuItem value="photo">Photo</MenuItem>
                                <MenuItem value="media_directory">Saved Media Folder</MenuItem>
                                <MenuItem value="media_list">Media List</MenuItem>
                                <MenuItem value="photo_list">Photo List</MenuItem>
                                <MenuItem value="media_channel">Media Channel</MenuItem>
                                <MenuItem value="direct_url">Direct URL</MenuItem>
                              </Select>
                            </FormControl>
                          </Grid>
                          <Grid item xs={12} md={2}>
                            <TextField
                              label="Order"
                              type="number"
                              value={edit.z_index}
                              onChange={(event) => updateRowEdit(row.index, { z_index: event.target.value })}
                              fullWidth
                            />
                          </Grid>
                          <Grid item xs={12} md={2}>
                            <TextField
                              label="Scale"
                              type="number"
                              value={edit.transform_scale}
                              onChange={(event) => updateRowEdit(row.index, { transform_scale: event.target.value })}
                              fullWidth
                            />
                          </Grid>
                          <Grid item xs={12} md={2}>
                            <TextField
                              label="Primary"
                              type="color"
                              value={edit.color_a}
                              onChange={(event) => updateRowEdit(row.index, { color_a: event.target.value })}
                              fullWidth
                            />
                          </Grid>
                          <Grid item xs={12} md={2}>
                            <TextField
                              label="Secondary"
                              type="color"
                              value={edit.color_b}
                              onChange={(event) => updateRowEdit(row.index, { color_b: event.target.value })}
                              fullWidth
                            />
                          </Grid>
                        </Grid>

                        {edit.media_binding_type === 'animation' && (
                          <FormControl fullWidth size="small">
                            <InputLabel>Animation</InputLabel>
                            <Select
                              label="Animation"
                              value={edit.animation_id}
                              onChange={(event) => updateRowEdit(row.index, { animation_id: event.target.value })}
                            >
                              {projectionAnimations.map((animation) => (
                                <MenuItem key={animation.id} value={animation.id}>
                                  {animation.thumbnail} {animation.name}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}
                        {edit.media_binding_type === 'animation_list' && (
                          <FormControl fullWidth size="small">
                            <InputLabel>Animation List</InputLabel>
                            <Select
                              label="Animation List"
                              value={edit.animation_list_id}
                              onChange={(event) => updateRowEdit(row.index, { animation_list_id: event.target.value })}
                            >
                              {animationLists.map((animationList) => (
                                <MenuItem key={animationList.id} value={animationList.id}>
                                  {animationList.name} ({(animationList.animation_ids || []).length})
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}
                        {edit.media_binding_type === 'video' && (
                          <TextField
                            select
                            label="Video"
                            value={edit.video_id}
                            onChange={(event) => updateRowEdit(row.index, { video_id: event.target.value })}
                            fullWidth
                          >
                            <MenuItem value=""><em>None</em></MenuItem>
                            {videos.map((video) => (
                              <MenuItem key={video.id} value={video.id}>{video.name}</MenuItem>
                            ))}
                          </TextField>
                        )}

                        {edit.media_binding_type === 'photo' && (
                          <TextField
                            select
                            label="Photo"
                            value={edit.photo_id}
                            onChange={(event) => updateRowEdit(row.index, { photo_id: event.target.value })}
                            fullWidth
                          >
                            <MenuItem value=""><em>None</em></MenuItem>
                            {photos.map((photo) => (
                              <MenuItem key={photo.id} value={photo.id}>{photo.name}</MenuItem>
                            ))}
                          </TextField>
                        )}

                        {edit.media_binding_type === 'media_list' && (
                          <TextField
                            select
                            label="Media List"
                            value={edit.media_list_id}
                            onChange={(event) => updateRowEdit(row.index, { media_list_id: event.target.value })}
                            fullWidth
                          >
                            <MenuItem value=""><em>None</em></MenuItem>
                            {mediaLists.map((list) => (
                              <MenuItem key={list.id} value={list.id}>{list.name}</MenuItem>
                            ))}
                          </TextField>
                        )}

                        {edit.media_binding_type === 'photo_list' && (
                          <TextField
                            select
                            label="Photo List"
                            value={edit.photo_list_id}
                            onChange={(event) => updateRowEdit(row.index, { photo_list_id: event.target.value })}
                            fullWidth
                          >
                            <MenuItem value=""><em>None</em></MenuItem>
                            {photoLists.map((list) => (
                              <MenuItem key={list.id} value={list.id}>{list.name}</MenuItem>
                            ))}
                          </TextField>
                        )}

                        {edit.media_binding_type === 'media_channel' && (
                          <TextField
                            select
                            label="Media Channel"
                            value={edit.media_channel_id}
                            onChange={(event) => updateRowEdit(row.index, { media_channel_id: event.target.value })}
                            fullWidth
                          >
                            <MenuItem value=""><em>None</em></MenuItem>
                            {mediaChannels.map((channel) => (
                              <MenuItem key={channel.id} value={channel.id}>{channel.name}</MenuItem>
                            ))}
                          </TextField>
                        )}

                        {edit.media_binding_type === 'media_directory' && (
                          <FormControl fullWidth>
                            <InputLabel>Saved Media Folders</InputLabel>
                            <Select
                              multiple
                              value={edit.media_directory_ids}
                              label="Saved Media Folders"
                              onChange={(event) => updateRowEdit(row.index, {
                                media_directory_ids: typeof event.target.value === 'string'
                                  ? normalizeNumericIdList(event.target.value.split(','))
                                  : normalizeNumericIdList(event.target.value),
                              })}
                            >
                              {mediaDirectories.map((directory) => (
                                <MenuItem key={directory.id} value={directory.id}>
                                  {directory.name}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}

                        {edit.media_binding_type === 'direct_url' && (
                          <TextField
                            label="Direct URL"
                            value={edit.direct_url}
                            onChange={(event) => updateRowEdit(row.index, { direct_url: event.target.value })}
                            fullWidth
                          />
                        )}

                        <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>
                          <FormControlLabel
                            control={<Switch checked={edit.auto_advance !== false} onChange={(event) => updateRowEdit(row.index, { auto_advance: event.target.checked })} />}
                            label="Auto-advance"
                          />
                          <FormControlLabel
                            control={<Switch checked={Boolean(edit.shuffle)} onChange={(event) => updateRowEdit(row.index, { shuffle: event.target.checked })} />}
                            label="Shuffle"
                          />
                          <FormControlLabel
                            control={<Switch checked={edit.visible !== false} onChange={(event) => updateRowEdit(row.index, { visible: event.target.checked })} />}
                            label="Visible"
                          />
                        </Stack>
                      </Stack>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </Stack>
        </Grid>
      </Grid>
    </Stack>
  );
}

export default SceneControl;
