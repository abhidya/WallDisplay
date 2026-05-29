import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Grid,
  Paper,
  Typography,
  Alert,
  Snackbar,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Checkbox,
  FormControlLabel,
  Chip
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  PlayArrow as PlayIcon,
  Devices as DevicesIcon,
  Movie as MovieIcon
} from '@mui/icons-material';
import { deviceApi, videoApi } from '../services/api';

export function isPlayableDeviceStatus(device) {
  const status = String(device?.status || '').toLowerCase();
  if (status === 'connected') return true;
  if (['disconnected', 'failed', 'error'].includes(status)) return false;

  const derivedStatus = String(device?.derived_status || '').toLowerCase();
  const availability = String(device?.availability || '').toLowerCase();
  const derivedSignals = [derivedStatus, availability].filter(Boolean);
  if (derivedSignals.some((signal) => ['online', 'ready', 'available', 'idle', 'playing', 'degraded'].includes(signal))) {
    return true;
  }
  if (derivedSignals.some((signal) => ['offline', 'disconnected', 'unavailable', 'failed', 'error'].includes(signal))) {
    return false;
  }

  return ['online', 'ready', 'available', 'idle', 'playing', 'degraded'].includes(status);
}

function PlayVideoOnDevice() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [video, setVideo] = useState(null);
  const [devices, setDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [loop, setLoop] = useState(true);
  const [syncOverlays, setSyncOverlays] = useState(false);
  const [loading, setLoading] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(null);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success'
  });

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      // Fetch video and devices in parallel
      const [videoResponse, devicesResponse] = await Promise.all([
        videoApi.getVideo(id),
        deviceApi.getDevices()
      ]);
      
      setVideo(videoResponse.data);
      // Show devices that are playable across legacy and discovery-v2 status vocabularies.
      const connectedDevices = (devicesResponse.data.devices || []).filter(isPlayableDeviceStatus);
      setDevices(connectedDevices);
      
      // If there's only one connected device, select it by default
      if (connectedDevices.length === 1) {
        setSelectedDevice(connectedDevices[0]);
      }
      
      setLoading(false);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to load data. Please try again later.');
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handlePlayVideo = async () => {
    if (!selectedDevice) {
      setSnackbar({
        open: true,
        message: 'Please select a device',
        severity: 'warning'
      });
      return;
    }

    try {
      setPlaying(true);
      await deviceApi.playVideo(selectedDevice.id, id, loop, syncOverlays);
      
      setSnackbar({
        open: true,
        message: `Playing ${video.name} on ${selectedDevice.friendly_name}`,
        severity: 'success'
      });
      
      // Navigate to device details page after successful play
      setTimeout(() => {
        navigate(`/devices/${selectedDevice.id}`);
      }, 2000);
    } catch (err) {
      console.error('Error playing video:', err);
      setSnackbar({
        open: true,
        message: 'Failed to play video on device',
        severity: 'error'
      });
      setPlaying(false);
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({
      ...prev,
      open: false
    }));
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'Unknown';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  if (loading) {
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
        <Button variant="contained" onClick={fetchData}>
          Retry
        </Button>
      </Box>
    );
  }

  if (!video) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h6">Video not found</Typography>
        <Button variant="contained" onClick={() => navigate('/videos')}>
          Back to Videos
        </Button>
      </Box>
    );
  }

  return (
    <Grid container spacing={3}>
      {/* Header */}
      <Grid item xs={12}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Button
            variant="outlined"
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/videos')}
            sx={{ mr: 2 }}
          >
            Back
          </Button>
          <Typography variant="h4">Play "{video.name}"</Typography>
        </Box>
        <Divider sx={{ mb: 2 }} />
      </Grid>

      {/* Video Info */}
      <Grid item xs={12} md={4}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Video Information</Typography>
          <List>
            <ListItem>
              <ListItemIcon>
                <MovieIcon />
              </ListItemIcon>
              <ListItemText 
                primary="Duration" 
                secondary={formatDuration(video.duration)} 
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <MovieIcon />
              </ListItemIcon>
              <ListItemText 
                primary="Format" 
                secondary={video.format || 'Unknown'} 
              />
            </ListItem>
            {video.resolution && (
              <ListItem>
                <ListItemIcon>
                  <MovieIcon />
                </ListItemIcon>
                <ListItemText 
                  primary="Resolution" 
                  secondary={video.resolution} 
                />
              </ListItem>
            )}
          </List>
        </Paper>
      </Grid>

      {/* Device Selection */}
      <Grid item xs={12} md={8}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Select Device</Typography>
          
          {devices.length === 0 ? (
            <Alert severity="warning" sx={{ mb: 2 }}>
              No playable devices available. Please make sure your devices are online or connected.
            </Alert>
          ) : (
            <Grid container spacing={2} sx={{ mb: 3 }}>
              {devices.map((device) => (
                <Grid item xs={12} sm={6} key={device.id}>
                  <Card 
                    sx={{ 
                      cursor: 'pointer',
                      border: selectedDevice?.id === device.id ? 2 : 0,
                      borderColor: 'primary.main'
                    }}
                    onClick={() => setSelectedDevice(device)}
                  >
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <DevicesIcon sx={{ mr: 1 }} />
                        <Typography variant="h6">
                          {device.friendly_name}
                        </Typography>
                      </Box>
                      <Typography variant="body2" color="textSecondary">
                        Type: {device.type}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        {device.hostname}
                      </Typography>
                      {device.is_playing && (
                        <Chip 
                          label="Currently Playing" 
                          color="warning" 
                          size="small" 
                          sx={{ mt: 1 }}
                        />
                      )}
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
          
          <Divider sx={{ my: 2 }} />
          
          <FormControlLabel
            control={
              <Checkbox
                checked={loop}
                onChange={(e) => setLoop(e.target.checked)}
                disabled={playing}
              />
            }
            label="Loop video"
            sx={{ mb: 2 }}
          />
          
          <FormControlLabel
            control={
              <Checkbox
                checked={syncOverlays}
                onChange={(e) => setSyncOverlays(e.target.checked)}
                disabled={playing}
              />
            }
            label="Sync overlay windows"
            sx={{ mb: 3 }}
          />
          
          <Button
            variant="contained"
            color="primary"
            startIcon={playing ? <CircularProgress size={20} color="inherit" /> : <PlayIcon />}
            onClick={handlePlayVideo}
            disabled={playing || devices.length === 0 || !selectedDevice}
            fullWidth
          >
            {playing ? 'Playing...' : 'Play on Selected Device'}
          </Button>
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

export default PlayVideoOnDevice;