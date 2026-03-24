import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
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
import { streamingApi } from '../services/api';

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    const fetchData = async (isPolling = false) => {
      try {
        if (!isPolling) {
          setLoading(true);
        }

        const [statsRes, analyticsRes, healthRes, sessionsRes] = await Promise.all([
          streamingApi.getStreamingStats(),
          streamingApi.getStreamingAnalytics(),
          streamingApi.getStreamingHealth(),
          streamingApi.getSessions(),
        ]);

        if (!active) {
          return;
        }

        setStats(statsRes.data);
        setAnalytics(analyticsRes.data);
        setHealth(healthRes.data);
        setSessions(sessionsRes.data || []);
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

  if (loading && !stats) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  const statsByType = renderCountMap(stats?.sessions_by_stream_type);
  const consumerBreakdown = renderCountMap(stats?.sessions_by_consumer_prefix);
  const activeByType = renderCountMap(analytics?.active_sessions_by_stream_type);
  const activeByConsumer = renderCountMap(analytics?.active_sessions_by_consumer_prefix);
  const stalledByType = renderCountMap(health?.stalled_by_stream_type);
  const errorByType = renderCountMap(health?.error_by_stream_type);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Streaming Diagnostics</Typography>
        <Typography variant="body2" color="text.secondary">
          Ownership and health view for device streams, projection streams, and overlay mapping streams.
        </Typography>
      </Box>

      {error ? <Alert severity="error">{error}</Alert> : null}

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
    </Stack>
  );
}

export default StreamingDiagnostics;
