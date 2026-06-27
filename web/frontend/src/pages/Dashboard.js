import React, { useState, useEffect } from 'react';
import { 
  Grid, 
  Paper, 
  Typography, 
  Card, 
  CardContent, 
  CardActions, 
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Divider,
  CircularProgress,
  Box
} from '@mui/material';
import { 
  Devices as DevicesIcon, 
  VideoLibrary as VideoLibraryIcon,
  Pause as PauseIcon,
  Stop as StopIcon
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { deviceApi, videoApi } from '../services/api';

function getCastingMethod(device) {
  return device?.casting_method || device?.config?.casting_method || device?.type || '';
}

function isHdmiDevice(device) {
  return getCastingMethod(device) === 'hdmi' || device?.type === 'hdmi';
}

function Dashboard() {
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch devices and videos through the shared API client so tests and runtime use the same contract.
        const [devicesResponse, videosResponse] = await Promise.all([
          deviceApi.getDevices(),
          videoApi.getVideos()
        ]);
        setDevices(devicesResponse.data.devices || []);
        setVideos(videosResponse.data.videos || []);
        
        setLoading(false);
      } catch (err) {
        console.error('Error fetching data:', err);
        setError('Failed to load data. Please try again later.');
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleDeviceAction = async (deviceId, action) => {
    try {
      if (action === 'pause') {
        await deviceApi.pauseVideo(deviceId);
      } else if (action === 'stop') {
        await deviceApi.stopVideo(deviceId);
      } else {
        throw new Error(`Unsupported device action: ${action}`);
      }
      
      // Refresh devices after action
      const devicesResponse = await deviceApi.getDevices();
      setDevices(devicesResponse.data.devices || []);
    } catch (err) {
      console.error(`Error performing ${action} action:`, err);
      setError(`Failed to ${action} device. Please try again.`);
    }
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
        <Button variant="contained" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </Box>
    );
  }

  return (
    <Grid container spacing={3}>
      {/* Header */}
      <Grid item xs={12}>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
        <Typography variant="body1" color="textSecondary" paragraph>
          Welcome to the nano-dlna Dashboard. Manage your DLNA and Transcreen projectors from here.
        </Typography>
      </Grid>

      {/* Active Devices */}
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            <DevicesIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
            Active Devices
          </Typography>
          <Divider sx={{ my: 1 }} />
          
          {devices.length === 0 ? (
            <Typography variant="body2" color="textSecondary" sx={{ py: 2 }}>
              No active devices found.
            </Typography>
          ) : (
            <List>
              {devices.slice(0, 5).map((device) => (
                <React.Fragment key={device.id}>
                  <ListItem>
                    <ListItemAvatar>
                      <Avatar sx={{ bgcolor: device.is_playing ? 'success.main' : 'primary.main' }}>
                        <DevicesIcon />
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText 
                      primary={device.friendly_name} 
                      secondary={`Status: ${device.status} | Type: ${device.type}`} 
                    />
                    <CardActions>
                      {device.is_playing ? (
                        <>
                          {!isHdmiDevice(device) && (
                            <Button 
                              size="small" 
                              color="primary"
                              aria-label={`Pause ${device.friendly_name || device.name || 'device'}`}
                              onClick={() => handleDeviceAction(device.id, 'pause')}
                            >
                              <PauseIcon fontSize="small" />
                            </Button>
                          )}
                          <Button 
                            size="small" 
                            color="secondary"
                            aria-label={`Stop ${device.friendly_name || device.name || 'device'}`}
                            onClick={() => handleDeviceAction(device.id, 'stop')}
                          >
                            <StopIcon fontSize="small" />
                          </Button>
                        </>
                      ) : (
                        <Button 
                          size="small" 
                          color="primary"
                          onClick={() => navigate(`/devices/${device.id}`)}
                        >
                          Details
                        </Button>
                      )}
                    </CardActions>
                  </ListItem>
                  <Divider variant="inset" component="li" />
                </React.Fragment>
              ))}
            </List>
          )}
          
          <Button 
            variant="outlined" 
            color="primary" 
            fullWidth 
            sx={{ mt: 2 }}
            onClick={() => navigate('/devices')}
          >
            View All Devices
          </Button>
        </Paper>
      </Grid>

      {/* Recent Videos */}
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            <VideoLibraryIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
            Recent Videos
          </Typography>
          <Divider sx={{ my: 1 }} />
          
          {videos.length === 0 ? (
            <Typography variant="body2" color="textSecondary" sx={{ py: 2 }}>
              No videos found.
            </Typography>
          ) : (
            <List>
              {videos.slice(0, 5).map((video) => (
                <React.Fragment key={video.id}>
                  <ListItem>
                    <ListItemAvatar>
                      <Avatar sx={{ bgcolor: 'secondary.main' }}>
                        <VideoLibraryIcon />
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText 
                      primary={video.name} 
                      secondary={`Duration: ${video.duration ? Math.floor(video.duration / 60) + 'm ' + Math.floor(video.duration % 60) + 's' : 'Unknown'}`} 
                    />
                    <CardActions>
                      <Button 
                        size="small" 
                        color="primary"
                        onClick={() => navigate(`/videos/${video.id}`)}
                      >
                        Details
                      </Button>
                    </CardActions>
                  </ListItem>
                  <Divider variant="inset" component="li" />
                </React.Fragment>
              ))}
            </List>
          )}
          
          <Button 
            variant="outlined" 
            color="primary" 
            fullWidth 
            sx={{ mt: 2 }}
            onClick={() => navigate('/videos')}
          >
            View All Videos
          </Button>
        </Paper>
      </Grid>

      {/* Quick Actions */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Quick Actions
          </Typography>
          <Divider sx={{ my: 1 }} />
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography variant="h6">Discover Devices</Typography>
                  <Typography variant="body2" color="textSecondary">
                    Scan your network for DLNA devices
                  </Typography>
                </CardContent>
                <CardActions>
                  <Button 
                    size="small" 
                    color="primary"
                    onClick={() => navigate('/devices/discover')}
                  >
                    Discover
                  </Button>
                </CardActions>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography variant="h6">Add Video</Typography>
                  <Typography variant="body2" color="textSecondary">
                    Add a new video to your library
                  </Typography>
                </CardContent>
                <CardActions>
                  <Button 
                    size="small" 
                    color="primary"
                    onClick={() => navigate('/videos/add')}
                  >
                    Add
                  </Button>
                </CardActions>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography variant="h6">Scan Directory</Typography>
                  <Typography variant="body2" color="textSecondary">
                    Scan a directory for videos
                  </Typography>
                </CardContent>
                <CardActions>
                  <Button 
                    size="small" 
                    color="primary"
                    onClick={() => navigate('/videos/scan')}
                  >
                    Scan
                  </Button>
                </CardActions>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography variant="h6">Load Config</Typography>
                  <Typography variant="body2" color="textSecondary">
                    Load devices from a config file
                  </Typography>
                </CardContent>
                <CardActions>
                  <Button 
                    size="small" 
                    color="primary"
                    onClick={() => navigate('/settings/load-config')}
                  >
                    Load
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          </Grid>
        </Paper>
      </Grid>
    </Grid>
  );
}

export default Dashboard;
