import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
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

import { mappingsApi, mediaLibraryApi, photoApi, photoListApi, videoApi } from '../services/api';

function normalizeNumericIdList(values) {
  return (Array.isArray(values) ? values : [])
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function createRowEdit(group = {}) {
  return {
    media_binding_type: group.media_binding_type || 'video',
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

function createGroupAssignments(hydratedScenes) {
  if (!hydratedScenes.length) {
    return {};
  }
  const canonical = hydratedScenes[0]._sortedGroups || [];
  const canonicalNames = canonical.map((group) => normalizeGroupName(group.name));

  return Object.fromEntries(hydratedScenes.map((scene, sceneIndex) => {
    const sortedGroups = scene._sortedGroups || [];
    if (sceneIndex === 0) {
      return [scene.id, sortedGroups.map((group) => [group.id])];
    }

    const remaining = [...sortedGroups];
    const orderedIds = [];
    canonicalNames.forEach((name) => {
      const matchIndex = remaining.findIndex((group) => normalizeGroupName(group.name) === name);
      if (matchIndex >= 0) {
        orderedIds.push([remaining[matchIndex].id]);
        remaining.splice(matchIndex, 1);
      } else {
        orderedIds.push([]);
      }
    });
    remaining.forEach((group) => orderedIds.push([group.id]));
    return [scene.id, orderedIds];
  }));
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

function SceneControl() {
  const [scenes, setScenes] = useState([]);
  const [selectedSceneIds, setSelectedSceneIds] = useState([]);
  const [selectedScenes, setSelectedScenes] = useState([]);
  const [videos, setVideos] = useState([]);
  const [photos, setPhotos] = useState([]);
  const [mediaLists, setMediaLists] = useState([]);
  const [photoLists, setPhotoLists] = useState([]);
  const [mediaChannels, setMediaChannels] = useState([]);
  const [mediaDirectories, setMediaDirectories] = useState([]);
  const [groupAssignments, setGroupAssignments] = useState({});
  const [rowEdits, setRowEdits] = useState({});
  const [dragState, setDragState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([
      mappingsApi.listScenes(),
      videoApi.getVideos(),
      photoApi.getPhotos(),
      mediaLibraryApi.listDirectories(),
      mediaLibraryApi.listMediaLists(),
      photoListApi.listPhotoLists(),
      mediaLibraryApi.listMediaChannels(),
    ]).then(([sceneRes, videoRes, photoRes, mediaDirectoryRes, mediaListRes, photoListRes, mediaChannelRes]) => {
      if (!active) {
        return;
      }
      const nextScenes = sceneRes.data || [];
      setScenes(nextScenes);
      setSelectedSceneIds(nextScenes.slice(0, 2).map((scene) => scene.id));
      setVideos(videoRes.data.videos || []);
      setPhotos(photoRes.data.photos || []);
      setMediaDirectories(mediaDirectoryRes.data || []);
      setMediaLists(mediaListRes.data || []);
      setPhotoLists(photoListRes.data || []);
      setMediaChannels(mediaChannelRes.data || []);
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
        const nextAssignments = createSmartGroupAssignments(hydratedScenes);
        setGroupAssignments(nextAssignments);
        setRowEdits((current) => {
          const next = {};
          const rowCount = Math.max(0, ...Object.values(nextAssignments).map((assignments) => assignments?.length || 0));
          for (let index = 0; index < rowCount; index += 1) {
            const seedGroup = hydratedScenes
              .flatMap((scene) => (nextAssignments[scene.id]?.[index] || []).map((groupId) => scene._groupsById?.[groupId]))
              .find(Boolean);
            next[index] = current[index] || createRowEdit(seedGroup);
          }
          return next;
        });
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
  }, [selectedSceneIds]);

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

  const persistAll = async () => {
    try {
      setSaving(true);
      setError('');
      setMessage('');
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
              media_binding_type: edit.media_binding_type,
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
      setSelectedScenes(refreshedScenes);
      setGroupAssignments((current) => current && Object.keys(current).length ? current : createSmartGroupAssignments(refreshedScenes));
      setMessage(`Saved ${selectedScenes.length} scenes.`);
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

  const autoAssignSimilar = () => {
    const nextAssignments = createSmartGroupAssignments(selectedScenes);
    setGroupAssignments(nextAssignments);
    setMessage('Auto-assigned groups by name first, then by size similarity.');
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Scene Control</Typography>
        <Typography variant="body2" color="text.secondary">
          Batch-edit existing groups across multiple scenes. Same-name groups auto-align first, then remaining groups are assigned by coverage-size similarity. Drag a group within its scene column to move it to a different rank or combine multiple groups into one row.
        </Typography>
      </Box>

      {error ? <Alert severity="error">{error}</Alert> : null}
      {message ? <Alert severity="success">{message}</Alert> : null}

      <Grid container spacing={2}>
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Scenes</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              Select the mapping scenes you want to align and batch-edit.
            </Typography>
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
                    <ListItemText primary={scene.name} secondary={`${scene.masks?.length || 0} masks • ${scene.groups?.length || 0} groups`} />
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
                          <Typography variant="h6">Rank {row.index + 1}</Typography>
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
                              <InputLabel>Media Binding</InputLabel>
                              <Select
                                value={edit.media_binding_type}
                                label="Media Binding"
                                onChange={(event) => updateRowEdit(row.index, { media_binding_type: event.target.value })}
                              >
                                <MenuItem value="video">Video</MenuItem>
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
