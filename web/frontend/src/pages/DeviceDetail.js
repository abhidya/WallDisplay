import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  CircularProgress,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  Paper,
  Typography,
  Alert,
  Snackbar,
  List,
  ListItem,
  ListItemText,
  ListItemIcon
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Info as InfoIcon,
  Router as RouterIcon,
  Computer as ComputerIcon,
  Link as LinkIcon,
  Movie as MovieIcon
} from '@mui/icons-material';
import { deviceApi } from '../services/api';

function formatDurationSeconds(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return null;
  }

  const totalSeconds = Math.max(0, Math.floor(Number(value)));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

function formatLastSeen(secondsSinceSeen) {
  if (secondsSinceSeen === null || secondsSinceSeen === undefined) {
    return 'No discovery data';
  }
  if (secondsSinceSeen < 5) {
    return 'Seen just now';
  }
  const duration = formatDurationSeconds(secondsSinceSeen);
  return duration ? `Seen ${duration} ago` : 'No discovery data';
}

function formatTimestamp(value) {
  if (value === null || value === undefined) {
    return 'No data';
  }

  let dateValue = value;
  if (typeof value === 'number') {
    dateValue = new Date(value * 1000);
  } else if (typeof value === 'string') {
    dateValue = new Date(value);
  }

  if (!(dateValue instanceof Date) || Number.isNaN(dateValue.getTime())) {
    return 'No data';
  }

  return dateValue.toLocaleString();
}

function getAvailabilityLabel(device) {
  return device?.availability || device?.derived_status || device?.status || 'unknown';
}

function getAvailabilityColor(availability) {
  switch (availability) {
    case 'online':
    case 'connected':
      return 'success';
    case 'degraded':
      return 'warning';
    case 'offline':
    case 'disconnected':
      return 'default';
    default:
      return 'default';
  }
}

function getCastingMethod(device) {
  return device?.casting_method || device?.config?.casting_method || device?.type || '';
}

function isHdmiDevice(device) {
  return getCastingMethod(device) === 'hdmi' || device?.type === 'hdmi';
}

function getHdmiConnectionColor(connectionState) {
  switch (connectionState) {
    case 'attached':
      return 'success';
    case 'unresponsive':
      return 'warning';
    case 'detached':
    default:
      return 'default';
  }
}

function getProjectionChipProps(device) {
  if (isHdmiDevice(device)) {
    const projectionState = device?.hdmi_projection_state || 'idle';
    switch (projectionState) {
      case 'projecting':
        return { label: projectionState, color: 'success' };
      case 'launching':
        return { label: projectionState, color: 'info' };
      case 'stale':
        return { label: projectionState, color: 'warning' };
      default:
        return { label: projectionState, color: 'default' };
    }
  }

  if (!device?.active_overlay_cast) {
    return { label: 'stopped', color: 'default' };
  }

  if (device.overlay_cast_source === 'direct_client') {
    return { label: 'direct html', color: 'info' };
  }

  return {
    label: device.overlay_cast_status || 'running',
    color: 'success',
  };
}

function getProjectionSourceLabel(device) {
  if (isHdmiDevice(device)) {
    return 'Local HDMI';
  }
  if (device?.overlay_cast_source === 'direct_client') {
    return 'Direct browser client';
  }
  if (device?.overlay_cast_source === 'backend_cast') {
    return 'Backend relay cast';
  }
  return 'Unknown';
}

function DeviceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [device, setDevice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success'
  });
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    fetchDevice();
    // Poll for device updates at a moderate interval to reduce backend churn.
    const interval = setInterval(fetchDevice, 15000);
    return () => clearInterval(interval);
  }, [id]);

  // Timer to update display every second
  useEffect(() => {
    let interval;
    
    // Check if device is currently playing
    if (device && device.is_playing) {
      // Update display every second
      interval = setInterval(() => {
        // Force re-render to update calculated time
        forceUpdate(prev => prev + 1);
      }, 1000); // Update every second
    }
    
    // Cleanup interval on unmount or when deps change
    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [device]);

  const fetchDevice = async () => {
    try {
      // Only show loading on initial load
      if (!device) {
        setLoading(true);
      }
      const response = await deviceApi.getDevice(id);
      setDevice(response.data);
      setLoading(false);
    } catch (err) {
      console.error('Error fetching device:', err);
      setError('Failed to load device. Please try again later.');
      setLoading(false);
    }
  };

  const handleDeviceAction = async (action) => {
    try {
      if (action === 'pause') {
        await deviceApi.pauseVideo(id);
      } else if (action === 'stop') {
        await deviceApi.stopVideo(id);
      }
      setSnackbar({
        open: true,
        message: `Device ${action} successful`,
        severity: 'success'
      });
      fetchDevice();
    } catch (err) {
      console.error(`Error performing ${action} action:`, err);
      setSnackbar({
        open: true,
        message: `Failed to ${action} device`,
        severity: 'error'
      });
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({
      ...prev,
      open: false
    }));
  };

  // Calculate current playback position
  const calculateCurrentPosition = (device) => {
    try {
      // Always prefer the backend-provided position if available
      if (device.playback_position) {
        return device.playback_position;
      }
      
      // Fallback to time-based calculation only if no backend position
      if (device.is_playing && device.playback_started_at) {
        // Backend sends timezone-naive timestamp, treat it as UTC
        // Add 'Z' to indicate UTC if not present
        let timestampStr = device.playback_started_at;
        if (!timestampStr.endsWith('Z') && !timestampStr.includes('+') && !timestampStr.includes('-')) {
          timestampStr += 'Z';
        }
        
        const startTime = new Date(timestampStr).getTime();
        const currentTime = Date.now();
        const elapsedMs = currentTime - startTime;
        
        // Prevent negative values (in case of timezone issues)
        const elapsedSeconds = Math.max(0, Math.floor(elapsedMs / 1000));
        
        // Parse duration to check if we exceeded it
        if (device.playback_duration) {
          const durationParts = device.playback_duration.split(':');
          const totalSeconds = parseInt(durationParts[0]) * 3600 + parseInt(durationParts[1]) * 60 + parseInt(durationParts[2]);
          
          // Don't exceed duration
          const currentSeconds = Math.min(elapsedSeconds, totalSeconds);
          
          // Format the time
          const hours = Math.floor(currentSeconds / 3600);
          const minutes = Math.floor((currentSeconds % 3600) / 60);
          const seconds = currentSeconds % 60;
          
          return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }
        
        // If no duration, just show elapsed time
        const hours = Math.floor(elapsedSeconds / 3600);
        const minutes = Math.floor((elapsedSeconds % 3600) / 60);
        const seconds = elapsedSeconds % 60;
        
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
      }
      
      return "00:00:00";
    } catch (error) {
      console.error('Error calculating playback position:', error, device);
      return "00:00:00";
    }
  };

  // Calculate progress percentage
  const calculateProgress = (device) => {
    // Always prefer the backend-provided progress if available
    if (device.playback_progress !== null && device.playback_progress !== undefined) {
      return device.playback_progress;
    }
    
    // Fallback to calculating based on position
    if (device.is_playing && device.playback_duration) {
      const currentPos = calculateCurrentPosition(device);
      const posParts = currentPos.split(':');
      const durationParts = device.playback_duration.split(':');
      
      const posSeconds = parseInt(posParts[0]) * 3600 + parseInt(posParts[1]) * 60 + parseInt(posParts[2]);
      const durationSeconds = parseInt(durationParts[0]) * 3600 + parseInt(durationParts[1]) * 60 + parseInt(durationParts[2]);
      
      if (durationSeconds === 0) return 0;
      
      return Math.min(100, Math.floor((posSeconds / durationSeconds) * 100));
    }
    
    return 0;
  };

  if (loading && !device) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error" variant="h6">{error}</Typography>
        <Button variant="contained" onClick={fetchDevice}>
          Retry
        </Button>
      </Box>
    );
  }

  if (!device) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h6">Device not found</Typography>
        <Button variant="contained" onClick={() => navigate('/devices')}>
          Back to Devices
        </Button>
      </Box>
    );
  }

  const hdmi = isHdmiDevice(device);

  return (
    <Grid container spacing={3}>
      {/* Header */}
      <Grid item xs={12}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Button
            variant="outlined"
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/devices')}
            sx={{ mr: 2 }}
          >
            Back
          </Button>
          <Typography variant="h4">{device.friendly_name || device.name}</Typography>
        </Box>
        <Divider sx={{ mb: 2 }} />
      </Grid>

      {/* Device Info */}
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Device Information</Typography>
          <List>
            <ListItem>
              <ListItemIcon>
                <InfoIcon />
              </ListItemIcon>
              <ListItemText 
                primary="Status" 
                secondaryTypographyProps={{ component: 'div' }}
                secondary={
                  <Chip 
                    label={getAvailabilityLabel(device)}
                    color={getAvailabilityColor(getAvailabilityLabel(device))}
                    size="small" 
                  />
                } 
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <MovieIcon />
              </ListItemIcon>
              <ListItemText 
                primary="Playing" 
                secondaryTypographyProps={{ component: 'div' }}
                secondary={
                  <Chip 
                    label={device.is_playing ? 'Yes' : 'No'} 
                    color={device.is_playing ? 'success' : 'default'} 
                    size="small" 
                  />
                } 
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <InfoIcon />
              </ListItemIcon>
              <ListItemText primary="Manager Status" secondary={device.manager_status || device.status || 'unknown'} />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <InfoIcon />
              </ListItemIcon>
              <ListItemText primary="Last Seen" secondary={formatLastSeen(device.seconds_since_seen)} />
            </ListItem>
            {(device.uptime_seconds !== null && device.uptime_seconds !== undefined) && (
              <ListItem>
                <ListItemIcon>
                  <InfoIcon />
                </ListItemIcon>
                <ListItemText primary="Uptime" secondary={formatDurationSeconds(device.uptime_seconds)} />
              </ListItem>
            )}
            {(device.downtime_seconds !== null && device.downtime_seconds !== undefined) && (
              <ListItem>
                <ListItemIcon>
                  <InfoIcon />
                </ListItemIcon>
                <ListItemText primary="Downtime" secondary={formatDurationSeconds(device.downtime_seconds)} />
              </ListItem>
            )}
            <ListItem>
              <ListItemIcon>
                <ComputerIcon />
              </ListItemIcon>
              <ListItemText primary="Type" secondary={device.type} />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <RouterIcon />
              </ListItemIcon>
              <ListItemText primary="Hostname" secondary={device.hostname} />
            </ListItem>
            {hdmi && (
              <>
                <ListItem>
                  <ListItemIcon>
                    <ComputerIcon />
                  </ListItemIcon>
                  <ListItemText primary="HDMI Target" secondary={device.hdmi_target_name || device.hostname || 'Not selected'} />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <InfoIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="HDMI Connection"
                    secondaryTypographyProps={{ component: 'div' }}
                    secondary={
                      <Chip
                        label={device.hdmi_connection_state || 'unknown'}
                        color={getHdmiConnectionColor(device.hdmi_connection_state)}
                        size="small"
                      />
                    }
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <InfoIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="HDMI Power"
                    secondaryTypographyProps={{ component: 'div' }}
                    secondary={
                      <Chip
                        label={device.hdmi_power_state || 'unknown'}
                        size="small"
                        variant="outlined"
                      />
                    }
                  />
                </ListItem>
              </>
            )}
            {device.action_url && (
              <ListItem>
                <ListItemIcon>
                  <LinkIcon />
                </ListItemIcon>
                <ListItemText 
                  primary="Action URL" 
                  secondary={device.action_url} 
                  secondaryTypographyProps={{ 
                    sx: { 
                      wordBreak: 'break-all' 
                    } 
                  }} 
                />
              </ListItem>
            )}
            {device.current_video && (
              <>
                <ListItem>
                  <ListItemIcon>
                    <MovieIcon />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Current Video" 
                    secondary={device.current_video.split('/').pop()} 
                    secondaryTypographyProps={{ 
                      sx: { 
                        wordBreak: 'break-all' 
                      } 
                    }} 
                  />
                </ListItem>
                {device.is_playing && (
                  <ListItem>
                    <Box sx={{ width: '100%' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="caption" color="textSecondary">
                          {calculateCurrentPosition(device)}
                        </Typography>
                        <Typography variant="caption" color="textSecondary">
                          {device.playback_duration || "00:00:00"}
                        </Typography>
                      </Box>
                      <Box sx={{ width: '100%', mr: 1 }}>
                        <LinearProgress 
                          variant="determinate" 
                          value={calculateProgress(device)} 
                          sx={{ height: 8, borderRadius: 4 }}
                        />
                      </Box>
                    </Box>
                  </ListItem>
                )}
              </>
            )}
          </List>
        </Paper>
      </Grid>

      {/* Device Controls */}
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Projection Health</Typography>
          <List>
            <ListItem>
              <ListItemIcon>
                <MovieIcon />
              </ListItemIcon>
              <ListItemText
                primary={hdmi ? 'HDMI Projection' : 'Overlay Projection'}
                secondaryTypographyProps={{ component: 'div' }}
                secondary={
                  <Chip {...getProjectionChipProps(device)} size="small" />
                }
              />
            </ListItem>
            {hdmi && (
              <ListItem>
                <ListItemIcon>
                  <InfoIcon />
                </ListItemIcon>
                <ListItemText primary="Projection Source" secondary={getProjectionSourceLabel(device)} />
              </ListItem>
            )}
            {device.active_overlay_cast && (
              <>
                <ListItem>
                  <ListItemIcon>
                    <InfoIcon />
                  </ListItemIcon>
                  <ListItemText primary="Projection Source" secondary={getProjectionSourceLabel(device)} />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <InfoIcon />
                  </ListItemIcon>
                  <ListItemText primary="Projection Uptime" secondary={formatDurationSeconds(device.overlay_cast_uptime_seconds)} />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <InfoIcon />
                  </ListItemIcon>
                  <ListItemText primary="Projection Step" secondary={device.overlay_cast_current_step || 'unknown'} />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <InfoIcon />
                  </ListItemIcon>
                  <ListItemText primary="Projection Started" secondary={formatTimestamp(device.overlay_cast_started_at)} />
                </ListItem>
                {device.overlay_cast_source === 'direct_client' ? (
                  <>
                    <ListItem>
                      <ListItemIcon>
                        <InfoIcon />
                      </ListItemIcon>
                      <ListItemText primary="Last Client Heartbeat" secondary={formatTimestamp(device.overlay_cast_last_seen_at)} />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <LinkIcon />
                      </ListItemIcon>
                      <ListItemText primary="Direct Overlay URL" secondary={device.overlay_cast_direct_url || 'No data'} />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <InfoIcon />
                      </ListItemIcon>
                      <ListItemText primary="Overlay Config ID" secondary={device.overlay_cast_direct_config_id ?? 'No data'} />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <ComputerIcon />
                      </ListItemIcon>
                      <ListItemText primary="Document Visibility" secondary={device.overlay_cast_direct_visibility || 'No data'} />
                    </ListItem>
                  </>
                ) : (
                  <>
                    <ListItem>
                      <ListItemIcon>
                        <InfoIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Encoder Health"
                        secondary={[
                          device.overlay_cast_ffmpeg_speed !== null && device.overlay_cast_ffmpeg_speed !== undefined ? `speed ${device.overlay_cast_ffmpeg_speed.toFixed(2)}x` : null,
                          device.overlay_cast_ffmpeg_fps !== null && device.overlay_cast_ffmpeg_fps !== undefined ? `fps ${device.overlay_cast_ffmpeg_fps.toFixed(1)}` : null,
                          device.overlay_cast_ffmpeg_bitrate_kbps !== null && device.overlay_cast_ffmpeg_bitrate_kbps !== undefined ? `${Math.round(device.overlay_cast_ffmpeg_bitrate_kbps)} kbps` : null,
                        ].filter(Boolean).join(' • ') || 'No metrics'}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemIcon>
                        <InfoIcon />
                      </ListItemIcon>
                      <ListItemText primary="Relay Clients" secondary={device.overlay_cast_active_clients ?? 0} />
                    </ListItem>
                  </>
                )}
              </>
            )}
            <ListItem>
              <ListItemIcon>
                <InfoIcon />
              </ListItemIcon>
              <ListItemText primary="Last Seen At" secondary={formatTimestamp(device.last_seen_at)} />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <InfoIcon />
              </ListItemIcon>
              <ListItemText primary="Last Lost At" secondary={formatTimestamp(device.last_lost_at)} />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <InfoIcon />
              </ListItemIcon>
              <ListItemText primary="Reconnect Count" secondary={device.reconnect_count ?? 0} />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <InfoIcon />
              </ListItemIcon>
              <ListItemText primary="Degraded Count" secondary={device.degraded_count ?? 0} />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <InfoIcon />
              </ListItemIcon>
              <ListItemText primary="Offline Count" secondary={device.offline_count ?? 0} />
            </ListItem>
          </List>
        </Paper>

        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Device Controls</Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Button
              variant="contained"
              color="primary"
              startIcon={<PlayIcon />}
              onClick={() => navigate(`/devices/${id}/play`)}
              fullWidth
            >
              Play Video
            </Button>
            {device.is_playing && (
              <>
                {!hdmi && (
                  <Button
                    variant="contained"
                    color="primary"
                    startIcon={<PauseIcon />}
                    onClick={() => handleDeviceAction('pause')}
                    fullWidth
                  >
                    Pause
                  </Button>
                )}
                <Button
                  variant="contained"
                  color="secondary"
                  startIcon={<StopIcon />}
                  onClick={() => handleDeviceAction('stop')}
                  fullWidth
                >
                  Stop
                </Button>
              </>
            )}
          </Box>
        </Paper>
      </Grid>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Grid>
  );
}

export default DeviceDetail;
