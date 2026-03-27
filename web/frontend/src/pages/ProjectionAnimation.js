import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import {
  Animation as AnimationIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';
import { projectionApi } from '../services/api';

const PREVIEW_BUNDLE_VERSION = '20260327-anim-2';

function ProjectionAnimation() {
  const [animations, setAnimations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [animationLists, setAnimationLists] = useState([]);
  const [listDraft, setListDraft] = useState({ id: '', name: '', animation_ids: [], auto_advance_seconds: 12 });

  useEffect(() => {
    let active = true;

    Promise.all([
      projectionApi.listAnimations(),
      projectionApi.listAnimationLists(),
    ]).then(([animationRes, animationListRes]) => {
      if (!active) {
        return;
      }
      setAnimations(animationRes.data?.animations || []);
      setAnimationLists(animationListRes.data?.animation_lists || []);
      setLoading(false);
    }).catch((err) => {
      console.error(err);
      if (!active) {
        return;
      }
      setError('Failed to load projection animations');
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, []);

  const copyAnimationId = async (animationId) => {
    try {
      await navigator.clipboard.writeText(animationId);
      setMessage(`Copied animation id: ${animationId}`);
    } catch (err) {
      console.error(err);
      setError('Failed to copy animation id');
    }
  };

  const resetListDraft = () => {
    setListDraft({ id: '', name: '', animation_ids: [], auto_advance_seconds: 12 });
  };

  const saveAnimationList = async () => {
    try {
      if (!listDraft.name.trim()) {
        setError('Animation list name is required');
        return;
      }
      if (!listDraft.animation_ids.length) {
        setError('Pick at least one animation');
        return;
      }
      const payload = {
        name: listDraft.name.trim(),
        animation_ids: listDraft.animation_ids,
        auto_advance_seconds: Number(listDraft.auto_advance_seconds) || 12,
      };
      const response = listDraft.id
        ? await projectionApi.updateAnimationList(listDraft.id, payload)
        : await projectionApi.createAnimationList(payload);
      const saved = response.data;
      setAnimationLists((current) => {
        const next = current.filter((item) => item.id !== saved.id);
        return [saved, ...next];
      });
      setMessage(`Saved animation list: ${saved.name}`);
      resetListDraft();
    } catch (err) {
      console.error(err);
      setError('Failed to save animation list');
    }
  };

  const editAnimationList = (animationList) => {
    setListDraft({
      id: animationList.id,
      name: animationList.name || '',
      animation_ids: animationList.animation_ids || [],
      auto_advance_seconds: animationList.auto_advance_seconds || 12,
    });
  };

  const deleteAnimationList = async (animationList) => {
    try {
      await projectionApi.deleteAnimationList(animationList.id);
      setAnimationLists((current) => current.filter((item) => item.id !== animationList.id));
      if (listDraft.id === animationList.id) {
        resetListDraft();
      }
      setMessage(`Deleted animation list: ${animationList.name}`);
    } catch (err) {
      console.error(err);
      setError('Failed to delete animation list');
    }
  };

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <Paper sx={{ p: 3 }}>
          <Typography variant="h4" gutterBottom>
            Projection Animation
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Projection animations are reusable visual sources. Use the library here for preview and selection, then bind
            them as media sources inside Mapping or Scene Control.
          </Typography>
        </Paper>
      </Grid>

      <Grid item xs={12}>
        <Alert severity="info">
          Removed from this page: mask upload, saved projection configurations, zone assignments, and unfinished CodePen
          import UI. This page is only the previewable animation library now.
        </Alert>
      </Grid>

      {error && (
        <Grid item xs={12}>
          <Alert severity="error" onClose={() => setError('')}>
            {error}
          </Alert>
        </Grid>
      )}

      {message && (
        <Grid item xs={12}>
          <Alert severity="success" onClose={() => setMessage('')}>
            {message}
          </Alert>
        </Grid>
      )}

      <Grid item xs={12}>
        <Card>
          <CardHeader
            title="Animation Library"
            avatar={<AnimationIcon />}
          />
          <CardContent>
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress />
              </Box>
            ) : (
              <Grid container spacing={2}>
                {animations.map((animation) => (
                  <Grid item xs={12} sm={6} md={4} key={animation.id}>
                    <Paper sx={{ p: 2, height: '100%' }}>
                      <Box
                        sx={{
                          width: '100%',
                          height: 180,
                          borderRadius: 1,
                          overflow: 'hidden',
                          background: '#000',
                          mb: 1.5,
                        }}
                      >
                        <iframe
                          title={`${animation.name} preview`}
                          src={`/backend-static/projection_animation_preview.html?animation=${encodeURIComponent(animation.id)}&v=${PREVIEW_BUNDLE_VERSION}`}
                          style={{ width: '100%', height: '100%', border: 0, display: 'block' }}
                        />
                      </Box>
                      <Typography variant="subtitle1" align="center">
                        {animation.thumbnail} {animation.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" align="center" sx={{ minHeight: 42 }}>
                        {animation.description}
                      </Typography>
                      <Stack direction="row" spacing={0.5} justifyContent="center" flexWrap="wrap" sx={{ mt: 1.5 }}>
                        {(animation.dataInputs || []).map((input) => (
                          <Chip key={input} label={input} size="small" sx={{ mt: 0.5 }} />
                        ))}
                      </Stack>
                      <Divider sx={{ my: 2 }} />
                      <Stack direction="row" spacing={1} justifyContent="space-between" alignItems="center">
                        <Typography variant="caption" color="text.secondary">
                          `{animation.id}`
                        </Typography>
                        <Button
                          size="small"
                          startIcon={<CopyIcon />}
                          onClick={() => copyAnimationId(animation.id)}
                        >
                          Copy ID
                        </Button>
                      </Stack>
                    </Paper>
                  </Grid>
                ))}
              </Grid>
            )}
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={5}>
        <Card>
          <CardHeader title="Animation Lists" />
          <CardContent>
            <Stack spacing={2}>
              <TextField
                label="List Name"
                value={listDraft.name}
                onChange={(event) => setListDraft((current) => ({ ...current, name: event.target.value }))}
                size="small"
                fullWidth
              />
              <FormControl fullWidth size="small">
                <InputLabel>Animations</InputLabel>
                <Select
                  multiple
                  label="Animations"
                  value={listDraft.animation_ids}
                  onChange={(event) => setListDraft((current) => ({ ...current, animation_ids: event.target.value }))}
                  renderValue={(selected) => selected.join(', ')}
                >
                  {animations.map((animation) => (
                    <MenuItem key={animation.id} value={animation.id}>
                      {animation.thumbnail} {animation.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                label="Auto Advance Seconds"
                type="number"
                size="small"
                value={listDraft.auto_advance_seconds}
                onChange={(event) => setListDraft((current) => ({ ...current, auto_advance_seconds: event.target.value }))}
                inputProps={{ min: 3, step: 1 }}
              />
              <Stack direction="row" spacing={1}>
                <Button variant="contained" onClick={saveAnimationList}>
                  {listDraft.id ? 'Update List' : 'Create List'}
                </Button>
                <Button variant="text" onClick={resetListDraft}>
                  Clear
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={7}>
        <Card>
          <CardHeader title="Saved Animation Lists" />
          <CardContent>
            <Stack spacing={1.5}>
              {animationLists.map((animationList) => (
                <Paper key={animationList.id} sx={{ p: 2 }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
                    <Box>
                      <Typography variant="subtitle1">{animationList.name}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {(animationList.animation_ids || []).join(', ')}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Advance every {animationList.auto_advance_seconds || 12}s
                      </Typography>
                    </Box>
                    <Stack direction="row" spacing={1}>
                      <Button size="small" onClick={() => editAnimationList(animationList)}>Edit</Button>
                      <Button size="small" color="error" onClick={() => deleteAnimationList(animationList)}>Delete</Button>
                    </Stack>
                  </Stack>
                </Paper>
              ))}
              {!animationLists.length && (
                <Typography variant="body2" color="text.secondary">
                  No animation lists yet.
                </Typography>
              )}
            </Stack>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}

export default ProjectionAnimation;
