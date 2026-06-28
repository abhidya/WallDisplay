import React, { useEffect, useState } from 'react';
import {
  Alert,
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
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import PageHeader from '../components/PageHeader';
import StatusPanel from '../components/StatusPanel';
import { overlayApi, streamingApi } from '../services/api';

function renderCountMap(data) {
  return Object.entries(data || {}).sort((a, b) => b[1] - a[1]);
}

function MetricCard({ title, value, subtitle }) {
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

function BreakdownList({ title, items, emptyLabel = 'No data' }) {
  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Typography variant="h6" gutterBottom>{title}</Typography>
      <Divider sx={{ mb: 1.5 }} />
      {!items.length ? (
        <Typography variant="body2" color="text.secondary">{emptyLabel}</Typography>
      ) : (
        <List dense disablePadding>
          {items.map(([label, value]) => (
            <ListItem key={label} disableGutters secondaryAction={<Chip label={value} size="small" />}>
              <ListItemText primary={label} />
            </ListItem>
          ))}
        </List>
      )}
    </Paper>
  );
}

function StreamingDiagnostics() {
  const [stats, setStats] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [health, setHealth] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [overlaySessions, setOverlaySessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sessionActionError, setSessionActionError] = useState('');
  const [stoppingSessionId, setStoppingSessionId] = useState('');
  const [resettingSessionId, setResettingSessionId] = useState('');

  useEffect(() => {
    let active = true;

    const fetchData = async (isPolling = false) => {
      try {
        if (!isPolling) {
          setLoading(true);
        }

        const [statsRes, analyticsRes, healthRes, sessionsRes, overlaySessionsRes] = await Promise.all([
          streamingApi.getStreamingStats(),
          streamingApi.getStreamingAnalytics(),
          streamingApi.getStreamingHealth(),
          streamingApi.getSessions(),
          overlayApi.listCastSessions(),
        ]);

        if (!active) {
          return;
        }

        setStats(statsRes.data);
        setAnalytics(analyticsRes.data);
        setHealth(healthRes.data);
        setSessions(sessionsRes.data || []);
        setOverlaySessions((overlaySessionsRes.data || []).filter((session) => !session.archived));
        setError('');
        setLoading(false);
      } catch (err) {
        console.error('Failed to load streaming diagnostics', err);
        if (!active) {
          return;
        }
        setError('Failed to load streaming diagnostics.');
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(() => fetchData(true), 15000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const refreshData = async () => {
    const [statsRes, analyticsRes, healthRes, sessionsRes, overlaySessionsRes] = await Promise.all([
      streamingApi.getStreamingStats(),
      streamingApi.getStreamingAnalytics(),
      streamingApi.getStreamingHealth(),
      streamingApi.getSessions(),
      overlayApi.listCastSessions(),
    ]);

    setStats(statsRes.data);
    setAnalytics(analyticsRes.data);
    setHealth(healthRes.data);
    setSessions(sessionsRes.data || []);
    setOverlaySessions((overlaySessionsRes.data || []).filter((session) => !session.archived));
  };

  const handleTerminateSession = async (sessionId) => {
    try {
      setStoppingSessionId(sessionId);
      setSessionActionError('');
      await streamingApi.deleteSession(sessionId);
      await refreshData();
    } catch (err) {
      console.error('Failed to terminate streaming session', err);
      setSessionActionError('Failed to terminate streaming session.');
    } finally {
      setStoppingSessionId('');
    }
  };

  const handleResetSession = async (sessionId) => {
    try {
      setResettingSessionId(sessionId);
      setSessionActionError('');
      await streamingApi.resetSession(sessionId);
      await refreshData();
    } catch (err) {
      console.error('Failed to reset streaming session', err);
      setSessionActionError('Failed to reset streaming session.');
    } finally {
      setResettingSessionId('');
    }
  };

  if (loading && !stats) {
    return (
      <StatusPanel
        icon={<CircularProgress size={24} />}
        title="Loading Streaming Diagnostics"
        description="Checking stream ownership, session health, and overlay relay state."
      />
    );
  }

  const statsByType = renderCountMap(stats?.sessions_by_stream_type);
  const consumerBreakdown = renderCountMap(stats?.sessions_by_consumer_prefix);
  const activeByType = renderCountMap(analytics?.active_sessions_by_stream_type);
  const activeByConsumer = renderCountMap(analytics?.active_sessions_by_consumer_prefix);
  const stalledByType = renderCountMap(health?.stalled_by_stream_type);
  const errorByType = renderCountMap(health?.error_by_stream_type);
  const runningOverlaySessions = overlaySessions.filter((session) => session.status === 'running');

  return (
    <Stack spacing={3}>
      <PageHeader
        title="Streaming Diagnostics"
        subtitle="Ownership and health view for device streams, projection streams, and overlay mapping streams."
        meta={(
          <>
            <Chip label={`health ${health?.status || 'unknown'}`} color={health?.status === 'healthy' ? 'success' : 'default'} />
            <Chip label={`${stats?.active_sessions || 0} active`} variant="outlined" />
            <Chip label={`${runningOverlaySessions.length} overlay running`} variant="outlined" />
          </>
        )}
      />

      {error ? <Alert severity="error">{error}</Alert> : null}
      {sessionActionError ? <Alert severity="error">{sessionActionError}</Alert> : null}

      <Grid container spacing={2}>
        <Grid item xs={12} md={3}>
          <MetricCard title="Health" value={health?.status || 'unknown'} subtitle={`score ${Math.round(health?.health_score || 0)}`} />
        </Grid>
        <Grid item xs={12} md={3}>
          <MetricCard title="Active Sessions" value={stats?.active_sessions || 0} subtitle={`${stats?.total_sessions || 0} total`} />
        </Grid>
        <Grid item xs={12} md={3}>
          <MetricCard title="Stalled Sessions" value={health?.stalled_sessions || 0} subtitle={`${health?.error_sessions || 0} with errors`} />
        </Grid>
        <Grid item xs={12} md={3}>
          <MetricCard
            title="Bandwidth"
            value={`${Math.round((analytics?.total_bandwidth_bps || 0) / 1024)} KB/s`}
            subtitle={`${sessions.length} live session records`}
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={3}>
          <MetricCard
            title="Overlay Cast Sessions"
            value={overlaySessions.length}
            subtitle={`${runningOverlaySessions.length} running`}
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <MetricCard
            title="Overlay Clients"
            value={overlaySessions.reduce((total, session) => total + (session.active_clients || 0), 0)}
            subtitle="relay consumers"
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <MetricCard
            title="Avg Overlay Speed"
            value={runningOverlaySessions.length
              ? `${(runningOverlaySessions.reduce((total, session) => total + (session.ffmpeg_speed || 0), 0) / runningOverlaySessions.length).toFixed(2)}x`
              : 'n/a'}
            subtitle="ffmpeg realtime factor"
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <MetricCard
            title="Slow Overlay Casts"
            value={runningOverlaySessions.filter((session) => (session.ffmpeg_speed || 0) < 1).length}
            subtitle="below realtime"
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <BreakdownList title="Sessions By Stream Type" items={statsByType} />
        </Grid>
        <Grid item xs={12} md={4}>
          <BreakdownList title="Sessions By Owner Prefix" items={consumerBreakdown} />
        </Grid>
        <Grid item xs={12} md={4}>
          <BreakdownList title="Active Sessions By Type" items={activeByType} />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <BreakdownList title="Active Sessions By Owner" items={activeByConsumer} />
        </Grid>
        <Grid item xs={12} md={4}>
          <BreakdownList title="Stalled By Type" items={stalledByType} />
        </Grid>
        <Grid item xs={12} md={4}>
          <BreakdownList title="Error Sessions By Type" items={errorByType} />
        </Grid>
      </Grid>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>Recent Active Sessions</Typography>
        <Divider sx={{ mb: 1.5 }} />
        {!sessions.length ? (
          <Typography variant="body2" color="text.secondary">No active streaming sessions.</Typography>
        ) : (
          <List dense disablePadding>
            {sessions.slice(0, 12).map((session) => (
              <ListItem
                key={session.session_id}
                disableGutters
                secondaryAction={
                  <Stack direction="row" spacing={1}>
                    <Chip label={session.stream_type || 'unknown'} size="small" />
                    <Chip label={session.status || 'unknown'} size="small" color={session.status === 'active' ? 'success' : 'default'} />
                    <Button
                      size="small"
                      color="info"
                      variant="outlined"
                      disabled={resettingSessionId === session.session_id}
                      onClick={() => handleResetSession(session.session_id)}
                    >
                      {resettingSessionId === session.session_id ? 'Resetting...' : 'Reset'}
                    </Button>
                    <Button
                      size="small"
                      color="warning"
                      variant="outlined"
                      disabled={stoppingSessionId === session.session_id || resettingSessionId === session.session_id}
                      onClick={() => handleTerminateSession(session.session_id)}
                    >
                      {stoppingSessionId === session.session_id ? 'Stopping...' : 'Terminate'}
                    </Button>
                  </Stack>
                }
              >
                <ListItemText
                  primary={`${session.device_name} • ${session.consumer_id || 'unassigned'}`}
                  secondary={`${session.server_ip}:${session.server_port} • ${Math.round((session.bandwidth_bps || 0) / 1024)} KB/s`}
                />
              </ListItem>
            ))}
          </List>
        )}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>Overlay Capture Sessions</Typography>
        <Divider sx={{ mb: 1.5 }} />
        {!overlaySessions.length ? (
          <Typography variant="body2" color="text.secondary">No overlay capture sessions.</Typography>
        ) : (
          <List dense disablePadding>
            {overlaySessions.slice(0, 12).map((session) => (
              <ListItem
                key={session.session_id}
                disableGutters
                secondaryAction={(
                  <Stack direction="row" spacing={1}>
                    <Chip label={session.status || 'unknown'} size="small" color={session.status === 'running' ? 'success' : 'default'} />
                    <Chip label={session.current_step || 'unknown'} size="small" />
                    <Chip label={`${session.active_clients || 0} clients`} size="small" />
                  </Stack>
                )}
              >
                <ListItemText
                  primary={`${session.device_id} • config ${session.config_id}`}
                  secondary={`speed ${session.ffmpeg_speed ? `${session.ffmpeg_speed.toFixed(2)}x` : 'n/a'} • fps ${session.ffmpeg_fps || 'n/a'} • bitrate ${Math.round(session.ffmpeg_bitrate_kbps || 0)} kbps`}
                />
              </ListItem>
            ))}
          </List>
        )}
      </Paper>
    </Stack>
  );
}

export default StreamingDiagnostics;
