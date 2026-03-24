import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { structuredLightingApi, discoveryV2Api } from '../services/api';

function SummaryCard({ title, value, subtitle }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="overline" color="text.secondary">{title}</Typography>
        <Typography variant="h4" sx={{ lineHeight: 1.2 }}>{value}</Typography>
        {subtitle ? <Typography variant="body2" color="text.secondary">{subtitle}</Typography> : null}
      </CardContent>
    </Card>
  );
}

function StructuredLighting() {
  const [capabilities, setCapabilities] = useState(null);
  const [status, setStatus] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [plan, setPlan] = useState(null);
  const [runtime, setRuntime] = useState(null);
  const [projectors, setProjectors] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    name: 'Wall Calibration',
    projector_device_id: '',
    camera_index: 1,
    projector_width: 1280,
    projector_height: 720,
    presentation_mode: 'dlna_step',
    hold_ms: 1200,
    notes: '',
  });

  const refreshSessions = useCallback(async () => {
    const sessionsRes = await structuredLightingApi.listSessions();
    const nextSessions = sessionsRes.data || [];
    setSessions(nextSessions);
    if (!selectedSessionId && nextSessions.length > 0) {
      setSelectedSessionId(nextSessions[0].session_id);
    }
    return nextSessions;
  }, [selectedSessionId]);

  const refreshStatus = useCallback(async () => {
    const response = await structuredLightingApi.getStatus();
    setStatus(response.data);
  }, []);

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        setLoading(true);
        const [capabilitiesRes, statusRes, projectorRes] = await Promise.all([
          structuredLightingApi.getCapabilities(),
          structuredLightingApi.getStatus(),
          discoveryV2Api.getDevices({ casting_method: 'dlna' }),
        ]);
        if (!active) {
          return;
        }
        setCapabilities(capabilitiesRes.data);
        setStatus(statusRes.data);
        setProjectors(projectorRes.data || []);
        await refreshSessions();
        setError('');
      } catch (err) {
        console.error('Failed to load structured lighting module', err);
        if (active) {
          setError('Failed to load structured lighting module.');
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      active = false;
    };
  }, [refreshSessions]);

  useEffect(() => {
    let active = true;
    const loadPlan = async () => {
      if (!selectedSessionId) {
        setPlan(null);
        setRuntime(null);
        return;
      }
      try {
        const [planResponse, runtimeResponse] = await Promise.all([
          structuredLightingApi.getCapturePlan(selectedSessionId),
          structuredLightingApi.getRuntime(selectedSessionId),
        ]);
        if (active) {
          setPlan(planResponse.data);
          setRuntime(runtimeResponse.data);
        }
      } catch (err) {
        console.error('Failed to load capture plan', err);
        if (active) {
          setPlan(null);
          setRuntime(null);
        }
      }
    };
    loadPlan();
    return () => {
      active = false;
    };
  }, [selectedSessionId]);

  const handleCreateSession = async () => {
    try {
      setActionLoading(true);
      const response = await structuredLightingApi.createSession({
        ...form,
        camera_index: Number(form.camera_index),
        projector_width: Number(form.projector_width),
        projector_height: Number(form.projector_height),
        hold_ms: Number(form.hold_ms),
        projector_device_id: form.projector_device_id || null,
      });
      const created = response.data;
      await refreshSessions();
      await refreshStatus();
      setSelectedSessionId(created.session_id);
      setError('');
    } catch (err) {
      console.error('Failed to create structured lighting session', err);
      setError('Failed to create structured lighting session.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartSession = async (sessionId) => {
    try {
      setActionLoading(true);
      await structuredLightingApi.startSession(sessionId);
      await refreshSessions();
      await refreshStatus();
      const runtimeResponse = await structuredLightingApi.getRuntime(sessionId);
      setRuntime(runtimeResponse.data);
      setError('');
    } catch (err) {
      console.error('Failed to start structured lighting session', err);
      setError('Failed to start structured lighting session.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteSession = async (sessionId) => {
    try {
      setActionLoading(true);
      await structuredLightingApi.deleteSession(sessionId);
      const remaining = await refreshSessions();
      await refreshStatus();
      if (selectedSessionId === sessionId) {
        setSelectedSessionId(remaining[0]?.session_id || '');
      }
    } catch (err) {
      console.error('Failed to delete structured lighting session', err);
      setError('Failed to delete structured lighting session.');
    } finally {
      setActionLoading(false);
    }
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
        <Typography variant="h4">Structured Lighting</Typography>
        <Typography variant="body2" color="text.secondary">
          Graycode calibration planning for the DLNA step-by-step capture workflow.
        </Typography>
      </Box>

      {error ? <Alert severity="error">{error}</Alert> : null}

      <Grid container spacing={2}>
        <Grid item xs={12} md={3}>
          <SummaryCard
            title="Worker"
            value={status?.worker?.state || 'unknown'}
            subtitle={status?.worker?.message || 'No worker status'}
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <SummaryCard
            title="Sessions"
            value={status?.summary?.total_sessions || 0}
            subtitle={`${status?.summary?.active_sessions || 0} active`}
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <SummaryCard
            title="Planned Frames"
            value={status?.summary?.total_planned_frames || 0}
            subtitle="across all sessions"
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <SummaryCard
            title="Estimated Time"
            value={`${status?.summary?.total_estimated_capture_seconds || 0}s`}
            subtitle="planned capture time"
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>New Session</Typography>
            <Stack spacing={2}>
              <TextField
                label="Session Name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                fullWidth
              />
              <TextField
                select
                label="Projector"
                value={form.projector_device_id}
                onChange={(e) => setForm({ ...form, projector_device_id: e.target.value })}
                fullWidth
              >
                <MenuItem value="">Unassigned</MenuItem>
                {projectors.map((projector) => (
                  <MenuItem key={projector.device_id} value={projector.device_id}>
                    {projector.name || projector.device_id}
                  </MenuItem>
                ))}
              </TextField>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <TextField
                    label="Camera Index"
                    type="number"
                    value={form.camera_index}
                    onChange={(e) => setForm({ ...form, camera_index: e.target.value })}
                    fullWidth
                  />
                </Grid>
                <Grid item xs={6}>
                  <TextField
                    label="Hold (ms)"
                    type="number"
                    value={form.hold_ms}
                    onChange={(e) => setForm({ ...form, hold_ms: e.target.value })}
                    fullWidth
                  />
                </Grid>
              </Grid>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <TextField
                    label="Projector Width"
                    type="number"
                    value={form.projector_width}
                    onChange={(e) => setForm({ ...form, projector_width: e.target.value })}
                    fullWidth
                  />
                </Grid>
                <Grid item xs={6}>
                  <TextField
                    label="Projector Height"
                    type="number"
                    value={form.projector_height}
                    onChange={(e) => setForm({ ...form, projector_height: e.target.value })}
                    fullWidth
                  />
                </Grid>
              </Grid>
              <TextField
                select
                label="Presentation Mode"
                value={form.presentation_mode}
                onChange={(e) => setForm({ ...form, presentation_mode: e.target.value })}
                fullWidth
              >
                {(capabilities?.presentation_modes || []).map((mode) => (
                  <MenuItem key={mode.id} value={mode.id}>
                    {mode.label}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                label="Notes"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                fullWidth
                multiline
                minRows={3}
              />
              <Button variant="contained" onClick={handleCreateSession} disabled={actionLoading}>
                {actionLoading ? 'Creating...' : 'Create Session'}
              </Button>
            </Stack>
          </Paper>
        </Grid>

        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Workflow</Typography>
            <Divider sx={{ mb: 1.5 }} />
            <List dense disablePadding>
              {(capabilities?.workflow || []).map((step) => (
                <ListItem key={step} disableGutters>
                  <ListItemText primary={step} />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Sessions</Typography>
            <Divider sx={{ mb: 1.5 }} />
            {!sessions.length ? (
              <Typography variant="body2" color="text.secondary">No structured-lighting sessions yet.</Typography>
            ) : (
              <Stack spacing={1.5}>
                {sessions.map((session) => (
                  <Card
                    key={session.session_id}
                    variant={selectedSessionId === session.session_id ? 'elevation' : 'outlined'}
                    sx={{ cursor: 'pointer' }}
                    onClick={() => setSelectedSessionId(session.session_id)}
                  >
                    <CardContent sx={{ '&:last-child': { pb: 2 } }}>
                      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                        <Box>
                          <Typography variant="subtitle1">{session.name}</Typography>
                          <Typography variant="body2" color="text.secondary">
                            Camera {session.camera_index} • {session.projector_width}x{session.projector_height}
                          </Typography>
                        </Box>
                        <Chip label={session.status} size="small" />
                      </Stack>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        {session.pattern_frame_count} frames • hold {session.hold_ms} ms
                      </Typography>
                      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={(event) => {
                            event.stopPropagation();
                            handleStartSession(session.session_id);
                          }}
                        >
                          Start
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          onClick={(event) => {
                            event.stopPropagation();
                            handleDeleteSession(session.session_id);
                          }}
                        >
                          Delete
                        </Button>
                      </Stack>
                    </CardContent>
                  </Card>
                ))}
              </Stack>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Capture Plan</Typography>
            <Divider sx={{ mb: 1.5 }} />
            {!plan ? (
              <Typography variant="body2" color="text.secondary">Select a session to inspect its graycode plan.</Typography>
            ) : (
              <Stack spacing={2}>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  <Chip label={`${plan.summary.total_frames} total frames`} size="small" />
                  <Chip label={`${plan.summary.graycode_frames} graycode frames`} size="small" />
                  <Chip label={`${plan.summary.reference_frames} reference frames`} size="small" />
                  <Chip label={`~${plan.summary.estimated_capture_seconds}s capture time`} size="small" />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Presentation mode: {plan.session.presentation_mode}. This plan assumes each pattern is cast to the projector, the camera captures after the image settles, and only then does the workflow advance.
                </Typography>
                <Alert severity="info">
                  Host worker state: {status?.worker?.state || 'unknown'}. {status?.worker?.message || 'No worker status yet.'}
                </Alert>
                {runtime ? (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    <Chip label={`session ${runtime.session.status}`} size="small" color={runtime.session.status === 'completed' ? 'success' : 'default'} />
                    <Chip label={`${runtime.progress.captured_frames} captured`} size="small" />
                    <Chip label={`${runtime.progress.remaining_frames} remaining`} size="small" />
                    <Chip label={`step ${runtime.progress.current_step_index + 1}`} size="small" />
                  </Box>
                ) : null}
                {runtime?.current_step ? (
                  <Alert severity="warning">
                    Current step: {runtime.current_step.index + 1}. {runtime.current_step.label}
                  </Alert>
                ) : null}
                {runtime?.current_step ? (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Current Pattern Preview</Typography>
                    <Box
                      component="img"
                      src={structuredLightingApi.getStepImageUrl(runtime.session.session_id, runtime.current_step.index)}
                      alt={runtime.current_step.label}
                      sx={{
                        width: '100%',
                        maxWidth: 320,
                        display: 'block',
                        border: '1px solid rgba(0,0,0,0.16)',
                        borderRadius: 1,
                        bgcolor: '#000',
                      }}
                    />
                  </Box>
                ) : null}
                <List dense disablePadding>
                  {plan.steps.slice(0, 18).map((step) => (
                    <ListItem key={`${step.index}-${step.label}`} disableGutters>
                      <ListItemText
                        primary={`${step.index + 1}. ${step.label}`}
                        secondary={`hold ${step.hold_ms} ms${step.capture_required ? ' • capture required' : ''}`}
                      />
                    </ListItem>
                  ))}
                  {plan.steps.length > 18 ? (
                    <ListItem disableGutters>
                      <ListItemText primary={`... ${plan.steps.length - 18} more frames`} />
                    </ListItem>
                  ) : null}
                </List>
              </Stack>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Stack>
  );
}

export default StructuredLighting;
