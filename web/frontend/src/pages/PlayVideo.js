import React, { useCallback, useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button,
  Chip,
  Checkbox,
  CircularProgress,
  FormControlLabel,
  Grid,
  Paper,
  Typography,
  Alert,
  Snackbar,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  PlayArrow as PlayIcon,
  Movie as MovieIcon
} from '@mui/icons-material';
import PageHeader from '../components/PageHeader';
import StatusPanel from '../components/StatusPanel';
import { deviceApi, videoApi } from '../services/api';

function PlayVideo() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [device, setDevice] = useState(null);
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState('');
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
      // Fetch device and videos in parallel
      const [deviceResponse, videosResponse] = await Promise.all([
        deviceApi.getDevice(id),
        videoApi.getVideos()
      ]);
      
      setDevice(deviceResponse.data);
      setVideos(videosResponse.data.videos);
      
      // If there are videos, select the first one by default
      if (videosResponse.data.videos.length > 0) {
        setSelectedVideo(videosResponse.data.videos[0].id);
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
    try {
      setPlaying(true);
      await deviceApi.playVideo(id, selectedVideo, loop, syncOverlays);
      
      setSnackbar({
        open: true,
        message: 'Video playing on device',
        severity: 'success'
      });
      
      // Navigate back to device details page after successful play
      setTimeout(() => {
        navigate(`/devices/${id}`);
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

  if (loading) {
    return (
      <StatusPanel
        icon={<CircularProgress size={24} />}
        title="Loading Playback Target"
        description="Loading the selected device and video library."
      />
    );
  }

  if (error) {
    return (
      <StatusPanel
        severity="error"
        title="Playback Target Unavailable"
        description={error}
        action={(
          <Button variant="contained" onClick={fetchData}>
            Retry
          </Button>
        )}
      />
    );
  }

  if (!device) {
    return (
      <StatusPanel
        severity="error"
        title="Device Not Found"
        description="This playback target is not available."
        action={(
          <Button variant="contained" onClick={() => navigate('/devices')}>
            Back to Devices
          </Button>
        )}
      />
    );
  }

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <PageHeader
          title={`Play Video on ${device.friendly_name || device.name}`}
          subtitle="Choose a media file and playback behavior for this display target."
          meta={(
            <>
              <Chip label={device.status || 'unknown'} color={device.status === 'online' ? 'success' : 'default'} />
              <Chip label={`${videos.length} videos`} variant="outlined" />
              <Chip label={syncOverlays ? 'overlay sync on' : 'overlay sync off'} variant="outlined" />
            </>
          )}
          actions={(
            <Button
              variant="outlined"
              startIcon={<ArrowBackIcon />}
              onClick={() => navigate(`/devices/${id}`)}
            >
              Back
            </Button>
          )}
        />
      </Grid>

      {/* Play Video Form */}
      <Grid item xs={12} md={8}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Select Video</Typography>
          
          {videos.length === 0 ? (
            <Alert severity="warning" sx={{ mb: 2 }}>
              No videos available. Please upload videos first.
            </Alert>
          ) : (
            <FormControl fullWidth sx={{ mb: 3 }}>
              <InputLabel id="video-select-label">Video</InputLabel>
              <Select
                labelId="video-select-label"
                id="video-select"
                value={selectedVideo}
                label="Video"
                onChange={(e) => setSelectedVideo(e.target.value)}
                disabled={playing}
              >
                {videos.map((video) => (
                  <MenuItem key={video.id} value={video.id}>
                    {video.name || video.path.split('/').pop()}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          
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
            disabled={playing || videos.length === 0 || !selectedVideo}
            fullWidth
          >
            {playing ? 'Playing...' : 'Play Video'}
          </Button>
        </Paper>
      </Grid>

      {/* Device Info */}
      <Grid item xs={12} md={4}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Device Information</Typography>
          <List>
            <ListItem>
              <ListItemIcon>
                <MovieIcon />
              </ListItemIcon>
              <ListItemText 
                primary="Status" 
                secondary={device.status} 
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <MovieIcon />
              </ListItemIcon>
              <ListItemText 
                primary="Type" 
                secondary={device.type} 
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <MovieIcon />
              </ListItemIcon>
              <ListItemText 
                primary="Hostname" 
                secondary={device.hostname} 
              />
            </ListItem>
          </List>
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

export default PlayVideo;
