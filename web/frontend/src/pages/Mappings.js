import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  Drawer,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Slider,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  CloudUpload as UploadIcon,
  Delete as DeleteIcon,
  ExpandLess as ExpandLessIcon,
  ExpandMore as ExpandMoreIcon,
  Fullscreen as FullscreenIcon,
  FullscreenExit as FullscreenExitIcon,
  Save as SaveIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from '@mui/icons-material';

import { mappingsApi, mediaLibraryApi, photoApi, photoListApi, projectionApi, videoApi } from '../services/api';

const SIDEBAR_WIDTH = 320;
const INSPECTOR_WIDTH = 360;
const PANEL_BG = '#f4efe3';
const PANEL_ALT_BG = '#fbf7ef';
const PANEL_BORDER = 'rgba(68, 58, 43, 0.14)';
const PANEL_TEXT = '#261f16';
const PANEL_SUBTEXT = 'rgba(38, 31, 22, 0.66)';
const CANVAS_FRAME = '#d6c8ae';

const emptyGroup = () => ({
  id: `group_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
  name: 'New Group',
  mask_ids: [],
  media_binding_type: 'video',
  animation_id: '',
  animation_list_id: '',
  video_id: '',
  photo_id: '',
  media_list_id: '',
  photo_list_id: '',
  media_channel_id: '',
  media_directory_id: '',
  media_directory_ids: [],
  direct_url: '',
  playlist_entries: [],
  auto_advance: true,
  shuffle: false,
  z_index: 0,
  visible: true,
  transform: { scale: 1, offset_x: 0, offset_y: 0, rotation: 0 },
  fill_mode: 'gradient',
  color_a: '#b56a2d',
  color_b: '#6a7f58',
});

const GROUP_COLOR_PALETTE = [
  ['#d1495b', '#edae49'],
  ['#00798c', '#d1495b'],
  ['#30638e', '#f4d35e'],
  ['#6a994e', '#a7c957'],
  ['#5f0f40', '#9a031e'],
  ['#0f4c5c', '#e36414'],
  ['#7b2cbf', '#c77dff'],
  ['#2a9d8f', '#e9c46a'],
  ['#3a86ff', '#8338ec'],
  ['#ef476f', '#ffd166'],
];

function normalizeNumericIdList(values) {
  return (Array.isArray(values) ? values : [])
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function addHexAlpha(color, alphaHex) {
  if (typeof color !== 'string') {
    return color;
  }
  const normalized = color.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(normalized)) {
    return `${normalized}${alphaHex}`;
  }
  return normalized;
}

function Mappings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const stageRef = useRef(null);
  const previewCanvasRef = useRef(null);

  const [scenes, setScenes] = useState([]);
  const [selectedSceneId, setSelectedSceneId] = useState('');
  const [sceneDraft, setSceneDraft] = useState(null);
  const [videos, setVideos] = useState([]);
  const [photos, setPhotos] = useState([]);
  const [mediaLists, setMediaLists] = useState([]);
  const [photoLists, setPhotoLists] = useState([]);
  const [mediaChannels, setMediaChannels] = useState([]);
  const [mediaDirectories, setMediaDirectories] = useState([]);
  const [projectionAnimations, setProjectionAnimations] = useState([]);
  const [animationLists, setAnimationLists] = useState([]);
  const [maskImages, setMaskImages] = useState({});
  const [selectedGroupId, setSelectedGroupId] = useState('');
  const [uiHidden, setUiHidden] = useState(false);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [polygonDraft, setPolygonDraft] = useState(null);
  const [collapsedSections, setCollapsedSections] = useState({
    scenes: false,
    sceneSettings: false,
    masks: false,
    groups: false,
    media: false,
    visual: false,
  });
  const requestedSceneId = searchParams.get('scene');

  useEffect(() => {
    const pickInitialScene = (loadedScenes) => {
      if (!loadedScenes?.length) {
        createSceneDraft();
        return;
      }
      const targetScene = requestedSceneId
        ? loadedScenes.find((scene) => String(scene.id) === String(requestedSceneId))
        : null;
      loadScene(targetScene || loadedScenes[0]);
    };

    Promise.all([
      mappingsApi.listScenes(),
      videoApi.getVideos(),
      photoApi.getPhotos(),
      mediaLibraryApi.listDirectories(),
      mediaLibraryApi.listMediaLists(),
      photoListApi.listPhotoLists(),
      mediaLibraryApi.listMediaChannels(),
      projectionApi.listAnimations(),
      projectionApi.listAnimationLists(),
    ]).then(([sceneRes, videoRes, photoRes, mediaDirectoryRes, mediaListRes, photoListRes, mediaChannelRes, animationRes, animationListRes]) => {
      const loadedScenes = sceneRes.data || [];
      setScenes(loadedScenes);
      setVideos(videoRes.data.videos || []);
      setPhotos(photoRes.data.photos || []);
      setMediaDirectories(mediaDirectoryRes.data || []);
      setMediaLists(mediaListRes.data || []);
      setPhotoLists(photoListRes.data || []);
      setMediaChannels(mediaChannelRes.data || []);
      setProjectionAnimations(animationRes.data?.animations || []);
      setAnimationLists(animationListRes.data?.animation_lists || []);
      pickInitialScene(loadedScenes);
    }).catch((err) => {
      console.error(err);
      setError('Failed to load mappings workspace');
    });
  }, [requestedSceneId]);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key.toLowerCase() === 'h' && uiHidden) {
        setUiHidden(false);
      }
      if (event.key.toLowerCase() === 'f') {
        toggleFullscreen();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [uiHidden]);

  const selectedScene = useMemo(
    () => scenes.find((scene) => scene.id === selectedSceneId) || null,
    [scenes, selectedSceneId]
  );

  const selectedGroup = useMemo(
    () => sceneDraft?.groups?.find((group) => group.id === selectedGroupId) || null,
    [sceneDraft, selectedGroupId]
  );

  const loadScene = (scene) => {
    setSelectedSceneId(scene.id);
    setSceneDraft(JSON.parse(JSON.stringify(scene)));
    setSelectedGroupId(scene.groups?.[0]?.id || '');
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set('scene', String(scene.id));
      return next;
    }, { replace: true });
  };

  const createSceneDraft = () => {
    setSelectedSceneId('');
    setSceneDraft({
      name: `Scene ${new Date().toLocaleString()}`,
      canvas_width: 1280,
      canvas_height: 720,
      mask_mode: 'luminance',
      masks: [],
      groups: [emptyGroup()],
      render_settings: { background: '#000000' },
    });
    setSelectedGroupId('');
  };

  const getMaskUrl = useCallback((mask) => {
    if (!selectedSceneId || !mask?.id) return null;
    return `/api/mappings/scenes/${selectedSceneId}/masks/${mask.id}/file`;
  }, [selectedSceneId]);

  useEffect(() => {
    let active = true;
    const masks = sceneDraft?.masks || [];
    if (!masks.length || !selectedSceneId) {
      setMaskImages({});
      return undefined;
    }

    Promise.all(
      masks.map((mask) => new Promise((resolve) => {
        const image = new Image();
        image.onload = () => resolve([mask.id, image]);
        image.onerror = () => resolve([mask.id, null]);
        image.src = getMaskUrl(mask);
      }))
    ).then((entries) => {
      if (!active) return;
      setMaskImages(Object.fromEntries(entries.filter(([, image]) => image)));
    });

    return () => {
      active = false;
    };
  }, [sceneDraft?.masks, selectedSceneId, getMaskUrl]);

  useEffect(() => {
    if (!sceneDraft || !previewCanvasRef.current) return;
    renderStage(previewCanvasRef.current, sceneDraft, maskImages, selectedGroupId, polygonDraft);
  }, [sceneDraft, maskImages, selectedGroupId, polygonDraft]);

  const persistScene = async () => {
    try {
      const payload = {
        ...sceneDraft,
        groups: (sceneDraft.groups || []).map((group) => ({
          ...group,
          video_id: group.video_id ? Number(group.video_id) : null,
          photo_id: group.photo_id ? Number(group.photo_id) : null,
          media_list_id: group.media_list_id ? Number(group.media_list_id) : null,
          photo_list_id: group.photo_list_id ? Number(group.photo_list_id) : null,
          animation_list_id: group.animation_list_id || null,
          media_channel_id: group.media_channel_id ? Number(group.media_channel_id) : null,
          media_directory_id: group.media_directory_id ? Number(group.media_directory_id) : null,
          media_directory_ids: normalizeNumericIdList(group.media_directory_ids || []),
        })),
      };

      const response = selectedScene
        ? await mappingsApi.updateScene(selectedScene.id, payload)
        : await mappingsApi.createScene(payload);

      const updatedScene = response.data;
      setScenes((current) => {
        if (selectedScene) {
          return current.map((scene) => (scene.id === updatedScene.id ? updatedScene : scene));
        }
        return [updatedScene, ...current];
      });
      loadScene(updatedScene);
      setMessage('Scene saved');
    } catch (err) {
      console.error(err);
      setError('Failed to save scene');
    }
  };

  const deleteScene = async () => {
    if (!selectedScene) {
      return;
    }
    try {
      await mappingsApi.deleteScene(selectedScene.id);
      const remainingScenes = scenes.filter((scene) => scene.id !== selectedScene.id);
      setScenes(remainingScenes);
      if (remainingScenes.length) {
        loadScene(remainingScenes[0]);
      } else {
        createSceneDraft();
        setSearchParams((current) => {
          const next = new URLSearchParams(current);
          next.delete('scene');
          return next;
        }, { replace: true });
      }
      setMessage(`Deleted scene "${selectedScene.name}"`);
    } catch (err) {
      console.error(err);
      setError('Failed to delete scene');
    }
  };

  const uploadMasks = async (event) => {
    if (!selectedScene || !event.target.files?.length) return;
    const formData = new FormData();
    Array.from(event.target.files).forEach((file) => formData.append('masks', file));

    try {
      const response = await mappingsApi.uploadMasks(selectedScene.id, formData);
      const updatedScene = response.data;
      setScenes((current) => current.map((scene) => (scene.id === updatedScene.id ? updatedScene : scene)));
      loadScene(updatedScene);
      setMessage(`Uploaded ${event.target.files.length} masks`);
    } catch (err) {
      console.error(err);
      setError('Failed to upload masks');
    }
  };

  const importSceneBundle = async (event) => {
    if (!event.target.files?.length) return;
    const formData = new FormData();
    formData.append('bundle', event.target.files[0]);

    try {
      const response = await mappingsApi.importScene(formData);
      const importedScene = response.data;
      const scenesResponse = await mappingsApi.listScenes();
      setScenes(scenesResponse.data);
      loadScene(importedScene);
      setMessage(`Imported scene "${importedScene.name}"`);
      setError('');
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to import scene bundle');
    } finally {
      event.target.value = '';
    }
  };

  const startPolygonMask = () => {
    if (!selectedScene) {
      setError('Save the scene before creating masks.');
      return;
    }
    setPolygonDraft({
      name: `Mask ${new Date().toLocaleTimeString()}`,
      points: [],
    });
    setMessage('');
    setError('');
  };

  const cancelPolygonMask = () => {
    setPolygonDraft(null);
  };

  const undoPolygonPoint = () => {
    setPolygonDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        points: current.points.slice(0, -1),
      };
    });
  };

  const savePolygonMask = async () => {
    if (!selectedScene || !polygonDraft) {
      return;
    }
    if (polygonDraft.points.length < 3) {
      setError('Polygon masks require at least 3 points.');
      return;
    }

    try {
      const response = await mappingsApi.createPolygonMask(selectedScene.id, polygonDraft);
      const updatedScene = response.data;
      setScenes((current) => current.map((scene) => (scene.id === updatedScene.id ? updatedScene : scene)));
      loadScene(updatedScene);
      setPolygonDraft(null);
      setMessage(`Created mask "${polygonDraft.name}"`);
    } catch (err) {
      console.error(err);
      setError('Failed to create polygon mask');
    }
  };

  const updateSceneField = (field, value) => {
    setSceneDraft((current) => ({ ...current, [field]: value }));
  };

  const updateGroup = (groupId, patch) => {
    setSceneDraft((current) => ({
      ...current,
      groups: current.groups.map((group) => (group.id === groupId ? { ...group, ...patch } : group)),
    }));
  };

  const addGroup = () => {
    const group = emptyGroup();
    setSceneDraft((current) => ({
      ...current,
      groups: [...(current.groups || []), group],
    }));
    setSelectedGroupId(group.id);
  };

  const buildGroupFromMask = (mask, index, zIndexBase = 0) => {
    const [colorA, colorB] = GROUP_COLOR_PALETTE[index % GROUP_COLOR_PALETTE.length];
    return {
      ...emptyGroup(),
      name: mask.name || mask.file_name || `Mask ${index + 1}`,
      mask_ids: [mask.id],
      z_index: zIndexBase + index,
      color_a: colorA,
      color_b: colorB,
    };
  };

  const ensureFullSceneMask = async () => {
    if (!selectedScene || !sceneDraft) {
      throw new Error('Save the scene before creating groups from masks.');
    }

    const existingFullMask = (sceneDraft.masks || []).find((mask) => (
      Number(mask.width) === Number(sceneDraft.canvas_width)
      && Number(mask.height) === Number(sceneDraft.canvas_height)
      && ['full', 'background', 'full_scene'].includes(String(mask.name || '').toLowerCase())
    ));
    if (existingFullMask) {
      return existingFullMask;
    }

    const response = await mappingsApi.createPolygonMask(selectedScene.id, {
      name: 'full',
      points: [
        { x: 0, y: 0 },
        { x: sceneDraft.canvas_width, y: 0 },
        { x: sceneDraft.canvas_width, y: sceneDraft.canvas_height },
        { x: 0, y: sceneDraft.canvas_height },
      ],
    });
    const updatedScene = response.data;
    setScenes((current) => current.map((scene) => (scene.id === updatedScene.id ? updatedScene : scene)));
    loadScene(updatedScene);
    return (updatedScene.masks || []).find((mask) => String(mask.name || '').toLowerCase() === 'full')
      || updatedScene.masks?.[updatedScene.masks.length - 1];
  };

  const createGroupsFromMasks = async () => {
    if (!selectedScene || !sceneDraft) {
      setError('Save the scene before generating groups from masks.');
      return;
    }
    if (!(sceneDraft.masks || []).length) {
      setError('Add masks before generating groups.');
      return;
    }

    try {
      setMessage('');
      setError('');
      const fullMask = await ensureFullSceneMask();
      const masks = (sceneDraft.masks || []).filter((mask) => mask.id !== fullMask?.id);
      const maskGroups = masks.map((mask, index) => buildGroupFromMask(mask, index, 1));
      const backgroundGroup = {
        ...emptyGroup(),
        name: 'background',
        mask_ids: fullMask ? [fullMask.id] : [],
        z_index: 0,
        color_a: '#000000',
        color_b: '#000000',
      };

      setSceneDraft((current) => ({
        ...current,
        groups: [backgroundGroup, ...maskGroups],
      }));
      setSelectedGroupId(backgroundGroup.id);
      setMessage(`Created ${maskGroups.length} mask groups plus background group.`);
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to generate groups from masks.');
    }
  };

  const removeGroup = (groupId) => {
    setSceneDraft((current) => ({
      ...current,
      groups: current.groups.filter((group) => group.id !== groupId),
    }));
    if (selectedGroupId === groupId) {
      const remaining = sceneDraft.groups.filter((group) => group.id !== groupId);
      setSelectedGroupId(remaining[0]?.id || '');
    }
  };

  const deleteMask = async (maskId) => {
    if (!selectedScene) {
      return;
    }
    try {
      const response = await mappingsApi.deleteMask(selectedScene.id, maskId);
      const updatedScene = response.data;
      setScenes((current) => current.map((scene) => (scene.id === updatedScene.id ? updatedScene : scene)));
      loadScene(updatedScene);
      setMessage('Mask deleted');
    } catch (err) {
      console.error(err);
      setError('Failed to delete mask');
    }
  };

  const toggleMaskForGroup = (groupId, maskId) => {
    setSceneDraft((current) => {
      if (!current?.groups) {
        return current;
      }

      return {
        ...current,
        groups: current.groups.map((group) => {
          if (group.id !== groupId) {
            return group;
          }

          const currentMaskIds = group.mask_ids || [];
          const nextMaskIds = currentMaskIds.includes(maskId)
            ? currentMaskIds.filter((id) => id !== maskId)
            : [...currentMaskIds, maskId];

          return {
            ...group,
            mask_ids: nextMaskIds,
          };
        }),
      };
    });
  };

  const toggleFullscreen = async () => {
    if (!stageRef.current) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await stageRef.current.requestFullscreen();
    }
  };

  const toggleSection = (section) => {
    setCollapsedSections((current) => ({
      ...current,
      [section]: !current[section],
    }));
  };

  const handleStageClick = (event) => {
    if (!polygonDraft || !sceneDraft || !previewCanvasRef.current) {
      return;
    }

    const rect = previewCanvasRef.current.getBoundingClientRect();
    const width = sceneDraft.canvas_width || 1280;
    const height = sceneDraft.canvas_height || 720;
    const scaleX = width / rect.width;
    const scaleY = height / rect.height;
    const x = Math.max(0, Math.min(width, (event.clientX - rect.left) * scaleX));
    const y = Math.max(0, Math.min(height, (event.clientY - rect.top) * scaleY));

    setPolygonDraft((current) => ({
      ...current,
      points: [...current.points, { x: Math.round(x), y: Math.round(y) }],
    }));
  };

  return (
    <Box sx={{ minHeight: 'calc(100vh - 96px)', bgcolor: '#e9dfcf', color: PANEL_TEXT, p: uiHidden ? 0 : 2 }}>
      {!uiHidden && (
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Box>
            <Typography variant="h4" sx={{ color: PANEL_TEXT }}>Mappings</Typography>
            <Typography variant="body2" sx={{ color: PANEL_SUBTEXT }}>
              Stage-first scene editor. `H` hides chrome. `F` toggles fullscreen.
            </Typography>
          </Box>
          <Stack direction="row" spacing={1}>
            <Button variant="contained" color="secondary" startIcon={<AddIcon />} onClick={createSceneDraft}>
              New Scene
            </Button>
            <Button component="label" variant="outlined" startIcon={<UploadIcon />}>
              Import Scene
              <input hidden accept=".zip" type="file" onChange={importSceneBundle} />
            </Button>
            <Button
              component="a"
              href={selectedScene ? mappingsApi.getExportUrl(selectedScene.id) : undefined}
              variant="outlined"
              disabled={!selectedScene}
            >
              Export Scene
            </Button>
            <Button variant="outlined" color="error" startIcon={<DeleteIcon />} onClick={deleteScene} disabled={!selectedScene}>
              Delete Scene
            </Button>
            <Button variant="outlined" startIcon={leftOpen ? <ChevronLeftIcon /> : <ChevronRightIcon />} onClick={() => setLeftOpen((v) => !v)}>
              Library
            </Button>
            <Button variant="outlined" startIcon={rightOpen ? <ChevronRightIcon /> : <ChevronLeftIcon />} onClick={() => setRightOpen((v) => !v)}>
              Inspector
            </Button>
            <Button variant="outlined" startIcon={<VisibilityOffIcon />} onClick={() => setUiHidden(true)}>
              Hide UI
            </Button>
            <Button variant="outlined" startIcon={document.fullscreenElement ? <FullscreenExitIcon /> : <FullscreenIcon />} onClick={toggleFullscreen}>
              Fullscreen
            </Button>
            <Button variant="contained" startIcon={<SaveIcon />} onClick={persistScene}>
              Save Scene
            </Button>
          </Stack>
        </Stack>
      )}

      <Box sx={{ display: 'flex', gap: 2, minHeight: uiHidden ? '100vh' : 'calc(100vh - 180px)' }}>
        {!uiHidden && leftOpen && (
          <Drawer
            variant="permanent"
            anchor="left"
            sx={{
              width: SIDEBAR_WIDTH,
              flexShrink: 0,
              '& .MuiDrawer-paper': {
                width: SIDEBAR_WIDTH,
                position: 'relative',
                bgcolor: PANEL_BG,
                color: PANEL_TEXT,
                border: `1px solid ${PANEL_BORDER}`,
                borderRadius: 2,
                p: 2,
              },
            }}
          >
            <Stack spacing={2}>
              <Paper sx={panelPaperSx}>
                <SectionHeader
                  title="Scenes"
                  collapsed={collapsedSections.scenes}
                  onToggle={() => toggleSection('scenes')}
                  action={(
                    <IconButton onClick={createSceneDraft} color="inherit" size="small">
                      <AddIcon />
                    </IconButton>
                  )}
                />
                <Collapse in={!collapsedSections.scenes}>
                  <Button fullWidth variant="outlined" startIcon={<AddIcon />} onClick={createSceneDraft} sx={{ mb: 1.5 }}>
                    New Scene
                  </Button>
                  <List dense>
                    {scenes.map((scene) => (
                      <ListItem key={scene.id} disablePadding>
                        <ListItemButton selected={selectedSceneId === scene.id} onClick={() => loadScene(scene)}>
                          <ListItemText primary={scene.name} secondary={`${scene.masks.length} masks • ${scene.groups.length} groups`} />
                        </ListItemButton>
                      </ListItem>
                    ))}
                  </List>
                </Collapse>
              </Paper>

              {sceneDraft && (
                <>
                  <Paper sx={panelPaperSx}>
                    <SectionHeader
                      title="Scene Settings"
                      collapsed={collapsedSections.sceneSettings}
                      onToggle={() => toggleSection('sceneSettings')}
                    />
                    <Collapse in={!collapsedSections.sceneSettings}>
                      <Stack spacing={2}>
                        <TextField
                          label="Scene Name"
                          value={sceneDraft.name}
                          onChange={(event) => updateSceneField('name', event.target.value)}
                          fullWidth
                          InputLabelProps={{ sx: { color: PANEL_SUBTEXT } }}
                          sx={darkFieldSx}
                        />
                        <Stack direction="row" spacing={1}>
                          <TextField
                            label="Width"
                            type="number"
                            value={sceneDraft.canvas_width}
                            onChange={(event) => updateSceneField('canvas_width', Number(event.target.value))}
                            sx={darkFieldSx}
                          />
                          <TextField
                            label="Height"
                            type="number"
                            value={sceneDraft.canvas_height}
                            onChange={(event) => updateSceneField('canvas_height', Number(event.target.value))}
                            sx={darkFieldSx}
                          />
                        </Stack>
                        <TextField
                          label="Background"
                          type="color"
                          value={sceneDraft.render_settings?.background || '#000000'}
                          onChange={(event) => updateSceneField('render_settings', { ...sceneDraft.render_settings, background: event.target.value })}
                          sx={{ width: 160 }}
                        />
                      </Stack>
                    </Collapse>
                  </Paper>

                  <Paper sx={panelPaperSx}>
                    <SectionHeader
                      title="Mask Library"
                      collapsed={collapsedSections.masks}
                      onToggle={() => toggleSection('masks')}
                      action={(
                        <Stack direction="row" spacing={1}>
                          <Button size="small" variant="outlined" onClick={startPolygonMask} disabled={!selectedScene || Boolean(polygonDraft)}>
                            New Polygon
                          </Button>
                          <Button component="label" size="small" variant="outlined" startIcon={<UploadIcon />} disabled={!selectedScene}>
                            Upload
                            <input hidden accept="image/png" multiple type="file" onChange={uploadMasks} />
                          </Button>
                        </Stack>
                      )}
                    />
                    <Collapse in={!collapsedSections.masks}>
                      <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
                        <Button size="small" variant="contained" onClick={createGroupsFromMasks} disabled={!selectedScene || !(sceneDraft?.masks || []).length}>
                          Groups From Masks
                        </Button>
                      </Stack>
                      {polygonDraft ? (
                        <Paper sx={{ p: 1.5, mb: 1.5, bgcolor: '#fff7ea', border: `1px solid ${PANEL_BORDER}`, boxShadow: 'none' }}>
                          <Stack spacing={1.5}>
                            <Typography variant="subtitle2">Polygon Mask Authoring</Typography>
                            <TextField
                              label="Mask Name"
                              value={polygonDraft.name}
                              onChange={(event) => setPolygonDraft((current) => ({ ...current, name: event.target.value }))}
                              fullWidth
                              sx={darkFieldSx}
                            />
                            <Typography variant="body2" sx={{ color: PANEL_SUBTEXT }}>
                              Click the stage to place points. The polygon closes automatically on save.
                            </Typography>
                            <Typography variant="body2" sx={{ color: PANEL_SUBTEXT }}>
                              {polygonDraft.points.length} points
                            </Typography>
                            <Stack direction="row" spacing={1}>
                              <Button size="small" variant="outlined" onClick={undoPolygonPoint} disabled={!polygonDraft.points.length}>
                                Undo
                              </Button>
                              <Button size="small" variant="outlined" color="inherit" onClick={cancelPolygonMask}>
                                Cancel
                              </Button>
                              <Button size="small" variant="contained" onClick={savePolygonMask} disabled={polygonDraft.points.length < 3}>
                                Save Mask
                              </Button>
                            </Stack>
                          </Stack>
                        </Paper>
                      ) : null}
                      <Box sx={{ maxHeight: 340, overflowY: 'auto' }}>
                        <List dense>
                          {(sceneDraft.masks || []).map((mask) => {
                            const active = selectedGroup?.mask_ids?.includes(mask.id);
                            return (
                              <ListItem
                                key={mask.id}
                                disablePadding
                                secondaryAction={(
                                  <IconButton edge="end" onClick={() => deleteMask(mask.id)} color="inherit">
                                    <DeleteIcon />
                                  </IconButton>
                                )}
                              >
                                <ListItemButton onClick={() => selectedGroup && toggleMaskForGroup(selectedGroup.id, mask.id)}>
                                  <ListItemText primary={mask.file_name} secondary={`${mask.width}x${mask.height}`} />
                                  <Chip size="small" label={active ? 'On' : 'Off'} color={active ? 'primary' : 'default'} />
                                </ListItemButton>
                              </ListItem>
                            );
                          })}
                        </List>
                      </Box>
                    </Collapse>
                  </Paper>
                </>
              )}
            </Stack>
          </Drawer>
        )}

        <Box
          ref={stageRef}
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            bgcolor: '#000',
            borderRadius: uiHidden ? 0 : 3,
            border: uiHidden ? 'none' : `1px solid ${CANVAS_FRAME}`,
            overflow: 'hidden',
            position: 'relative',
            boxShadow: uiHidden ? 'none' : '0 14px 40px rgba(69, 48, 18, 0.12)',
          }}
        >
          {!uiHidden && sceneDraft && (
            <Stack direction="row" spacing={1} sx={{ p: 1.5, bgcolor: 'rgba(248,243,233,0.96)', borderBottom: `1px solid ${CANVAS_FRAME}` }}>
              <Chip label={`${sceneDraft.masks?.length || 0} masks`} />
              <Chip label={`${sceneDraft.groups?.length || 0} groups`} />
              <Chip label={selectedGroup ? `Selected: ${selectedGroup.name}` : 'No group selected'} color="primary" />
            </Stack>
          )}

          <Box sx={{ flex: 1, display: 'grid', placeItems: 'center', p: uiHidden ? 0 : 2 }}>
            {sceneDraft ? (
              <Box sx={{ width: '100%', maxWidth: uiHidden ? '100vw' : 1320 }}>
                <canvas
                  ref={previewCanvasRef}
                  onClick={handleStageClick}
                  style={{
                    width: '100%',
                    aspectRatio: `${sceneDraft.canvas_width || 1280} / ${sceneDraft.canvas_height || 720}`,
                    display: 'block',
                    background: '#000',
                    cursor: polygonDraft ? 'crosshair' : 'default',
                  }}
                />
              </Box>
            ) : (
              <Typography color="rgba(255,255,255,0.65)">Create or select a scene to start.</Typography>
            )}
          </Box>
        </Box>

        {!uiHidden && rightOpen && (
          <Drawer
            variant="permanent"
            anchor="right"
            sx={{
              width: INSPECTOR_WIDTH,
              flexShrink: 0,
              '& .MuiDrawer-paper': {
                width: INSPECTOR_WIDTH,
                position: 'relative',
                bgcolor: PANEL_BG,
                color: PANEL_TEXT,
                border: `1px solid ${PANEL_BORDER}`,
                borderRadius: 2,
                p: 2,
              },
            }}
          >
            <Stack spacing={2}>
              <Paper sx={panelPaperSx}>
                <SectionHeader
                  title="Groups"
                  collapsed={collapsedSections.groups}
                  onToggle={() => toggleSection('groups')}
                  action={(
                    <Button size="small" variant="contained" startIcon={<AddIcon />} onClick={addGroup}>
                      Add
                    </Button>
                  )}
                />
                <Collapse in={!collapsedSections.groups}>
                  <List dense>
                    {(sceneDraft?.groups || []).map((group) => (
                      <ListItem
                        key={group.id}
                        disablePadding
                        secondaryAction={(
                          <IconButton edge="end" onClick={() => removeGroup(group.id)} color="inherit">
                            <DeleteIcon />
                          </IconButton>
                        )}
                      >
                        <ListItemButton
                          selected={selectedGroupId === group.id}
                          onClick={() => setSelectedGroupId(group.id)}
                          sx={{
                            borderRadius: 1.5,
                            mb: 0.75,
                            border: `1px solid ${selectedGroupId === group.id ? addHexAlpha(group.color_a || '#b56a2d', 'aa') : PANEL_BORDER}`,
                            background: `linear-gradient(135deg, ${addHexAlpha(group.color_a || '#b56a2d', '33')}, ${addHexAlpha(group.color_b || '#6a7f58', '66')})`,
                            color: PANEL_TEXT,
                            '&.Mui-selected': {
                              background: `linear-gradient(135deg, ${addHexAlpha(group.color_a || '#b56a2d', '55')}, ${addHexAlpha(group.color_b || '#6a7f58', '88')})`,
                            },
                            '&.Mui-selected:hover': {
                              background: `linear-gradient(135deg, ${addHexAlpha(group.color_a || '#b56a2d', '66')}, ${addHexAlpha(group.color_b || '#6a7f58', '99')})`,
                            },
                            '&:hover': {
                              background: `linear-gradient(135deg, ${addHexAlpha(group.color_a || '#b56a2d', '44')}, ${addHexAlpha(group.color_b || '#6a7f58', '77')})`,
                            },
                          }}
                        >
                          <ListItemText
                            primary={group.name}
                            secondary={`${group.mask_ids.length} masks • z ${group.z_index || 0}`}
                            primaryTypographyProps={{ fontWeight: selectedGroupId === group.id ? 700 : 600 }}
                            secondaryTypographyProps={{ color: 'rgba(38, 31, 22, 0.78)' }}
                          />
                        </ListItemButton>
                      </ListItem>
                    ))}
                  </List>
                </Collapse>
              </Paper>

              {selectedGroup ? (
                <Stack spacing={2}>
                  <Paper sx={panelPaperSx}>
                    <SectionHeader
                      title="Media Manager"
                      collapsed={collapsedSections.media}
                      onToggle={() => toggleSection('media')}
                      action={(
                        <Tooltip title={selectedGroup.visible === false ? 'Show Group' : 'Hide Group'}>
                          <IconButton color="inherit" onClick={() => updateGroup(selectedGroup.id, { visible: selectedGroup.visible === false })}>
                            {selectedGroup.visible === false ? <VisibilityOffIcon /> : <VisibilityIcon />}
                          </IconButton>
                        </Tooltip>
                      )}
                    />
                    <Collapse in={!collapsedSections.media}>
                      <Stack spacing={2}>
                        <TextField
                          label="Group Name"
                          value={selectedGroup.name}
                          onChange={(event) => updateGroup(selectedGroup.id, { name: event.target.value })}
                          sx={darkFieldSx}
                        />

                        <Stack direction="row" spacing={1}>
                          <TextField
                            label="Order"
                            type="number"
                            value={selectedGroup.z_index || 0}
                            onChange={(event) => updateGroup(selectedGroup.id, { z_index: Number(event.target.value) })}
                            sx={darkFieldSx}
                          />
                          <TextField
                            label="Scale"
                            value={selectedGroup.transform?.scale || 1}
                            onChange={(event) => updateGroup(selectedGroup.id, {
                              transform: { ...(selectedGroup.transform || {}), scale: Number(event.target.value) || 1 },
                            })}
                            sx={darkFieldSx}
                          />
                        </Stack>

                        <FormControl fullWidth sx={darkSelectSx}>
                          <InputLabel>Media Binding</InputLabel>
                          <Select
                            value={selectedGroup.media_binding_type}
                            label="Media Binding"
                            onChange={(event) => updateGroup(selectedGroup.id, { media_binding_type: event.target.value })}
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

                        {selectedGroup.media_binding_type === 'animation' && (
                          <FormControl fullWidth size="small">
                            <InputLabel>Animation</InputLabel>
                            <Select
                              label="Animation"
                              value={selectedGroup.animation_id || ''}
                              onChange={(event) => updateGroup(selectedGroup.id, { animation_id: event.target.value })}
                            >
                              {projectionAnimations.map((animation) => (
                                <MenuItem key={animation.id} value={animation.id}>
                                  {animation.thumbnail} {animation.name}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}

                        {selectedGroup.media_binding_type === 'animation_list' && (
                          <FormControl fullWidth size="small">
                            <InputLabel>Animation List</InputLabel>
                            <Select
                              label="Animation List"
                              value={selectedGroup.animation_list_id || ''}
                              onChange={(event) => updateGroup(selectedGroup.id, { animation_list_id: event.target.value })}
                            >
                              {animationLists.map((animationList) => (
                                <MenuItem key={animationList.id} value={animationList.id}>
                                  {animationList.name} ({(animationList.animation_ids || []).length})
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}
                        {selectedGroup.media_binding_type === 'video' && (
                          <FormControl fullWidth sx={darkSelectSx}>
                            <InputLabel>Video</InputLabel>
                            <Select
                              value={selectedGroup.video_id || ''}
                              label="Video"
                              onChange={(event) => updateGroup(selectedGroup.id, { video_id: event.target.value })}
                            >
                              <MenuItem value=""><em>None</em></MenuItem>
                              {videos.map((video) => (
                                <MenuItem key={video.id} value={video.id}>{video.name} ({video.category})</MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}

                        {selectedGroup.media_binding_type === 'photo' && (
                          <FormControl fullWidth sx={darkSelectSx}>
                            <InputLabel>Photo</InputLabel>
                            <Select
                              value={selectedGroup.photo_id || ''}
                              label="Photo"
                              onChange={(event) => updateGroup(selectedGroup.id, { photo_id: event.target.value })}
                            >
                              <MenuItem value=""><em>None</em></MenuItem>
                              {photos.map((photo) => (
                                <MenuItem key={photo.id} value={photo.id}>{photo.name} ({photo.category})</MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}

                        {selectedGroup.media_binding_type === 'media_directory' && (
                          <FormControl fullWidth sx={darkSelectSx}>
                            <InputLabel>Saved Media Folders</InputLabel>
                            <Select
                              multiple
                              value={
                                selectedGroup.media_directory_ids?.length
                                  ? selectedGroup.media_directory_ids
                                  : (selectedGroup.media_directory_id ? [selectedGroup.media_directory_id] : [])
                              }
                              label="Saved Media Folders"
                              onChange={(event) => {
                                const nextIds = typeof event.target.value === 'string'
                                  ? normalizeNumericIdList(event.target.value.split(','))
                                  : normalizeNumericIdList(event.target.value);
                                updateGroup(selectedGroup.id, {
                                  media_directory_ids: nextIds,
                                  media_directory_id: nextIds[0] || '',
                                });
                              }}
                              renderValue={(selected) => {
                                const selectedIds = Array.isArray(selected) ? selected : [];
                                const selectedNames = mediaDirectories
                                  .filter((directory) => selectedIds.includes(directory.id))
                                  .map((directory) => directory.name);
                                return selectedNames.length ? selectedNames.join(', ') : 'None';
                              }}
                            >
                              <MenuItem value={[]}>
                                <em>None</em>
                              </MenuItem>
                              {mediaDirectories.map((directory) => (
                                <MenuItem key={directory.id} value={directory.id}>
                                  {directory.name} ({directory.category})
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}

                        {selectedGroup.media_binding_type === 'media_list' && (
                          <FormControl fullWidth sx={darkSelectSx}>
                            <InputLabel>Media List</InputLabel>
                            <Select
                              value={selectedGroup.media_list_id || ''}
                              label="Media List"
                              onChange={(event) => updateGroup(selectedGroup.id, { media_list_id: event.target.value })}
                            >
                              <MenuItem value=""><em>None</em></MenuItem>
                              {mediaLists.map((list) => (
                                <MenuItem key={list.id} value={list.id}>{list.name}</MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}

                        {selectedGroup.media_binding_type === 'photo_list' && (
                          <FormControl fullWidth sx={darkSelectSx}>
                            <InputLabel>Photo List</InputLabel>
                            <Select
                              value={selectedGroup.photo_list_id || ''}
                              label="Photo List"
                              onChange={(event) => updateGroup(selectedGroup.id, { photo_list_id: event.target.value })}
                            >
                              <MenuItem value=""><em>None</em></MenuItem>
                              {photoLists.map((list) => (
                                <MenuItem key={list.id} value={list.id}>{list.name}</MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}

                        {['media_directory', 'media_list', 'photo_list'].includes(selectedGroup.media_binding_type) && (
                          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                            <FormControlLabel
                              control={(
                                <Switch
                                  checked={selectedGroup.auto_advance !== false}
                                  onChange={(event) => updateGroup(selectedGroup.id, { auto_advance: event.target.checked })}
                                />
                              )}
                              label="Auto-advance"
                            />
                            <FormControlLabel
                              control={(
                                <Switch
                                  checked={Boolean(selectedGroup.shuffle)}
                                  onChange={(event) => updateGroup(selectedGroup.id, { shuffle: event.target.checked })}
                                />
                              )}
                              label="Shuffle"
                            />
                          </Stack>
                        )}

                        {selectedGroup.media_binding_type === 'media_channel' && (
                          <FormControl fullWidth sx={darkSelectSx}>
                            <InputLabel>Media Channel</InputLabel>
                            <Select
                              value={selectedGroup.media_channel_id || ''}
                              label="Media Channel"
                              onChange={(event) => updateGroup(selectedGroup.id, { media_channel_id: event.target.value })}
                            >
                              <MenuItem value=""><em>None</em></MenuItem>
                              {mediaChannels.map((channel) => (
                                <MenuItem key={channel.id} value={channel.id}>{channel.name}</MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}

                        {selectedGroup.media_binding_type === 'direct_url' && (
                          <TextField
                            label="Direct URL"
                            value={selectedGroup.direct_url || ''}
                            onChange={(event) => updateGroup(selectedGroup.id, { direct_url: event.target.value })}
                            fullWidth
                            sx={darkFieldSx}
                          />
                        )}
                      </Stack>
                    </Collapse>
                  </Paper>

                  <Paper sx={panelPaperSx}>
                    <SectionHeader
                      title="Visual Logic"
                      collapsed={collapsedSections.visual}
                      onToggle={() => toggleSection('visual')}
                    />
                    <Collapse in={!collapsedSections.visual}>
                      <Stack spacing={2}>
                        <Stack direction="row" spacing={1}>
                          <TextField
                            label="Primary"
                            type="color"
                            value={selectedGroup.color_a || '#b56a2d'}
                            onChange={(event) => updateGroup(selectedGroup.id, { color_a: event.target.value })}
                            sx={{ width: 140 }}
                          />
                          <TextField
                            label="Secondary"
                            type="color"
                            value={selectedGroup.color_b || '#6a7f58'}
                            onChange={(event) => updateGroup(selectedGroup.id, { color_b: event.target.value })}
                            sx={{ width: 140 }}
                          />
                        </Stack>

                        <Box>
                          <Typography gutterBottom>Cover Scale</Typography>
                          <Slider
                            min={0.5}
                            max={2}
                            step={0.05}
                            value={selectedGroup.transform?.scale || 1}
                            onChange={(_, value) => updateGroup(selectedGroup.id, {
                              transform: { ...(selectedGroup.transform || {}), scale: value },
                            })}
                          />
                        </Box>

                        <Stack direction="row" spacing={1}>
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => updateGroup(selectedGroup.id, { mask_ids: (sceneDraft?.masks || []).map((mask) => mask.id) })}
                          >
                            All Masks
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => updateGroup(selectedGroup.id, { mask_ids: [] })}
                          >
                            Clear
                          </Button>
                        </Stack>
                      </Stack>
                    </Collapse>
                  </Paper>
                </Stack>
              ) : (
                <Paper sx={panelPaperSx}>
                  <Typography variant="body2" sx={{ color: PANEL_SUBTEXT }}>
                    Select a group to edit its masks and media behavior.
                  </Typography>
                </Paper>
              )}
            </Stack>
          </Drawer>
        )}
      </Box>

      {!uiHidden && (
        <Stack spacing={1} sx={{ mt: 2 }}>
          {message && <Alert onClose={() => setMessage('')} severity="success">{message}</Alert>}
          {error && <Alert onClose={() => setError('')} severity="error">{error}</Alert>}
        </Stack>
      )}
    </Box>
  );
}

export default Mappings;

const darkFieldSx = {
  '& .MuiInputBase-root': {
    bgcolor: PANEL_ALT_BG,
    color: PANEL_TEXT,
  },
  '& .MuiOutlinedInput-notchedOutline': {
    borderColor: PANEL_BORDER,
  },
  '& .MuiInputLabel-root': {
    color: PANEL_SUBTEXT,
  },
};

const darkSelectSx = {
  '& .MuiInputBase-root': {
    bgcolor: PANEL_ALT_BG,
    color: PANEL_TEXT,
  },
  '& .MuiOutlinedInput-notchedOutline': {
    borderColor: PANEL_BORDER,
  },
  '& .MuiInputLabel-root': {
    color: PANEL_SUBTEXT,
  },
};

const panelPaperSx = {
  p: 2,
  bgcolor: PANEL_ALT_BG,
  color: PANEL_TEXT,
  border: `1px solid ${PANEL_BORDER}`,
  boxShadow: 'none',
};

function SectionHeader({ title, collapsed, onToggle, action = null }) {
  return (
    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: collapsed ? 0 : 1 }}>
      <Button
        onClick={onToggle}
        color="inherit"
        sx={{ p: 0, minWidth: 0, justifyContent: 'flex-start', textTransform: 'none', fontSize: '1rem', fontWeight: 600 }}
        startIcon={collapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
      >
        {title}
      </Button>
      {action}
    </Stack>
  );
}

function renderStage(canvas, sceneDraft, maskImages, selectedGroupId, polygonDraft = null) {
  const width = sceneDraft.canvas_width || 1280;
  const height = sceneDraft.canvas_height || 720;
  canvas.width = width;
  canvas.height = height;

  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = sceneDraft.render_settings?.background || '#000000';
  ctx.fillRect(0, 0, width, height);

  const groups = [...(sceneDraft.groups || [])]
    .filter((group) => group.visible !== false && group.mask_ids?.length)
    .sort((a, b) => (a.z_index || 0) - (b.z_index || 0));

  groups.forEach((group) => {
    const images = group.mask_ids.map((maskId) => maskImages[maskId]).filter(Boolean);
    if (!images.length) return;

    const bounds = computeMaskBounds(images, width, height);
    const offscreen = document.createElement('canvas');
    offscreen.width = width;
    offscreen.height = height;
    const offscreenCtx = offscreen.getContext('2d');

    drawFallbackFill(offscreenCtx, group, bounds);
    applyLuminanceMasks(offscreenCtx, images, width, height);
    ctx.drawImage(offscreen, 0, 0);

    ctx.strokeStyle = group.color_a || '#b56a2d';
    ctx.lineWidth = selectedGroupId === group.id ? 3 : 1.5;
    ctx.setLineDash(selectedGroupId === group.id ? [10, 6] : [4, 4]);
    ctx.strokeRect(bounds.x, bounds.y, bounds.width, bounds.height);
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(255,255,255,0.92)';
    ctx.font = selectedGroupId === group.id ? 'bold 15px sans-serif' : '14px sans-serif';
    ctx.fillText(group.name, bounds.x + 8, Math.max(18, bounds.y + 18));
  });

  if (polygonDraft?.points?.length) {
    drawPolygonDraft(ctx, polygonDraft.points);
  }
}

function computeMaskBounds(maskImages, width, height) {
  let minX = width;
  let minY = height;
  let maxX = 0;
  let maxY = 0;

  maskImages.forEach((image) => {
    const offscreen = document.createElement('canvas');
    offscreen.width = width;
    offscreen.height = height;
    const ctx = offscreen.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(image, 0, 0, width, height);
    const { data } = ctx.getImageData(0, 0, width, height);

    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const idx = (y * width + x) * 4;
        const alpha = data[idx + 3];
        const lum = (data[idx] + data[idx + 1] + data[idx + 2]) / 3;
        if (alpha > 5 && lum > 127) {
          minX = Math.min(minX, x);
          minY = Math.min(minY, y);
          maxX = Math.max(maxX, x);
          maxY = Math.max(maxY, y);
        }
      }
    }
  });

  return {
    x: minX === width ? 0 : minX,
    y: minY === height ? 0 : minY,
    width: Math.max(1, maxX - minX + 1),
    height: Math.max(1, maxY - minY + 1),
  };
}

function drawFallbackFill(ctx, group, bounds) {
  const gradient = ctx.createLinearGradient(bounds.x, bounds.y, bounds.x + bounds.width, bounds.y + bounds.height);
  gradient.addColorStop(0, group.color_a || '#00bbf9');
  gradient.addColorStop(1, group.color_b || '#003049');
  ctx.fillStyle = gradient;
  ctx.fillRect(bounds.x, bounds.y, bounds.width, bounds.height);
}

function applyLuminanceMasks(ctx, maskImages, width, height) {
  const maskCanvas = document.createElement('canvas');
  maskCanvas.width = width;
  maskCanvas.height = height;
  const maskCtx = maskCanvas.getContext('2d', { willReadFrequently: true });
  const combinedImageData = maskCtx.createImageData(width, height);
  const combinedPixels = combinedImageData.data;

  maskImages.forEach((image) => {
    maskCtx.clearRect(0, 0, width, height);
    maskCtx.drawImage(image, 0, 0, width, height);
    const { data } = maskCtx.getImageData(0, 0, width, height);

    for (let i = 0; i < data.length; i += 4) {
      const alpha = data[i + 3];
      if (alpha <= 5) {
        continue;
      }

      const lum = (data[i] + data[i + 1] + data[i + 2]) / 3;
      if (lum > combinedPixels[i + 3]) {
        combinedPixels[i] = 255;
        combinedPixels[i + 1] = 255;
        combinedPixels[i + 2] = 255;
        combinedPixels[i + 3] = lum > 127 ? 255 : 0;
      }
    }
  });

  maskCtx.putImageData(combinedImageData, 0, 0);
  ctx.globalCompositeOperation = 'destination-in';
  ctx.drawImage(maskCanvas, 0, 0);
  ctx.globalCompositeOperation = 'source-over';
}

function drawPolygonDraft(ctx, points) {
  if (!points.length) {
    return;
  }

  ctx.save();
  ctx.strokeStyle = '#ffe082';
  ctx.fillStyle = 'rgba(255, 224, 130, 0.18)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  points.slice(1).forEach((point) => {
    ctx.lineTo(point.x, point.y);
  });
  if (points.length >= 3) {
    ctx.closePath();
    ctx.fill();
  }
  ctx.stroke();

  points.forEach((point, index) => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, index === 0 ? 6 : 4, 0, Math.PI * 2);
    ctx.fillStyle = index === 0 ? '#ffca28' : '#ffffff';
    ctx.fill();
  });
  ctx.restore();
}
