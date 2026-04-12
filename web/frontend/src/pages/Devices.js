import React, { useState, useEffect } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Grid,
  Paper,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  CardHeader,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  TextField,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  CircularProgress,
  Box,
  Chip,
  Divider,
  Alert,
  Snackbar,
  LinearProgress,
  Switch,
  FormControlLabel
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Settings as SettingsIcon,
  FilterList as FilterIcon,
  ExpandMore as ExpandMoreIcon
} from '@mui/icons-material';
import { deviceApi } from '../services/api';
import { useNavigate } from 'react-router-dom';
import ConfigurationManager from '../components/ConfigurationManager';

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

function formatCycleAge(isoTimestamp) {
  if (!isoTimestamp) {
    return 'Never';
  }
  const parsed = Date.parse(isoTimestamp);
  if (Number.isNaN(parsed)) {
    return isoTimestamp;
  }
  return formatLastSeen((Date.now() - parsed) / 1000);
}

function getAvailabilityLabel(device) {
  return device.availability || device.derived_status || device.status || 'unknown';
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

function getProjectionChipProps(device) {
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
  if (device?.overlay_cast_source === 'direct_client') {
    return 'browser client';
  }
  if (device?.overlay_cast_source === 'backend_cast') {
    return 'backend relay';
  }
  return null;
}

function Devices() {
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openAddDialog, setOpenAddDialog] = useState(false);
  const [openDeleteDialog, setOpenDeleteDialog] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [newDevice, setNewDevice] = useState({
    name: '',
    type: 'dlna',
    hostname: '',
    friendly_name: '',
    action_url: '',
  });
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success'
  });
  const [discovering, setDiscovering] = useState(false);
  const [discoveryStatus, setDiscoveryStatus] = useState(null);
  const [openConfigManager, setOpenConfigManager] = useState(false);
  const [filters, setFilters] = useState({
    castingMethod: '',
    onlineOnly: false,
    group: '',
    zone: ''
  });
  const [showDiscoveryDiagnostics, setShowDiscoveryDiagnostics] = useState(false);
  const [discoveryIntervalInput, setDiscoveryIntervalInput] = useState('10');
  const [discoveryIntervalDirty, setDiscoveryIntervalDirty] = useState(false);
  const [savingDiscoveryInterval, setSavingDiscoveryInterval] = useState(false);

  const onlineDevices = devices.filter(device => getAvailabilityLabel(device) === 'online');
  const degradedDevices = devices.filter(device => getAvailabilityLabel(device) === 'degraded');
  const offlineDevices = devices.filter(device => getAvailabilityLabel(device) === 'offline');
  const activePlaybackDevices = devices.filter(device => device.is_playing);
  const manualControlDevices = devices.filter(
    device => device.user_control_mode && device.user_control_mode !== 'auto'
  );
  const stalestSeenSeconds = devices.reduce((maxSeen, device) => {
    const seen = device.seconds_since_seen;
    if (seen === null || seen === undefined || Number.isNaN(Number(seen))) {
      return maxSeen;
    }
    return Math.max(maxSeen, Number(seen));
  }, 0);

  useEffect(() => {
    fetchDevices();
    fetchDiscoveryStatus();
    
    // Keep device/discovery state fresh without excessive poll noise.
    const pollingInterval = setInterval(() => {
      fetchDevices(true); // true = isPolling, to avoid showing loading spinner
      fetchDiscoveryStatus();
    }, 15000);
    
    // Cleanup polling interval on unmount
    return () => {
      clearInterval(pollingInterval);
    };
  }, []);

  // Add a state to force re-renders for timer updates
  const [, forceUpdate] = useState(0);

  // Timer to update display every second
  useEffect(() => {
    let interval;
    
    // Check if any device is currently playing
    const hasPlayingDevices = devices.some(device => device.is_playing);
    
    if (hasPlayingDevices) {
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
  }, [devices]);

  const fetchDevices = async (isPolling = false) => {
    try {
      // Only show loading spinner on initial load or manual refresh
      if (!isPolling) {
        setLoading(true);
      }
      setError(null); // Clear any previous errors
      const response = await deviceApi.getDevices();
      // Debug: log playing devices
      const playingDevices = response.data.devices.filter(d => d.is_playing);
      if (playingDevices.length > 0) {
        console.log('Playing devices:', playingDevices.map(d => ({
          name: d.name,
          playback_started_at: d.playback_started_at,
          is_playing: d.is_playing,
          current_video: d.current_video
        })));
      }
      setDevices(response.data.devices);
      if (!isPolling) {
        setLoading(false);
      }
    } catch (err) {
      console.error('Error fetching devices:', err);
      
      // Provide more specific error messages based on the error
      if (err.response) {
        // The request was made and the server responded with a status code
        if (err.response.status === 404) {
          setError('API endpoint not found. The server may be misconfigured.');
        } else if (err.response.status === 500) {
          setError('Server error occurred. Please try again later.');
        } else {
          setError(`Failed to load devices: ${err.response.data.detail || 'Unknown error'}`);
        }
      } else if (err.request) {
        // The request was made but no response was received
        setError('No response from server. The backend may be down.');
      } else {
        // Something happened in setting up the request
        setError(`Failed to load devices: ${err.message}`);
      }
      
      if (!isPolling) {
        setLoading(false);
      }
    }
  };

  const fetchDiscoveryStatus = async () => {
    try {
      const response = await deviceApi.getDiscoveryStatus();
      setDiscoveryStatus(response.data);
      if (!discoveryIntervalDirty && response.data?.interval !== undefined && response.data?.interval !== null) {
        setDiscoveryIntervalInput(String(response.data.interval));
      }
    } catch (err) {
      console.error('Error fetching discovery status:', err);
    }
  };

  const handleSaveDiscoveryInterval = async () => {
    const seconds = Number.parseInt(discoveryIntervalInput, 10);
    if (!Number.isFinite(seconds) || seconds < 1 || seconds > 300) {
      setSnackbar({
        open: true,
        message: 'Discovery interval must be between 1 and 300 seconds',
        severity: 'error'
      });
      return;
    }

    try {
      setSavingDiscoveryInterval(true);
      await deviceApi.setDiscoveryInterval(seconds);
      setDiscoveryIntervalDirty(false);
      setSnackbar({
        open: true,
        message: `Discovery interval set to ${seconds}s`,
        severity: 'success'
      });
      fetchDiscoveryStatus();
    } catch (err) {
      console.error('Error updating discovery interval:', err);
      setSnackbar({
        open: true,
        message: 'Failed to update discovery interval',
        severity: 'error'
      });
    } finally {
      setSavingDiscoveryInterval(false);
    }
  };

  const handleToggleDiscovery = async () => {
    try {
      if (discoveryStatus?.running) {
        await deviceApi.pauseDiscovery();
        setSnackbar({
          open: true,
          message: 'Discovery loop paused',
          severity: 'success'
        });
      } else {
        await deviceApi.resumeDiscovery();
        setSnackbar({
          open: true,
          message: 'Discovery loop resumed',
          severity: 'success'
        });
      }
      fetchDiscoveryStatus();
    } catch (err) {
      console.error('Error toggling discovery:', err);
      setSnackbar({
        open: true,
        message: 'Failed to toggle discovery',
        severity: 'error'
      });
    }
  };

  const handleEnableAutoMode = async (deviceId) => {
    try {
      await deviceApi.enableAutoMode(deviceId);
      setSnackbar({
        open: true,
        message: 'Auto mode enabled',
        severity: 'success'
      });
      fetchDevices();
    } catch (err) {
      console.error('Error enabling auto mode:', err);
      setSnackbar({
        open: true,
        message: 'Failed to enable auto mode',
        severity: 'error'
      });
    }
  };

  const handleAddDevice = async () => {
    try {
      await deviceApi.createDevice(newDevice);
      setOpenAddDialog(false);
      setNewDevice({
        name: '',
        type: 'dlna',
        hostname: '',
        friendly_name: '',
        action_url: '',
      });
      setSnackbar({
        open: true,
        message: 'Device added successfully',
        severity: 'success'
      });
      fetchDevices();
    } catch (err) {
      console.error('Error adding device:', err);
      
      // Provide more specific error messages based on the error
      let errorMessage = 'Failed to add device';
      
      if (err.response) {
        // The request was made and the server responded with a status code
        if (err.response.status === 400) {
          // Bad request - likely validation error
          errorMessage = err.response.data.detail 
            ? `Validation error: ${err.response.data.detail}` 
            : 'Invalid device data provided';
        } else if (err.response.status === 409) {
          // Conflict - device might already exist
          errorMessage = 'A device with this name or hostname already exists';
        } else if (err.response.status === 500) {
          errorMessage = 'Server error occurred while adding device';
        } else if (err.response.data && err.response.data.detail) {
          errorMessage = `Failed to add device: ${err.response.data.detail}`;
        }
      } else if (err.request) {
        // The request was made but no response was received
        errorMessage = 'No response from server. The backend may be down.';
      } else {
        // Something happened in setting up the request
        errorMessage = `Failed to add device: ${err.message}`;
      }
      
      setSnackbar({
        open: true,
        message: errorMessage,
        severity: 'error'
      });
    }
  };

  const handleDeleteDevice = async () => {
    try {
      await deviceApi.deleteDevice(selectedDevice.id);
      setOpenDeleteDialog(false);
      setSelectedDevice(null);
      setSnackbar({
        open: true,
        message: 'Device deleted successfully',
        severity: 'success'
      });
      fetchDevices();
    } catch (err) {
      console.error('Error deleting device:', err);
      
      // Provide more specific error messages based on the error
      let errorMessage = 'Failed to delete device';
      
      if (err.response) {
        // The request was made and the server responded with a status code
        if (err.response.status === 404) {
          errorMessage = 'Device not found. It may have been already deleted.';
        } else if (err.response.status === 500) {
          errorMessage = 'Server error occurred while deleting device.';
        } else if (err.response.status === 403) {
          errorMessage = 'You do not have permission to delete this device.';
        } else if (err.response.data && err.response.data.detail) {
          errorMessage = `Failed to delete device: ${err.response.data.detail}`;
        }
      } else if (err.request) {
        // The request was made but no response was received
        errorMessage = 'No response from server. The backend may be down.';
      } else {
        // Something happened in setting up the request
        errorMessage = `Failed to delete device: ${err.message}`;
      }
      
      setSnackbar({
        open: true,
        message: errorMessage,
        severity: 'error'
      });
      
      // Close the dialog even if there was an error
      setOpenDeleteDialog(false);
    }
  };

  const handleDeviceAction = async (deviceId, action) => {
    try {
      if (action === 'pause') {
        await deviceApi.pauseVideo(deviceId);
      } else if (action === 'stop') {
        await deviceApi.stopVideo(deviceId);
      }
      setSnackbar({
        open: true,
        message: `Device ${action} successful`,
        severity: 'success'
      });
      fetchDevices();
    } catch (err) {
      console.error(`Error performing ${action} action:`, err);
      
      // Provide more specific error messages based on the error
      let errorMessage = `Failed to ${action} device`;
      
      if (err.response) {
        // The request was made and the server responded with a status code
        if (err.response.status === 404) {
          errorMessage = `Device action endpoint not found for ${action}.`;
        } else if (err.response.status === 500) {
          errorMessage = `Server error occurred while trying to ${action} device.`;
        } else if (err.response.data && err.response.data.detail) {
          errorMessage = `Failed to ${action} device: ${err.response.data.detail}`;
        }
      } else if (err.request) {
        // The request was made but no response was received
        errorMessage = `No response from server while trying to ${action} device. The backend may be down.`;
      } else {
        // Something happened in setting up the request
        errorMessage = `Failed to ${action} device: ${err.message}`;
      }
      
      setSnackbar({
        open: true,
        message: errorMessage,
        severity: 'error'
      });
    }
  };

  const handleDiscoverDevices = async () => {
    try {
      setDiscovering(true);
      const response = await deviceApi.discoverDevices();
      setSnackbar({
        open: true,
        message: `Device discovery completed. Found ${response.data.total} devices.`,
        severity: 'success'
      });
      fetchDevices();
    } catch (err) {
      console.error('Error discovering devices:', err);
      
      // Provide more specific error messages based on the error
      let errorMessage = 'Failed to discover devices';
      
      if (err.response) {
        // The request was made and the server responded with a status code
        if (err.response.status === 404) {
          errorMessage = 'Device discovery endpoint not found. The server may be misconfigured.';
        } else if (err.response.status === 500) {
          errorMessage = 'Server error occurred during device discovery. Please try again later.';
        } else if (err.response.data && err.response.data.detail) {
          errorMessage = `Device discovery failed: ${err.response.data.detail}`;
        }
      } else if (err.request) {
        // The request was made but no response was received
        errorMessage = 'No response from server during device discovery. The backend may be down.';
      } else {
        // Something happened in setting up the request
        errorMessage = `Device discovery failed: ${err.message}`;
      }
      
      setSnackbar({
        open: true,
        message: errorMessage,
        severity: 'error'
      });
    } finally {
      setDiscovering(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setNewDevice(prev => ({
      ...prev,
      [name]: value
    }));
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
        <Button variant="contained" onClick={fetchDevices}>
          Retry
        </Button>
      </Box>
    );
  }

  return (
    <Grid container spacing={3}>
      {/* Header */}
      <Grid item xs={12}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h4">Devices</Typography>
          <Box>
            <Button
              variant="contained"
              color="primary"
              startIcon={<RefreshIcon />}
              onClick={fetchDevices}
              sx={{ mr: 1 }}
            >
              Refresh
            </Button>
            <Button
              variant="contained"
              color="secondary"
              startIcon={<AddIcon />}
              onClick={() => setOpenAddDialog(true)}
            >
              Add Device
            </Button>
          </Box>
        </Box>
        <Divider sx={{ mb: 2 }} />
      </Grid>

      {/* Discovery Control */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box>
              <Typography variant="h6">Discovery Control</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Typography variant="body2" color="textSecondary" component="span">
                  Discovery Loop: 
                </Typography>
                {discoveryStatus?.running ? 
                  <Chip label="Running" color="success" size="small" sx={{ ml: 1 }} /> : 
                  <Chip label="Paused" color="default" size="small" sx={{ ml: 1 }} />
                }
              </Box>
              <Typography variant="body2" color="textSecondary" sx={{ mt: 0.75 }}>
                Status is now derived from last-seen timing with an `online / degraded / offline` model instead of raw poll results.
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1.5 }}>
                <Chip label={`${onlineDevices.length} online`} color="success" size="small" />
                <Chip label={`${degradedDevices.length} degraded`} color="warning" size="small" />
                <Chip label={`${offlineDevices.length} offline`} size="small" />
                <Chip label={`${activePlaybackDevices.length} playing`} color={activePlaybackDevices.length > 0 ? 'success' : 'default'} size="small" />
                <Chip label={`${manualControlDevices.length} manual override`} color={manualControlDevices.length > 0 ? 'warning' : 'default'} size="small" />
              </Box>
              <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
                {devices.length > 0
                  ? `Observed ${devices.length} devices. Worst-case last seen: ${formatLastSeen(stalestSeenSeconds)}.`
                  : 'No devices have been observed yet.'}
              </Typography>
              <Accordion
                expanded={showDiscoveryDiagnostics}
                onChange={(_, expanded) => setShowDiscoveryDiagnostics(expanded)}
                disableGutters
                elevation={0}
                sx={{
                  mt: 1,
                  bgcolor: 'transparent',
                  '&:before': { display: 'none' },
                }}
              >
                <AccordionSummary
                  expandIcon={<ExpandMoreIcon />}
                  sx={{ px: 0, minHeight: 'auto', '& .MuiAccordionSummary-content': { my: 0 } }}
                >
                  <Typography variant="body2" color="textSecondary">
                    Discovery Diagnostics
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ px: 0, pt: 0.5 }}>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    <Chip
                      label={`Loop ${discoveryStatus?.paused ? 'paused' : discoveryStatus?.running ? 'running' : 'stopped'}`}
                      size="small"
                      color={discoveryStatus?.running ? 'success' : 'default'}
                    />
                    {discoveryStatus?.interval !== undefined && (
                      <Chip label={`Interval ${discoveryStatus.interval}s`} size="small" />
                    )}
                    {discoveryStatus?.observed_devices !== undefined && (
                      <Chip label={`${discoveryStatus.observed_devices} in runtime inventory`} size="small" />
                    )}
                    {discoveryStatus?.devices_discovered !== undefined && (
                      <Chip label={`${discoveryStatus.devices_discovered} discovered this pass`} size="small" />
                    )}
                    {discoveryStatus?.devices_seen_this_pass !== undefined && (
                      <Chip label={`${discoveryStatus.devices_seen_this_pass} refreshed this pass`} size="small" />
                    )}
                    {discoveryStatus?.devices_registered_new !== undefined && (
                      <Chip label={`${discoveryStatus.devices_registered_new} new`} size="small" />
                    )}
                    {discoveryStatus?.devices_registered_changed !== undefined && (
                      <Chip label={`${discoveryStatus.devices_registered_changed} changed`} size="small" />
                    )}
                    {discoveryStatus?.devices_playing !== undefined && (
                      <Chip label={`${discoveryStatus.devices_playing} marked playing`} size="small" />
                    )}
                    {discoveryStatus?.ssdp_response_count !== undefined && (
                      <Chip label={`${discoveryStatus.ssdp_response_count} SSDP responses`} size="small" />
                    )}
                    {discoveryStatus?.location_url_count !== undefined && (
                      <Chip label={`${discoveryStatus.location_url_count} AVTransport endpoints`} size="small" />
                    )}
                    {discoveryStatus?.registration_failures !== undefined && (
                      <Chip label={`${discoveryStatus.registration_failures} registration failures`} size="small" color={discoveryStatus.registration_failures > 0 ? 'warning' : 'default'} />
                    )}
                    {discoveryStatus?.devices_marked_disconnected !== undefined && (
                      <Chip label={`${discoveryStatus.devices_marked_disconnected} marked disconnected`} size="small" color={discoveryStatus.devices_marked_disconnected > 0 ? 'warning' : 'default'} />
                    )}
                    {discoveryStatus?.devices_removed !== undefined && (
                      <Chip label={`${discoveryStatus.devices_removed} removed`} size="small" color={discoveryStatus.devices_removed > 0 ? 'warning' : 'default'} />
                    )}
                  </Box>
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption" color="textSecondary" display="block">
                      Last cycle finished: {formatCycleAge(discoveryStatus?.last_cycle_finished_at)}
                      {discoveryStatus?.last_cycle_duration_ms !== undefined && discoveryStatus?.last_cycle_duration_ms !== null
                        ? ` • duration ${discoveryStatus.last_cycle_duration_ms}ms`
                        : ''}
                    </Typography>
                    {Array.isArray(discoveryStatus?.candidate_hosts) && discoveryStatus.candidate_hosts.length > 0 && (
                      <Typography variant="caption" color="textSecondary" display="block">
                        Candidate interfaces: {discoveryStatus.candidate_hosts.join(', ')}
                      </Typography>
                    )}
                    {discoveryStatus?.last_error && (
                      <Typography variant="caption" color="error" display="block">
                        Last discovery error: {discoveryStatus.last_error}
                      </Typography>
                    )}
                  </Box>
                </AccordionDetails>
              </Accordion>
            </Box>
            <Box>
              <TextField
                size="small"
                label="Interval (s)"
                type="number"
                value={discoveryIntervalInput}
                onChange={(e) => {
                  setDiscoveryIntervalInput(e.target.value);
                  setDiscoveryIntervalDirty(true);
                }}
                inputProps={{ min: 1, max: 300 }}
                sx={{ mr: 1, width: 130 }}
              />
              <Button
                variant="outlined"
                color="primary"
                onClick={handleSaveDiscoveryInterval}
                disabled={savingDiscoveryInterval}
                sx={{ mr: 1 }}
              >
                {savingDiscoveryInterval ? 'Saving...' : 'Set Interval'}
              </Button>
              <Button
                variant="outlined"
                color="primary"
                onClick={handleToggleDiscovery}
                sx={{ mr: 1 }}
              >
                {discoveryStatus?.running ? 'Pause Discovery' : 'Resume Discovery'}
              </Button>
              <Button
                variant="contained"
                color="primary"
                startIcon={discovering ? <CircularProgress size={20} color="inherit" /> : <RefreshIcon />}
                onClick={handleDiscoverDevices}
                disabled={discovering}
                sx={{ mr: 1 }}
              >
                {discovering ? 'Scanning...' : 'Scan Now'}
              </Button>
              <Button
                variant="outlined"
                startIcon={<SettingsIcon />}
                onClick={() => setOpenConfigManager(true)}
              >
                Config
              </Button>
            </Box>
          </Box>
        </Paper>
      </Grid>

      {/* Filters */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
            <Typography variant="subtitle1">
              <FilterIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Filters:
            </Typography>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Casting Method</InputLabel>
              <Select
                value={filters.castingMethod}
                label="Casting Method"
                onChange={(e) => setFilters({ ...filters, castingMethod: e.target.value })}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="dlna">DLNA</MenuItem>
                <MenuItem value="airplay">AirPlay</MenuItem>
                <MenuItem value="transcreen">TranScreen</MenuItem>
                <MenuItem value="overlay">Overlay</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Group</InputLabel>
              <Select
                value={filters.group}
                label="Group"
                onChange={(e) => setFilters({ ...filters, group: e.target.value })}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="living_room">Living Room</MenuItem>
                <MenuItem value="bedroom">Bedroom</MenuItem>
                <MenuItem value="office">Office</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Zone</InputLabel>
              <Select
                value={filters.zone}
                label="Zone"
                onChange={(e) => setFilters({ ...filters, zone: e.target.value })}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="floor1">Floor 1</MenuItem>
                <MenuItem value="floor2">Floor 2</MenuItem>
                <MenuItem value="outdoor">Outdoor</MenuItem>
              </Select>
            </FormControl>
            <FormControlLabel
              control={
                <Switch
                  checked={filters.onlineOnly}
                  onChange={(e) => setFilters({ ...filters, onlineOnly: e.target.checked })}
                />
              }
              label="Online Only"
            />
          </Box>
        </Paper>
      </Grid>

      {/* Device List */}
      {devices.length === 0 ? (
        <Grid item xs={12}>
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="h6" color="textSecondary">
              No devices found
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              Add a device manually or discover devices on your network
            </Typography>
          </Paper>
        </Grid>
      ) : (
        devices.map(device => (
          <Grid item xs={12} sm={6} md={4} key={device.id}>
            <Card>
              <CardHeader
                title={device.friendly_name}
                subheader={`Type: ${device.type}`}
                action={
                  <IconButton onClick={() => { setSelectedDevice(device); setOpenDeleteDialog(true); }}>
                    <DeleteIcon />
                  </IconButton>
                }
              />
              <CardContent>
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  Status: <Chip 
                    label={getAvailabilityLabel(device)}
                    color={getAvailabilityColor(getAvailabilityLabel(device))}
                    size="small" 
                  />
                  {device.manager_status && (
                    <Chip
                      label={`manager: ${device.manager_status}`}
                      variant="outlined"
                      size="small"
                      sx={{ ml: 1 }}
                    />
                  )}
                </Typography>
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  Playing: <Chip 
                    label={device.is_playing ? 'Yes' : 'No'} 
                    color={device.is_playing ? 'success' : 'default'} 
                    size="small" 
                  />
                  {device.user_control_mode && device.user_control_mode !== 'auto' && (
                    <Chip 
                      label={`${device.user_control_mode} mode`} 
                      color="warning" 
                      size="small" 
                      sx={{ ml: 1 }}
                      title={device.user_control_reason || 'User controlled'}
                    />
                  )}
                </Typography>
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  Projection:{' '}
                  <Chip {...getProjectionChipProps(device)} size="small" />
                  {getProjectionSourceLabel(device) && (
                    <Chip
                      label={getProjectionSourceLabel(device)}
                      variant="outlined"
                      size="small"
                      sx={{ ml: 1 }}
                    />
                  )}
                  {device.active_overlay_cast && device.overlay_cast_ffmpeg_speed !== null && device.overlay_cast_ffmpeg_speed !== undefined && (
                    <Chip
                      label={`speed ${device.overlay_cast_ffmpeg_speed.toFixed(2)}x`}
                      color={device.overlay_cast_ffmpeg_speed >= 1 ? 'success' : 'warning'}
                      size="small"
                      sx={{ ml: 1 }}
                    />
                  )}
                </Typography>
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  {formatLastSeen(device.seconds_since_seen)}
                  {formatDurationSeconds(device.uptime_seconds) && ` • uptime ${formatDurationSeconds(device.uptime_seconds)}`}
                  {!formatDurationSeconds(device.uptime_seconds) && formatDurationSeconds(device.downtime_seconds) && ` • downtime ${formatDurationSeconds(device.downtime_seconds)}`}
                </Typography>
                {device.overlay_cast_source === 'direct_client' && (
                  <Typography variant="body2" color="textSecondary" gutterBottom>
                    Direct overlay page {formatCycleAge(device.overlay_cast_last_seen_at)}
                  </Typography>
                )}
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  Reconnects {device.reconnect_count ?? 0} • degraded {device.degraded_count ?? 0} • offline {device.offline_count ?? 0}
                </Typography>
                {device.current_video && (
                  <>
                    <Typography variant="body2" color="textSecondary" gutterBottom>
                      Current Video: {device.current_video.split('/').pop()}
                    </Typography>
                    {device.is_playing && (
                      <Box sx={{ mt: 1, mb: 1 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                          <Typography variant="caption" color="textSecondary">
                            {calculateCurrentPosition(device)}
                          </Typography>
                          <Typography variant="caption" color="textSecondary">
                            {device.playback_duration || "00:00:00"}
                          </Typography>
                        </Box>
                        <LinearProgress 
                          variant="determinate" 
                          value={calculateProgress(device)} 
                          sx={{ height: 8, borderRadius: 4 }}
                        />
                      </Box>
                    )}
                  </>
                )}
                <Typography variant="body2" color="textSecondary">
                  Hostname: {device.hostname}
                </Typography>
              </CardContent>
              <CardActions>
                <Button 
                  size="small" 
                  color="primary"
                  onClick={() => navigate(`/devices/${device.id}`)}
                >
                  Details
                </Button>
                {device.is_playing && (
                  <>
                    <Button 
                      size="small" 
                      color="primary"
                      onClick={() => handleDeviceAction(device.id, 'pause')}
                      startIcon={<PauseIcon />}
                    >
                      Pause
                    </Button>
                    <Button 
                      size="small" 
                      color="secondary"
                      onClick={() => handleDeviceAction(device.id, 'stop')}
                      startIcon={<StopIcon />}
                    >
                      Stop
                    </Button>
                  </>
                )}
                <Button 
                  size="small" 
                  color="primary"
                  onClick={() => navigate(`/devices/${device.id}/play`)}
                  startIcon={<PlayIcon />}
                >
                  Play Video
                </Button>
                {device.user_control_mode && device.user_control_mode !== 'auto' && (
                  <Button 
                    size="small" 
                    color="warning"
                    onClick={() => handleEnableAutoMode(device.id)}
                  >
                    Enable Auto
                  </Button>
                )}
              </CardActions>
            </Card>
          </Grid>
        ))
      )}

      {/* Add Device Dialog */}
      <Dialog open={openAddDialog} onClose={() => setOpenAddDialog(false)}>
        <DialogTitle>Add New Device</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Enter the details of the device you want to add.
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            name="name"
            label="Device Name"
            type="text"
            fullWidth
            variant="outlined"
            value={newDevice.name}
            onChange={handleInputChange}
            sx={{ mb: 2 }}
          />
          <FormControl fullWidth variant="outlined" sx={{ mb: 2 }}>
            <InputLabel>Device Type</InputLabel>
            <Select
              name="type"
              value={newDevice.type}
              onChange={handleInputChange}
              label="Device Type"
            >
              <MenuItem value="dlna">DLNA</MenuItem>
              <MenuItem value="transcreen">Transcreen</MenuItem>
            </Select>
          </FormControl>
          <TextField
            margin="dense"
            name="hostname"
            label="Hostname/IP"
            type="text"
            fullWidth
            variant="outlined"
            value={newDevice.hostname}
            onChange={handleInputChange}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            name="friendly_name"
            label="Friendly Name"
            type="text"
            fullWidth
            variant="outlined"
            value={newDevice.friendly_name}
            onChange={handleInputChange}
            sx={{ mb: 2 }}
          />
          {newDevice.type === 'dlna' && (
            <TextField
              margin="dense"
              name="action_url"
              label="Action URL (DLNA only)"
              type="text"
              fullWidth
              variant="outlined"
              value={newDevice.action_url}
              onChange={handleInputChange}
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenAddDialog(false)}>Cancel</Button>
          <Button onClick={handleAddDevice} variant="contained" color="primary">Add</Button>
        </DialogActions>
      </Dialog>

      {/* Delete Device Dialog */}
      <Dialog open={openDeleteDialog} onClose={() => setOpenDeleteDialog(false)}>
        <DialogTitle>Delete Device</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete the device "{selectedDevice?.friendly_name}"? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDeleteDialog(false)}>Cancel</Button>
          <Button onClick={handleDeleteDevice} variant="contained" color="error">Delete</Button>
        </DialogActions>
      </Dialog>

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

      {/* Configuration Manager Dialog */}
      <ConfigurationManager 
        open={openConfigManager} 
        onClose={() => setOpenConfigManager(false)} 
      />
    </Grid>
  );
}

export default Devices;
