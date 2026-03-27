import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  LinearProgress,
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

function getProjectorOptionId(projector) {
  return projector?.device_id || projector?.id || '';
}

function getProjectorOptionLabel(projector) {
  return projector?.name || projector?.friendly_name || getProjectorOptionId(projector);
}

function StructuredLighting() {
  const navigate = useNavigate();
  const [capabilities, setCapabilities] = useState(null);
  const [status, setStatus] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [plan, setPlan] = useState(null);
  const [runtime, setRuntime] = useState(null);
  const [captures, setCaptures] = useState(null);
  const [artifactReview, setArtifactReview] = useState(null);
  const [tuningSearch, setTuningSearch] = useState(null);
  const [projectors, setProjectors] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewedBy, setReviewedBy] = useState('');
  const [sessionView, setSessionView] = useState('active');
  const [sessionFilter, setSessionFilter] = useState('all');
  const [selectedSessionIds, setSelectedSessionIds] = useState([]);
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
  const [workerForm, setWorkerForm] = useState({
    base_url: 'http://localhost:8000',
    camera_index: 1,
    projector_screen_x: 1280,
    projector_screen_y: 0,
    projector_width: 1280,
    projector_height: 720,
  });
  const runtimeRefreshInFlightRef = useRef(false);

  const refreshSessions = useCallback(async () => {
    const sessionsRes = await structuredLightingApi.listSessions();
    const nextSessions = sessionsRes.data || [];
    setSessions(nextSessions);
    setSelectedSessionId((current) => current || nextSessions[0]?.session_id || '');
    return nextSessions;
  }, []);

  const refreshStatus = useCallback(async () => {
    const response = await structuredLightingApi.getStatus();
    setStatus(response.data);
  }, []);

  const syncSessionSnapshot = useCallback((nextSession) => {
    if (!nextSession?.session_id) {
      return;
    }

    setSessions((current) => {
      let found = false;
      const nextSessions = current.map((session) => {
        if (session.session_id !== nextSession.session_id) {
          return session;
        }
        found = true;
        return { ...session, ...nextSession };
      });
      return found ? nextSessions : current;
    });
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
        const nextProjectors = Array.isArray(projectorRes.data) ? projectorRes.data : [];
        setProjectors(nextProjectors);
        setForm((current) => {
          const currentProjectorId = current.projector_device_id || '';
          if (!currentProjectorId) {
            return current;
          }
          const stillExists = nextProjectors.some((projector) => getProjectorOptionId(projector) === currentProjectorId);
          return stillExists ? current : { ...current, projector_device_id: '' };
        });
        await refreshSessions();
        setError('');
        setMessage('');
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
    const loadSessionDetails = async () => {
      if (!selectedSessionId) {
        setPlan(null);
        setRuntime(null);
        setCaptures(null);
        setArtifactReview(null);
        setTuningSearch(null);
        setReviewNotes('');
        return;
      }
      try {
        const [planResponse, runtimeResponse, capturesResponse, reviewResponse, tuningSearchResponse] = await Promise.all([
          structuredLightingApi.getCapturePlan(selectedSessionId),
          structuredLightingApi.getRuntime(selectedSessionId),
          structuredLightingApi.listCaptures(selectedSessionId),
          structuredLightingApi.getArtifactReview(selectedSessionId),
          structuredLightingApi.getTuningSearch(selectedSessionId),
        ]);
        if (active) {
          setPlan(planResponse.data);
          setRuntime(runtimeResponse.data);
          setCaptures(capturesResponse.data);
          setArtifactReview(reviewResponse.data);
          setTuningSearch(tuningSearchResponse.data);
          syncSessionSnapshot(runtimeResponse.data?.session || planResponse.data?.session);
          setReviewNotes(reviewResponse.data?.review?.notes || '');
          setReviewedBy(reviewResponse.data?.review?.reviewed_by || '');
        }
      } catch (err) {
        console.error('Failed to load capture plan', err);
        if (active) {
          setPlan(null);
          setRuntime(null);
          setCaptures(null);
          setArtifactReview(null);
          setTuningSearch(null);
          setReviewNotes('');
          setReviewedBy('');
        }
      }
    };
    loadSessionDetails();
    return () => {
      active = false;
    };
  }, [selectedSessionId, syncSessionSnapshot]);

  const selectedSession = sessions.find((session) => session.session_id === selectedSessionId) || null;
  const selectedSessionStatus = runtime?.session?.status || selectedSession?.status || '';
  const decodeStatus = runtime?.session?.decode?.status || selectedSession?.decode?.status || '';
  const shouldPollRuntime = Boolean(selectedSessionId) && (
    ['waiting_for_worker', 'ready', 'capturing'].includes(selectedSessionStatus)
    || decodeStatus === 'running'
  );

  useEffect(() => {
    if (!selectedSessionId || !shouldPollRuntime) {
      return undefined;
    }

    let cancelled = false;
    let timeoutId = null;

    const pollRuntime = async () => {
      if (cancelled) {
        return;
      }
      if (runtimeRefreshInFlightRef.current) {
        timeoutId = window.setTimeout(pollRuntime, 3000);
        return;
      }

      runtimeRefreshInFlightRef.current = true;
      try {
        const [statusResponse, runtimeResponse, capturesResponse, reviewResponse, tuningSearchResponse] = await Promise.all([
          structuredLightingApi.getStatus(),
          structuredLightingApi.getRuntime(selectedSessionId),
          structuredLightingApi.listCaptures(selectedSessionId),
          structuredLightingApi.getArtifactReview(selectedSessionId),
          structuredLightingApi.getTuningSearch(selectedSessionId),
        ]);
        if (cancelled) {
          return;
        }
        setStatus(statusResponse.data);
        setRuntime(runtimeResponse.data);
        setCaptures(capturesResponse.data);
        setArtifactReview(reviewResponse.data);
        setTuningSearch(tuningSearchResponse.data);
        syncSessionSnapshot(runtimeResponse.data?.session);
        setReviewNotes((current) => current || reviewResponse.data?.review?.notes || '');
        setReviewedBy((current) => current || reviewResponse.data?.review?.reviewed_by || '');
      } catch (err) {
        console.error('Failed to refresh structured-lighting runtime', err);
      } finally {
        runtimeRefreshInFlightRef.current = false;
        if (!cancelled) {
          timeoutId = window.setTimeout(pollRuntime, 3000);
        }
      }
    };

    pollRuntime();
    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [selectedSessionId, shouldPollRuntime, syncSessionSnapshot]);

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
      setMessage('');
    } catch (err) {
      console.error('Failed to create structured lighting session', err);
      setError('Failed to create structured lighting session.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartWorker = async () => {
    try {
      setActionLoading(true);
      await structuredLightingApi.startWorker({
        ...workerForm,
        camera_index: Number(workerForm.camera_index),
        projector_screen_x: Number(workerForm.projector_screen_x),
        projector_screen_y: Number(workerForm.projector_screen_y),
        projector_width: Number(workerForm.projector_width),
        projector_height: Number(workerForm.projector_height),
      });
      await refreshStatus();
      setError('');
      setMessage('');
    } catch (err) {
      console.error('Failed to start structured lighting worker', err);
      setError('Failed to start structured lighting worker.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStopWorker = async () => {
    try {
      setActionLoading(true);
      await structuredLightingApi.stopWorker();
      await refreshStatus();
      setError('');
      setMessage('');
    } catch (err) {
      console.error('Failed to stop structured lighting worker', err);
      setError('Failed to stop structured lighting worker.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirmWorkerReady = async () => {
    try {
      if (!status?.worker?.worker_id) {
        return;
      }
      setActionLoading(true);
      await structuredLightingApi.confirmWorkerReady(status.worker.worker_id);
      await refreshStatus();
      setError('');
      setMessage('');
    } catch (err) {
      console.error('Failed to confirm structured lighting camera framing', err);
      setError('Failed to confirm structured lighting camera framing.');
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
      const [runtimeResponse, capturesResponse, reviewResponse, tuningSearchResponse] = await Promise.all([
        structuredLightingApi.getRuntime(sessionId),
        structuredLightingApi.listCaptures(sessionId),
        structuredLightingApi.getArtifactReview(sessionId),
        structuredLightingApi.getTuningSearch(sessionId),
      ]);
      setRuntime(runtimeResponse.data);
      setCaptures(capturesResponse.data);
      setArtifactReview(reviewResponse.data);
      setTuningSearch(tuningSearchResponse.data);
      setReviewNotes(reviewResponse.data?.review?.notes || '');
      setReviewedBy(reviewResponse.data?.review?.reviewed_by || '');
      setError('');
      setMessage('');
    } catch (err) {
      console.error('Failed to start structured lighting session', err);
      setError('Failed to start structured lighting session.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDecodeSession = async (sessionId, tuningParams = null) => {
    try {
      setActionLoading(true);
      setRuntime((current) => (
        current && current.session?.session_id === sessionId
          ? {
              ...current,
              session: {
                ...current.session,
                decode: {
                  ...(current.session.decode || {}),
                  status: 'running',
                  message: tuningParams ? 'Applying selected tuning candidate.' : 'Decoding graycode captures and generating repaired projector layers.',
                  progress: {
                    phase: 'initializing',
                    label: tuningParams ? 'Applying selected tuning candidate' : 'Preparing decode',
                    percent: 2,
                  },
                },
              },
            }
          : current
      ));
      await structuredLightingApi.decodeSession(sessionId, { sample_step: 1, tuning_params: tuningParams || undefined });
      const [runtimeResponse, capturesResponse, sessionsResponse, reviewResponse, tuningSearchResponse] = await Promise.all([
        structuredLightingApi.getRuntime(sessionId),
        structuredLightingApi.listCaptures(sessionId),
        structuredLightingApi.listSessions(),
        structuredLightingApi.getArtifactReview(sessionId),
        structuredLightingApi.getTuningSearch(sessionId),
      ]);
      setRuntime(runtimeResponse.data);
      setCaptures(capturesResponse.data);
      setSessions(sessionsResponse.data || []);
      setArtifactReview(reviewResponse.data);
      setTuningSearch(tuningSearchResponse.data);
      setReviewNotes(reviewResponse.data?.review?.notes || '');
      setReviewedBy(reviewResponse.data?.review?.reviewed_by || '');
      await refreshStatus();
      setError('');
      setMessage(tuningParams ? 'Decoded using selected tuning candidate.' : '');
    } catch (err) {
      console.error('Failed to decode structured lighting session', err);
      setError('Failed to decode structured lighting session.');
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
      if (selectedSessionId === sessionId && !remaining.length) {
        setArtifactReview(null);
        setReviewNotes('');
        setReviewedBy('');
      }
      setSelectedSessionIds((current) => current.filter((id) => id !== sessionId));
      setMessage('');
    } catch (err) {
      console.error('Failed to delete structured lighting session', err);
      setError('Failed to delete structured lighting session.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdateReview = async (sessionId, verdict) => {
    try {
      setActionLoading(true);
      const response = await structuredLightingApi.updateReview(sessionId, {
        verdict,
        notes: reviewNotes,
        reviewed_by: reviewedBy,
      });
      const updatedSession = response.data;
      setRuntime((current) => (current ? { ...current, session: updatedSession } : current));
      setArtifactReview((current) => (
        current ? { ...current, review: updatedSession.review } : current
      ));
      await refreshSessions();
      await refreshStatus();
      setError('');
      setMessage('');
    } catch (err) {
      console.error('Failed to update structured lighting review', err);
      setError('Failed to update structured lighting review.');
    } finally {
      setActionLoading(false);
    }
  };

  const handlePublishMappingScene = async (sessionId) => {
    try {
      setActionLoading(true);
      const response = await structuredLightingApi.publishMappingScene(sessionId, {});
      const published = response.data;
      setError('');
      setMessage(`Published ${published.mask_count} masks to Mapping scene "${published.scene_name}" (#${published.scene_id}).`);
      navigate(`/mappings?scene=${published.scene_id}`);
    } catch (err) {
      console.error('Failed to publish mapping scene', err);
      setError(err.response?.data?.detail || 'Failed to publish mapping scene.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRunTuningSearch = async (sessionId) => {
    try {
      setActionLoading(true);
      const response = await structuredLightingApi.runTuningSearch(sessionId, { sample_step: 1 });
      setTuningSearch(response.data);
      setError('');
      setMessage('Generated tuning candidates for operator review.');
    } catch (err) {
      console.error('Failed to run tuning search', err);
      setError(err.response?.data?.detail || 'Failed to run tuning search.');
    } finally {
      setActionLoading(false);
    }
  };

  const visibleSessions = sessions.filter((session) => {
    const reviewStatus = session.review?.status || 'pending';
    const isDeleted = session.status === 'deleted';
    if (sessionFilter === 'deleted') {
      return isDeleted;
    }
    if (isDeleted) {
      return false;
    }
    const inView = sessionView === 'archive' ? reviewStatus === 'accepted' : reviewStatus !== 'accepted';
    if (!inView) {
      return false;
    }
    if (sessionFilter === 'all') {
      return true;
    }
    return reviewStatus === sessionFilter;
  });

  const sessionCounts = sessions.reduce((counts, session) => {
    if (session.status === 'deleted') {
      counts.deleted = (counts.deleted || 0) + 1;
      return counts;
    }
    const reviewStatus = session.review?.status || 'pending';
    counts[reviewStatus] = (counts[reviewStatus] || 0) + 1;
    return counts;
  }, { pending: 0, needs_recapture: 0, accepted: 0, deleted: 0 });

  const selectedVisibleSessionIds = selectedSessionIds.filter((id) => (
    visibleSessions.some((session) => session.session_id === id)
  ));
  const allVisibleSelected = Boolean(visibleSessions.length) && selectedVisibleSessionIds.length === visibleSessions.length;
  const workerState = status?.worker?.state || 'unknown';
  const workerProcessState = status?.worker?.process_state || 'stopped';
  const workerCanConfirm = workerState === 'awaiting_operator' && Boolean(status?.worker?.worker_id);
  const workerCanStartSession = workerState === 'idle';

  useEffect(() => {
    if (!visibleSessions.length) {
      if (selectedSessionId) {
        setSelectedSessionId('');
      }
      return;
    }
    const selectedStillVisible = visibleSessions.some((session) => session.session_id === selectedSessionId);
    if (!selectedStillVisible) {
      setSelectedSessionId(visibleSessions[0].session_id);
    }
  }, [selectedSessionId, visibleSessions]);

  useEffect(() => {
    setSelectedSessionIds((current) => current.filter((id) => sessions.some((session) => session.session_id === id)));
  }, [sessions]);

  const toggleSessionSelection = (sessionId) => {
    setSelectedSessionIds((current) => (
      current.includes(sessionId)
        ? current.filter((id) => id !== sessionId)
        : [...current, sessionId]
    ));
  };

  const toggleVisibleSelections = () => {
    if (allVisibleSelected) {
      setSelectedSessionIds((current) => current.filter((id) => !selectedVisibleSessionIds.includes(id)));
      return;
    }
    setSelectedSessionIds((current) => {
      const next = new Set(current);
      visibleSessions.forEach((session) => next.add(session.session_id));
      return Array.from(next);
    });
  };

  const handleBulkReviewUpdate = async (verdict) => {
    if (!selectedSessionIds.length) {
      return;
    }
    try {
      setActionLoading(true);
      await Promise.all(
        selectedSessionIds.map((sessionId) => structuredLightingApi.updateReview(sessionId, {
          verdict,
          notes: reviewNotes,
          reviewed_by: reviewedBy,
        })),
      );
      const refreshed = await refreshSessions();
      await refreshStatus();
      setSelectedSessionIds([]);
      if (selectedSessionId && !refreshed.some((session) => session.session_id === selectedSessionId)) {
        setSelectedSessionId(refreshed[0]?.session_id || '');
      }
      setError('');
    } catch (err) {
      console.error('Failed to update selected structured-lighting reviews', err);
      setError('Failed to update selected structured-lighting reviews.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleBulkDelete = async () => {
    if (!selectedSessionIds.length) {
      return;
    }
    try {
      setActionLoading(true);
      await Promise.all(selectedSessionIds.map((sessionId) => structuredLightingApi.deleteSession(sessionId)));
      const remaining = await refreshSessions();
      await refreshStatus();
      setSelectedSessionIds([]);
      if (!remaining.some((session) => session.session_id === selectedSessionId)) {
        setSelectedSessionId(remaining[0]?.session_id || '');
      }
      if (!remaining.length) {
        setArtifactReview(null);
        setReviewNotes('');
        setReviewedBy('');
      }
      setError('');
    } catch (err) {
      console.error('Failed to delete selected structured-lighting sessions', err);
      setError('Failed to delete selected structured-lighting sessions.');
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
      {message ? <Alert severity="success">{message}</Alert> : null}

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
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>Worker Control</Typography>
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                Start the local host worker, verify the native camera preview, then confirm framing before capture.
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={3}>
                  <TextField
                    label="Backend URL"
                    value={workerForm.base_url}
                    onChange={(e) => setWorkerForm({ ...workerForm, base_url: e.target.value })}
                    fullWidth
                  />
                </Grid>
                <Grid item xs={6} md={2}>
                  <TextField
                    label="Camera Index"
                    type="number"
                    value={workerForm.camera_index}
                    onChange={(e) => setWorkerForm({ ...workerForm, camera_index: e.target.value })}
                    fullWidth
                  />
                </Grid>
                <Grid item xs={6} md={2}>
                  <TextField
                    label="Projector X"
                    type="number"
                    value={workerForm.projector_screen_x}
                    onChange={(e) => setWorkerForm({ ...workerForm, projector_screen_x: e.target.value })}
                    fullWidth
                  />
                </Grid>
                <Grid item xs={6} md={2}>
                  <TextField
                    label="Projector Y"
                    type="number"
                    value={workerForm.projector_screen_y}
                    onChange={(e) => setWorkerForm({ ...workerForm, projector_screen_y: e.target.value })}
                    fullWidth
                  />
                </Grid>
                <Grid item xs={6} md={1}>
                  <TextField
                    label="Width"
                    type="number"
                    value={workerForm.projector_width}
                    onChange={(e) => setWorkerForm({ ...workerForm, projector_width: e.target.value })}
                    fullWidth
                  />
                </Grid>
                <Grid item xs={6} md={2}>
                  <TextField
                    label="Height"
                    type="number"
                    value={workerForm.projector_height}
                    onChange={(e) => setWorkerForm({ ...workerForm, projector_height: e.target.value })}
                    fullWidth
                  />
                </Grid>
              </Grid>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                <Chip label={`worker ${workerState}`} size="small" />
                <Chip label={`process ${workerProcessState}`} size="small" variant="outlined" />
                {status?.worker?.process_pid ? (
                  <Chip label={`pid ${status.worker.process_pid}`} size="small" variant="outlined" />
                ) : null}
                {status?.worker?.camera_indices?.length ? (
                  <Chip label={`camera ${status.worker.camera_indices.join(', ')}`} size="small" variant="outlined" />
                ) : null}
              </Box>
              <Typography variant="body2" color="text.secondary">
                Camera Index selects the host capture device used by the worker.
              </Typography>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                <Button variant="contained" onClick={handleStartWorker} disabled={actionLoading || workerProcessState !== 'stopped'}>
                  Start Worker
                </Button>
                <Button variant="outlined" color="error" onClick={handleStopWorker} disabled={actionLoading || workerProcessState === 'stopped'}>
                  Stop Worker
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => setWorkerForm((current) => ({ ...current, camera_index: form.camera_index }))}
                  disabled={actionLoading}
                >
                  Use Session Camera
                </Button>
                <Button variant="contained" color="success" onClick={handleConfirmWorkerReady} disabled={actionLoading || !workerCanConfirm}>
                  Confirm Camera Ready
                </Button>
              </Stack>
              <Alert severity={workerCanConfirm ? 'warning' : workerCanStartSession ? 'success' : 'info'}>
                {status?.worker?.message || 'No worker status yet.'}
              </Alert>
              {status?.worker?.log_path ? (
                <Typography variant="body2" color="text.secondary">
                  Worker log: {status.worker.log_path}
                </Typography>
              ) : null}
            </Stack>
          </Paper>
        </Grid>

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
                value={form.projector_device_id || ''}
                onChange={(e) => setForm({ ...form, projector_device_id: e.target.value || '' })}
                fullWidth
              >
                <MenuItem value="">Unassigned</MenuItem>
                {projectors.map((projector) => (
                  <MenuItem key={getProjectorOptionId(projector)} value={getProjectorOptionId(projector)}>
                    {getProjectorOptionLabel(projector)}
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
            <Stack spacing={1.5} sx={{ mb: 1 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="h6">Sessions</Typography>
                <Chip
                  label={sessionView === 'archive' ? 'Archive View' : 'Active Queue'}
                  size="small"
                  color={sessionView === 'archive' ? 'success' : 'default'}
                />
              </Stack>
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant={sessionView === 'active' ? 'contained' : 'outlined'}
                  onClick={() => {
                    setSessionView('active');
                    setSessionFilter('all');
                  }}
                >
                  Active
                </Button>
                <Button
                  size="small"
                  variant={sessionView === 'archive' ? 'contained' : 'outlined'}
                  color="success"
                  onClick={() => {
                    setSessionView('archive');
                    setSessionFilter('all');
                  }}
                >
                  Archive
                </Button>
              </Stack>
              <TextField
                select
                size="small"
                label="Filter"
                value={sessionFilter}
                onChange={(event) => setSessionFilter(event.target.value)}
                sx={{ minWidth: 160 }}
              >
                <MenuItem value="all">All In View</MenuItem>
                <MenuItem value="pending">Pending Review</MenuItem>
                <MenuItem value="needs_recapture">Needs Recapture</MenuItem>
                <MenuItem value="accepted">Accepted</MenuItem>
                <MenuItem value="deleted">Deleted</MenuItem>
              </TextField>
              <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                <Chip
                  label={`Pending ${sessionCounts.pending}`}
                  color={sessionFilter === 'pending' ? 'warning' : 'default'}
                  clickable
                  onClick={() => setSessionFilter('pending')}
                />
                <Chip
                  label={`Recapture ${sessionCounts.needs_recapture}`}
                  color={sessionFilter === 'needs_recapture' ? 'error' : 'default'}
                  clickable
                  onClick={() => setSessionFilter('needs_recapture')}
                />
                <Chip
                  label={`Accepted ${sessionCounts.accepted}`}
                  color={sessionFilter === 'accepted' ? 'success' : 'default'}
                  clickable
                  onClick={() => {
                    setSessionView('archive');
                    setSessionFilter('accepted');
                  }}
                />
                <Chip
                  label={`Deleted ${sessionCounts.deleted}`}
                  color={sessionFilter === 'deleted' ? 'default' : 'default'}
                  clickable
                  onClick={() => setSessionFilter('deleted')}
                />
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ flexWrap: 'wrap' }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={toggleVisibleSelections}
                  disabled={!visibleSessions.length}
                >
                  {allVisibleSelected ? 'Clear Visible' : 'Select Visible'}
                </Button>
                <Chip label={`${selectedSessionIds.length} selected`} size="small" />
              </Stack>
              {selectedSessionIds.length ? (
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                  <Button
                    size="small"
                    variant="contained"
                    color="success"
                    disabled={actionLoading}
                    onClick={() => handleBulkReviewUpdate('accepted')}
                  >
                    Accept Selected
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    disabled={actionLoading}
                    onClick={() => handleBulkReviewUpdate('needs_recapture')}
                  >
                    Recapture Selected
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    disabled={actionLoading}
                    onClick={handleBulkDelete}
                  >
                    Delete Selected
                  </Button>
                </Stack>
              ) : null}
            </Stack>
            <Divider sx={{ mb: 1.5 }} />
            {!visibleSessions.length ? (
              <Typography variant="body2" color="text.secondary">
                {sessionView === 'archive'
                  ? 'No accepted sessions in the archive yet.'
                  : 'No active structured-lighting sessions in this filter.'}
              </Typography>
            ) : (
              <Stack spacing={1.5}>
                {visibleSessions.map((session) => (
                  <Card
                    key={session.session_id}
                    variant={selectedSessionId === session.session_id ? 'elevation' : 'outlined'}
                    sx={{ cursor: 'pointer' }}
                    onClick={() => setSelectedSessionId(session.session_id)}
                  >
                    <CardContent sx={{ '&:last-child': { pb: 2 } }}>
                      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                        <Stack direction="row" spacing={1} alignItems="flex-start">
                          <Checkbox
                            checked={selectedSessionIds.includes(session.session_id)}
                            onClick={(event) => event.stopPropagation()}
                            onChange={() => toggleSessionSelection(session.session_id)}
                            size="small"
                          />
                          <Box>
                            <Typography variant="subtitle1">{session.name}</Typography>
                            <Typography variant="body2" color="text.secondary">
                              Camera {session.camera_index} • {session.projector_width}x{session.projector_height}
                            </Typography>
                          </Box>
                        </Stack>
                        <Chip label={session.status} size="small" />
                      </Stack>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        {session.pattern_frame_count} frames • hold {session.hold_ms} ms
                      </Typography>
                      {session.decode ? (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                          decode {session.decode.status}
                        </Typography>
                      ) : null}
                      {session.calibration ? (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                          calibration {session.calibration.status}
                        </Typography>
                      ) : null}
                      {session.review ? (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                          review {session.review.status}
                        </Typography>
                      ) : null}
                      {session.review?.reviewed_by ? (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                          by {session.review.reviewed_by}
                        </Typography>
                      ) : null}
                      {session.review?.accepted_at ? (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                          accepted {new Date(session.review.accepted_at).toLocaleString()}
                        </Typography>
                      ) : null}
                      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={!workerCanStartSession}
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
                        <Button
                          size="small"
                          onClick={(event) => {
                            event.stopPropagation();
                            handleDecodeSession(session.session_id);
                          }}
                        >
                          Decode
                        </Button>
                        {session.review?.status === 'accepted' ? (
                          <Button
                            size="small"
                            component="a"
                            href={structuredLightingApi.getExportUrl(session.session_id)}
                            onClick={(event) => {
                              event.stopPropagation();
                            }}
                          >
                            Export
                          </Button>
                        ) : null}
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
                {runtime?.session?.decode ? (
                  <Alert severity={runtime.session.decode.status === 'completed' ? 'success' : runtime.session.decode.status === 'failed' ? 'error' : 'info'}>
                    Decode status: {runtime.session.decode.status}. {runtime.session.decode.message}
                  </Alert>
                ) : null}
                {runtime?.session?.decode?.status === 'running' ? (
                  <Box>
                    <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.75 }}>
                      <Typography variant="subtitle2">
                        {runtime.session.decode.progress?.label || 'Decode in progress'}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {runtime.session.decode.progress?.percent ?? 0}%
                      </Typography>
                    </Stack>
                    <LinearProgress
                      variant="determinate"
                      value={runtime.session.decode.progress?.percent ?? 0}
                      sx={{ height: 8, borderRadius: 999 }}
                    />
                  </Box>
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
                {captures ? (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Captures ({captures.captured_frames}/{captures.expected_frames})
                    </Typography>
                    {!captures.captures?.length ? (
                      <Typography variant="body2" color="text.secondary">
                        No captures uploaded yet.
                      </Typography>
                    ) : (
                      <List dense disablePadding>
                        {captures.captures.slice(0, 10).map((capture) => (
                          <ListItem key={capture.step_index} disableGutters>
                            <ListItemText
                              primary={`${capture.step_index + 1}. ${capture.filename}`}
                              secondary={capture.step_kind}
                            />
                          </ListItem>
                        ))}
                        {captures.captures.length > 10 ? (
                          <ListItem disableGutters>
                            <ListItemText primary={`... ${captures.captures.length - 10} more captures`} />
                          </ListItem>
                        ) : null}
                      </List>
                    )}
                  </Box>
                ) : null}
                {runtime?.session?.decode?.metrics && Object.keys(runtime.session.decode.metrics).length ? (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {Object.entries(runtime.session.decode.metrics).map(([key, value]) => (
                      <Chip key={key} label={`${key}: ${value}`} size="small" variant="outlined" />
                    ))}
                  </Box>
                ) : null}
                {runtime?.session?.decode?.artifacts && Object.keys(runtime.session.decode.artifacts).length ? (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Decode Artifacts</Typography>
                    <List dense disablePadding>
                      {Object.entries(runtime.session.decode.artifacts).map(([key, value]) => (
                        <ListItem key={key} disableGutters>
                          <ListItemText primary={key} secondary={value} />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                ) : null}
                {runtime?.session?.calibration ? (
                  <Alert severity={runtime.session.calibration.status === 'completed' ? 'success' : 'info'}>
                    Calibration status: {runtime.session.calibration.status}. {runtime.session.calibration.message}
                  </Alert>
                ) : null}
                {runtime?.session?.calibration?.summary && Object.keys(runtime.session.calibration.summary).length ? (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {Object.entries(runtime.session.calibration.summary).map(([key, value]) => (
                      <Chip key={key} label={`${key}: ${value}`} size="small" variant="outlined" color="success" />
                    ))}
                  </Box>
                ) : null}
                {runtime?.session?.calibration?.artifacts && Object.keys(runtime.session.calibration.artifacts).length ? (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Calibration Artifacts</Typography>
                    <List dense disablePadding>
                      {Object.entries(runtime.session.calibration.artifacts).map(([key, value]) => (
                        <ListItem key={key} disableGutters>
                          <ListItemText primary={key} secondary={value || 'not available'} />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                ) : null}
                {runtime?.session?.review?.status === 'accepted' ? (
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                    <Button
                      variant="contained"
                      onClick={() => handlePublishMappingScene(runtime.session.session_id)}
                      disabled={actionLoading}
                    >
                      Publish To Mapping
                    </Button>
                    <Button
                      variant="outlined"
                      component="a"
                      href={structuredLightingApi.getExportUrl(runtime.session.session_id)}
                    >
                      Export Session Bundle
                    </Button>
                  </Stack>
                ) : null}
                {runtime?.session?.status === 'completed' ? (
                  <Box>
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 1.5 }}>
                      <Button
                        variant="outlined"
                        onClick={() => handleRunTuningSearch(runtime.session.session_id)}
                        disabled={actionLoading}
                      >
                        Run Parameter Search
                      </Button>
                      {runtime?.session?.decode?.metrics?.tuning_params ? (
                        <Chip
                          label={`active tuning: threshold ${runtime.session.decode.metrics.tuning_params.segmentation_threshold}, blur ${runtime.session.decode.metrics.tuning_params.segmentation_blur}, contrast ${runtime.session.decode.metrics.tuning_params.contrast_threshold}, layer area ${runtime.session.decode.metrics.tuning_params.layer_min_area}`}
                          size="small"
                          variant="outlined"
                        />
                      ) : null}
                    </Stack>
                    {tuningSearch?.candidates?.length ? (
                      <Stack spacing={2}>
                        <Typography variant="subtitle2">
                          Parameter Search Results
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Compare candidate masks before choosing one to apply to the final decode.
                        </Typography>
                        <Grid container spacing={2}>
                          {tuningSearch.candidates.map((candidate) => (
                            <Grid item xs={12} lg={6} key={candidate.id}>
                              <Card variant="outlined">
                                <CardContent>
                                  <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={1} sx={{ mb: 1 }}>
                                    <Box>
                                      <Typography variant="subtitle2">{candidate.label}</Typography>
                                      <Typography variant="body2" color="text.secondary">
                                        {candidate.description}
                                      </Typography>
                                    </Box>
                                    <Button
                                      size="small"
                                      variant="contained"
                                      disabled={actionLoading}
                                      onClick={() => handleDecodeSession(runtime.session.session_id, candidate.params)}
                                    >
                                      Use This Candidate
                                    </Button>
                                  </Stack>
                                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
                                    <Chip label={`seg threshold ${candidate.params.segmentation_threshold}`} size="small" variant="outlined" />
                                    <Chip label={`seg blur ${candidate.params.segmentation_blur}`} size="small" variant="outlined" />
                                    <Chip label={`contrast ${candidate.params.contrast_threshold}`} size="small" variant="outlined" />
                                    <Chip label={`layer min area ${candidate.params.layer_min_area}`} size="small" variant="outlined" />
                                    <Chip label={`filtered layers ${candidate.metrics.filtered_layer_count}`} size="small" />
                                  </Box>
                                  <Grid container spacing={1}>
                                    <Grid item xs={12} md={6}>
                                      <Box
                                        component="img"
                                        src={structuredLightingApi.getTuningSearchPreviewUrl(runtime.session.session_id, candidate.id, 'warp')}
                                        alt={`${candidate.label} warp`}
                                        sx={{
                                          width: '100%',
                                          display: 'block',
                                          border: '1px solid rgba(0,0,0,0.16)',
                                          borderRadius: 1,
                                          bgcolor: '#000',
                                        }}
                                      />
                                    </Grid>
                                    <Grid item xs={12} md={6}>
                                      <Box
                                        component="img"
                                        src={structuredLightingApi.getTuningSearchPreviewUrl(runtime.session.session_id, candidate.id, 'mask')}
                                        alt={`${candidate.label} mask`}
                                        sx={{
                                          width: '100%',
                                          display: 'block',
                                          border: '1px solid rgba(0,0,0,0.16)',
                                          borderRadius: 1,
                                          bgcolor: '#000',
                                        }}
                                      />
                                    </Grid>
                                  </Grid>
                                </CardContent>
                              </Card>
                            </Grid>
                          ))}
                        </Grid>
                      </Stack>
                    ) : null}
                  </Box>
                ) : null}
                {artifactReview ? (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Artifact Review</Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
                      <Chip
                        label={`review ${artifactReview.review?.status || 'pending'}`}
                        size="small"
                        color={
                          artifactReview.review?.status === 'accepted'
                            ? 'success'
                            : artifactReview.review?.status === 'needs_recapture'
                              ? 'error'
                              : 'default'
                        }
                      />
                      <Chip
                        label={`coverage ${artifactReview.coverage_status}`}
                        size="small"
                        color={
                          artifactReview.coverage_status === 'good'
                            ? 'success'
                            : artifactReview.coverage_status === 'poor'
                              ? 'error'
                              : 'warning'
                        }
                      />
                      {artifactReview.metrics?.coverage_ratio !== undefined ? (
                        <Chip label={`coverage ratio: ${artifactReview.metrics.coverage_ratio}`} size="small" variant="outlined" />
                      ) : null}
                      {artifactReview.metrics?.white_black_mean_delta !== undefined ? (
                        <Chip label={`white-black delta: ${artifactReview.metrics.white_black_mean_delta}`} size="small" variant="outlined" />
                      ) : null}
                    </Box>
                    {!artifactReview.previews?.length ? (
                      <Typography variant="body2" color="text.secondary">
                        Run decode to generate review previews for coverage and correspondence quality.
                      </Typography>
                    ) : (
                      <Stack spacing={2}>
                        <Alert severity={artifactReview.review?.status === 'needs_recapture' ? 'error' : 'info'}>
                          {artifactReview.review?.message || 'Review the artifacts and set a verdict before export.'}
                        </Alert>
                        {artifactReview.review?.accepted_at ? (
                          <Typography variant="body2" color="text.secondary">
                            Accepted at {new Date(artifactReview.review.accepted_at).toLocaleString()}
                          </Typography>
                        ) : null}
                        <TextField
                          label="Reviewed By"
                          value={reviewedBy}
                          onChange={(event) => setReviewedBy(event.target.value)}
                          fullWidth
                          placeholder="Operator name or host identifier"
                        />
                        <TextField
                          label="Review Notes"
                          value={reviewNotes}
                          onChange={(event) => setReviewNotes(event.target.value)}
                          fullWidth
                          multiline
                          minRows={2}
                          placeholder="Record why this scan is acceptable or why it needs recapture."
                        />
                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                          <Button
                            variant="contained"
                            color="success"
                            disabled={actionLoading || runtime?.session?.decode?.status !== 'completed'}
                            onClick={() => handleUpdateReview(runtime.session.session_id, 'accepted')}
                          >
                            Accept Session
                          </Button>
                          <Button
                            variant="outlined"
                            color="error"
                            disabled={actionLoading || runtime?.session?.decode?.status !== 'completed'}
                            onClick={() => handleUpdateReview(runtime.session.session_id, 'needs_recapture')}
                          >
                            Mark For Recapture
                          </Button>
                        </Stack>
                        <Grid container spacing={2}>
                          {artifactReview.previews.map((preview) => (
                            <Grid item xs={12} md={4} key={preview.id}>
                              <Card variant="outlined">
                                <CardContent>
                                  <Typography variant="subtitle2" gutterBottom>{preview.label}</Typography>
                                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                                    {preview.description}
                                  </Typography>
                                  <Box
                                    component="img"
                                    src={structuredLightingApi.getArtifactPreviewUrl(runtime.session.session_id, preview.id)}
                                    alt={preview.label}
                                    sx={{
                                      width: '100%',
                                      display: 'block',
                                      border: '1px solid rgba(0,0,0,0.16)',
                                      borderRadius: 1,
                                      bgcolor: '#000',
                                    }}
                                  />
                                </CardContent>
                              </Card>
                            </Grid>
                          ))}
                        </Grid>
                      </Stack>
                    )}
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
