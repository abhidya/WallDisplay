import React, { useState, useEffect, useCallback } from 'react';
import {
  Grid,
  Paper,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  CardHeader,
  Box,
  CircularProgress,
  Divider,
  Alert,
  Snackbar,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Chip,
  Stack,
  Tabs,
  Tab
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Info as InfoIcon,
  Settings as SettingsIcon,
  Search as SearchIcon,
  Cast as CastIcon,
  Pause as PauseIcon,
  PlayCircleFilled as ResumeIcon,
  Cable as CableIcon,
  Visibility as IdentifyIcon,
  PowerSettingsNew as PowerIcon,
  Lightbulb as LightIcon
} from '@mui/icons-material';
import { rendererApi } from '../services/api';

function displayTargetValue(display) {
  if (!display) {
    return '';
  }
  if (display.id !== undefined && display.id !== null && display.id !== '') {
    return String(display.id);
  }
  if (display.index !== undefined && display.index !== null) {
    return String(display.index);
  }
  return String(display.name || '');
}

function Renderer() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [projectors, setProjectors] = useState([]);
  const [scenes, setScenes] = useState([]);
  const [activeRenderers, setActiveRenderers] = useState([]);
  const [selectedProjector, setSelectedProjector] = useState('');
  const [selectedScene, setSelectedScene] = useState('');
  const [selectedHdmiProjector, setSelectedHdmiProjector] = useState('');
  const [selectedHdmiTarget, setSelectedHdmiTarget] = useState('');
  const [hdmiDisplays, setHdmiDisplays] = useState([]);
  const [hdmiMode, setHdmiMode] = useState('structured_light');
  const [hdmiPatternSet, setHdmiPatternSet] = useState('gray_code');
  const [hdmiFrameDuration, setHdmiFrameDuration] = useState(300);
  const [hdmiOverlayConfigId, setHdmiOverlayConfigId] = useState('1');
  const [openStatusDialog, setOpenStatusDialog] = useState(false);
  const [selectedRendererStatus, setSelectedRendererStatus] = useState(null);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success'
  });
  // AirPlay discovery state
  const [airplayDevices, setAirplayDevices] = useState([]);
  const [airplayLoading, setAirplayLoading] = useState(false);
  const [openAirplayDialog, setOpenAirplayDialog] = useState(false);
  const [airplayTabValue, setAirplayTabValue] = useState(0);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Fetch projectors, scenes, and active renderers in parallel
      const [projectorsResponse, scenesResponse, renderersResponse, hdmiDisplaysResponse] = await Promise.all([
        rendererApi.listProjectors(),
        rendererApi.listScenes(),
        rendererApi.listRenderers(),
        rendererApi.listHdmiDisplays()
      ]);

      // The API response structure is: { data: { success: true, message: "...", data: { projectors: [...] } } }
      // So we need to access data.data.projectors
      const projectorsList = projectorsResponse.data.data.projectors || [];
      const scenesList = scenesResponse.data.data.scenes || [];
      const hdmiDisplaysList = hdmiDisplaysResponse.data.data.displays || [];
      
      setProjectors(projectorsList);
      setScenes(scenesList);
      setActiveRenderers(renderersResponse.data.data.renderers || []);
      setHdmiDisplays(hdmiDisplaysList);
      
      // Set default selections if available
      if (projectorsList.length > 0) {
        setSelectedProjector(projectorsList[0].id);
      }
      
      if (scenesList.length > 0) {
        setSelectedScene(scenesList[0].id);
      }

      const nextHdmiProjectors = projectorsList.filter((projector) => projector.sender === 'hdmi');
      const fallbackHdmiProjector = nextHdmiProjectors[0] || null;
      setSelectedHdmiProjector((current) => {
        if (current && nextHdmiProjectors.some((projector) => projector.id === current)) {
          return current;
        }
        return fallbackHdmiProjector?.id || '';
      });
      setSelectedHdmiTarget((current) => {
        const firstDisplayTarget = hdmiDisplaysList[0] ? displayTargetValue(hdmiDisplaysList[0]) : '';
        if (current && hdmiDisplaysList.some((display) => displayTargetValue(display) === current)) {
          return current;
        }
        return fallbackHdmiProjector?.target_name || firstDisplayTarget;
      });
      
      setLoading(false);
    } catch (err) {
      console.error('Error fetching renderer data:', err);
      setError('Failed to load renderer data. Please try again.');
      setLoading(false);
    }
  }, []);

  const fetchActiveRenderers = useCallback(async () => {
    try {
      const response = await rendererApi.listRenderers();
      // The API response structure is: { data: { success: true, message: "...", data: { renderers: [...] } } }
      setActiveRenderers(response.data.data.renderers || []);
    } catch (err) {
      console.error('Error fetching active renderers:', err);
      // Don't set error state here to avoid disrupting the UI during auto-refresh
    }
  }, []);

  useEffect(() => {
    fetchData();
    
    // Keep active renderer state reasonably fresh without hammering the backend.
    const interval = setInterval(() => {
      fetchActiveRenderers();
    }, 15000);
    
    return () => {
      clearInterval(interval);
    };
  }, [fetchData, fetchActiveRenderers]);

  const handleStartRenderer = async () => {
    if (!selectedProjector || !selectedScene) {
      setSnackbar({
        open: true,
        message: 'Please select a projector and scene',
        severity: 'warning'
      });
      return;
    }

    try {
      setLoading(true);
      const response = await rendererApi.startRenderer(selectedScene, selectedProjector);
      console.log('Start Renderer Response:', JSON.stringify(response, null, 2));
      setSnackbar({
        open: true,
        message: 'Renderer started successfully',
        severity: 'success'
      });
      fetchActiveRenderers();
    } catch (err) {
      console.error('Error starting renderer:', err);
      setSnackbar({
        open: true,
        message: `Failed to start renderer: ${err.response?.data?.detail || err.message}`,
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleStopRenderer = async (projectorId) => {
    try {
      setLoading(true);
      const response = await rendererApi.stopRenderer(projectorId);
      console.log('Stop Renderer Response:', JSON.stringify(response, null, 2));
      setSnackbar({
        open: true,
        message: 'Renderer stopped successfully',
        severity: 'success'
      });
      fetchActiveRenderers();
    } catch (err) {
      console.error('Error stopping renderer:', err);
      setSnackbar({
        open: true,
        message: `Failed to stop renderer: ${err.response?.data?.detail || err.message}`,
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handlePauseRenderer = async (projectorId) => {
    try {
      setLoading(true);
      const response = await rendererApi.pauseRenderer(projectorId);
      console.log('Pause Renderer Response:', JSON.stringify(response, null, 2));
      setSnackbar({
        open: true,
        message: 'Renderer paused successfully',
        severity: 'success'
      });
      fetchActiveRenderers();
    } catch (err) {
      console.error('Error pausing renderer:', err);
      setSnackbar({
        open: true,
        message: `Failed to pause renderer: ${err.response?.data?.detail || err.message}`,
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleResumeRenderer = async (projectorId) => {
    try {
      setLoading(true);
      const response = await rendererApi.resumeRenderer(projectorId);
      console.log('Resume Renderer Response:', JSON.stringify(response, null, 2));
      setSnackbar({
        open: true,
        message: 'Renderer resumed successfully',
        severity: 'success'
      });
      fetchActiveRenderers();
    } catch (err) {
      console.error('Error resuming renderer:', err);
      setSnackbar({
        open: true,
        message: `Failed to resume renderer: ${err.response?.data?.detail || err.message}`,
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleViewStatus = async (projectorId) => {
    try {
      setLoading(true);
      const response = await rendererApi.getRendererStatus(projectorId);
      // The API response structure is: { data: { success: true, message: "...", data: {...} } }
      setSelectedRendererStatus(response.data.data);
      setOpenStatusDialog(true);
    } catch (err) {
      console.error('Error fetching renderer status:', err);
      setSnackbar({
        open: true,
        message: `Failed to fetch renderer status: ${err.response?.data?.detail || err.message}`,
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleStartProjector = async (projectorId) => {
    try {
      setLoading(true);
      const response = await rendererApi.startProjector(projectorId);
      console.log('Start Projector Response:', JSON.stringify(response, null, 2));
      setSnackbar({
        open: true,
        message: 'Projector started with default scene',
        severity: 'success'
      });
      fetchActiveRenderers();
    } catch (err) {
      console.error('Error starting projector:', err);
      setSnackbar({
        open: true,
        message: `Failed to start projector: ${err.response?.data?.detail || err.message}`,
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveHdmiTarget = async () => {
    if (!selectedHdmiProjector || !selectedHdmiTarget) {
      setSnackbar({
        open: true,
        message: 'Select an HDMI projector and display target',
        severity: 'warning'
      });
      return;
    }

    try {
      setLoading(true);
      await rendererApi.setProjectorTarget(selectedHdmiProjector, selectedHdmiTarget);
      setSnackbar({
        open: true,
        message: 'HDMI display target saved',
        severity: 'success'
      });
      await fetchData();
    } catch (err) {
      console.error('Error saving HDMI target:', err);
      setSnackbar({
        open: true,
        message: `Failed to save HDMI target: ${err.response?.data?.detail || err.message}`,
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const hdmiModeOptions = (modeOverride = null) => {
    const mode = modeOverride || hdmiMode;
    if (mode === 'structured_light') {
      return {
        pattern_set: hdmiPatternSet,
        frame_duration_ms: Number(hdmiFrameDuration) || 300,
        safe_black_between_frames: true
      };
    }
    if (mode === 'overlay') {
      return {
        config_id: hdmiOverlayConfigId ? Number(hdmiOverlayConfigId) : undefined,
        controls: 'hidden'
      };
    }
    if (mode === 'blank') {
      return { background_color: 'black' };
    }
    return {};
  };

  const handleStartHdmiMode = async (modeOverride = null) => {
    if (!selectedHdmiProjector) {
      setSnackbar({
        open: true,
        message: 'Select an HDMI projector first',
        severity: 'warning'
      });
      return;
    }

    const mode = modeOverride || hdmiMode;
    try {
      setLoading(true);
      await rendererApi.startProjectorMode(selectedHdmiProjector, mode, hdmiModeOptions(mode));
      setSnackbar({
        open: true,
        message: `Started ${mode.replace('_', ' ')} on HDMI projector`,
        severity: 'success'
      });
      await fetchData();
    } catch (err) {
      console.error('Error starting HDMI mode:', err);
      setSnackbar({
        open: true,
        message: `Failed to start HDMI mode: ${err.response?.data?.detail || err.message}`,
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleIdentifyHdmiProjector = async () => {
    if (!selectedHdmiProjector) {
      return;
    }

    try {
      setLoading(true);
      await rendererApi.identifyProjector(selectedHdmiProjector);
      setSnackbar({
        open: true,
        message: 'Identify pattern launched',
        severity: 'success'
      });
      await fetchData();
    } catch (err) {
      console.error('Error identifying HDMI projector:', err);
      setSnackbar({
        open: true,
        message: `Failed to identify projector: ${err.response?.data?.detail || err.message}`,
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSetPowerState = async (powerState) => {
    if (!selectedHdmiProjector) {
      return;
    }

    try {
      await rendererApi.setProjectorPowerState(selectedHdmiProjector, powerState);
      setSnackbar({
        open: true,
        message: `Projector marked ${powerState.replace('manual_', '')}`,
        severity: 'success'
      });
      await fetchData();
    } catch (err) {
      console.error('Error setting projector power state:', err);
      setSnackbar({
        open: true,
        message: `Failed to mark projector power: ${err.response?.data?.detail || err.message}`,
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

  const getProjectorById = (projectorId) => {
    return projectors.find(p => p.id === projectorId);
  };

  const getSceneById = (sceneId) => {
    return scenes.find(s => s.id === sceneId);
  };

  const isProjectorActive = (projectorId) => {
    return activeRenderers.some(r => r.projector_id === projectorId);
  };

  const hdmiProjectors = projectors.filter((projector) => projector.sender === 'hdmi');
  const selectedHdmiProjectorConfig = hdmiProjectors.find((projector) => projector.id === selectedHdmiProjector);

  const getProjectorRuntimeStatus = (projector) => {
    return activeRenderers.find((renderer) => renderer.projector_id === projector.id) || projector.runtime_status;
  };

  const getStatusColor = (status) => {
    if (['projecting', 'running', 'attached', 'manual_on'].includes(status)) return 'success';
    if (['launching', 'unknown', 'manual_off'].includes(status)) return 'warning';
    if (['stale', 'unresponsive', 'detached'].includes(status)) return 'error';
    return 'default';
  };

  const formatDisplayGeometry = (display) => {
    if (!display) {
      return 'No display target selected';
    }
    const size = `${display.width || 0}x${display.height || 0}`;
    const origin = `${display.x || 0},${display.y || 0}`;
    return `${size} at ${origin}${display.is_primary ? ' / primary' : ''}`;
  };

  const handleDiscoverAirPlayDevices = async () => {
    try {
      setAirplayLoading(true);
      
      // Fetch AirPlay devices from all sources
      const [networkResponse, systemResponse, allResponse] = await Promise.all([
        rendererApi.discoverAirPlayDevices(),
        rendererApi.listAirPlayDevices(),
        rendererApi.getAllAirPlayDevices()
      ]);
      
      // Process network devices
      const networkDevices = networkResponse.data.data.devices || [];
      networkDevices.forEach(device => {
        device.source = 'network';
      });
      
      // Process system devices
      const systemDevices = systemResponse.data.data.devices || [];
      systemDevices.forEach(device => {
        device.source = 'system';
      });
      
      // Process all devices
      const allDevices = allResponse.data.data.devices || [];
      allDevices.forEach(device => {
        // If we can't determine the source, mark it as 'combined'
        if (!networkDevices.some(d => d.id === device.id) && 
            !systemDevices.some(d => d.id === device.id)) {
          device.source = 'combined';
        } else if (networkDevices.some(d => d.id === device.id)) {
          device.source = 'network';
        } else if (systemDevices.some(d => d.id === device.id)) {
          device.source = 'system';
        }
      });
      
      setAirplayDevices(allDevices);
      
      setSnackbar({
        open: true,
        message: `Found ${allDevices.length} AirPlay devices`,
        severity: 'success'
      });
    } catch (err) {
      console.error('Error discovering AirPlay devices:', err);
      setSnackbar({
        open: true,
        message: `Failed to discover AirPlay devices: ${err.response?.data?.detail || err.message}`,
        severity: 'error'
      });
      setAirplayDevices([]);
    } finally {
      setAirplayLoading(false);
    }
  };

  const selectedHdmiRuntime = selectedHdmiProjectorConfig
    ? getProjectorRuntimeStatus(selectedHdmiProjectorConfig)
    : null;
  const selectedHdmiSenderStatus = selectedHdmiRuntime?.sender_status || {};
  const selectedHdmiDisplay = hdmiDisplays.find((display) => displayTargetValue(display) === selectedHdmiTarget);

  if (loading && projectors.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error && projectors.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error" variant="h6">{error}</Typography>
        <Button variant="contained" onClick={fetchData}>
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
          <Typography variant="h4">Renderer Management</Typography>
          <Button
            variant="contained"
            color="primary"
            startIcon={<RefreshIcon />}
            onClick={fetchData}
          >
            Refresh
          </Button>
        </Box>
        <Divider sx={{ mb: 2 }} />
      </Grid>

      {/* Start Renderer Section */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Start New Renderer</Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={4}>
              <FormControl fullWidth>
                <InputLabel>Projector</InputLabel>
                <Select
                  value={selectedProjector}
                  onChange={(e) => setSelectedProjector(e.target.value)}
                  label="Projector"
                  disabled={loading}
                >
                  {projectors.map((projector) => (
                    <MenuItem key={projector.id} value={projector.id}>
                      {projector.name} ({projector.sender})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <FormControl fullWidth>
                <InputLabel>Scene</InputLabel>
                <Select
                  value={selectedScene}
                  onChange={(e) => setSelectedScene(e.target.value)}
                  label="Scene"
                  disabled={loading}
                >
                  {scenes.map((scene) => (
                    <MenuItem key={scene.id} value={scene.id}>
                      {scene.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={12} md={4}>
              <Button
                variant="contained"
                color="primary"
                startIcon={<PlayIcon />}
                onClick={handleStartRenderer}
                disabled={loading || !selectedProjector || !selectedScene}
                fullWidth
                sx={{ height: '56px' }}
              >
                Start Renderer
              </Button>
            </Grid>
          </Grid>
        </Paper>
      </Grid>

      {/* HDMI Projector Section */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            justifyContent: 'space-between',
            alignItems: { xs: 'stretch', sm: 'center' },
            gap: 1,
            mb: 2
          }}>
            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CableIcon /> HDMI Projector
            </Typography>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={fetchData}
              disabled={loading}
            >
              Refresh Displays
            </Button>
          </Box>

          {hdmiProjectors.length === 0 ? (
            <Alert severity="info">
              No HDMI projector is configured.
            </Alert>
          ) : (
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <Stack spacing={2}>
                  <FormControl fullWidth>
                    <InputLabel>HDMI Projector</InputLabel>
                    <Select
                      value={selectedHdmiProjector}
                      onChange={(event) => {
                        const projectorId = event.target.value;
                        const projector = hdmiProjectors.find((item) => item.id === projectorId);
                        setSelectedHdmiProjector(projectorId);
                        setSelectedHdmiTarget(projector?.target_name || selectedHdmiTarget);
                      }}
                      label="HDMI Projector"
                      disabled={loading}
                    >
                      {hdmiProjectors.map((projector) => (
                        <MenuItem key={projector.id} value={projector.id}>
                          {projector.name || projector.id}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  <FormControl fullWidth>
                    <InputLabel>Display Target</InputLabel>
                    <Select
                      value={selectedHdmiTarget}
                      onChange={(event) => setSelectedHdmiTarget(event.target.value)}
                      label="Display Target"
                      disabled={loading || isProjectorActive(selectedHdmiProjector)}
                    >
                      {selectedHdmiTarget && !hdmiDisplays.some((display) => displayTargetValue(display) === selectedHdmiTarget) && (
                        <MenuItem value={selectedHdmiTarget}>
                          Saved target {selectedHdmiTarget} - not detected
                        </MenuItem>
                      )}
                      {hdmiDisplays.map((display) => (
                        <MenuItem key={displayTargetValue(display)} value={displayTargetValue(display)}>
                          {display.name || displayTargetValue(display)} - {formatDisplayGeometry(display)}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  <Button
                    variant="outlined"
                    onClick={handleSaveHdmiTarget}
                    disabled={loading || !selectedHdmiProjector || !selectedHdmiTarget || isProjectorActive(selectedHdmiProjector)}
                  >
                    Save Target
                  </Button>
                </Stack>
              </Grid>

              <Grid item xs={12} md={4}>
                <Stack spacing={2}>
                  <FormControl fullWidth>
                    <InputLabel>Content Mode</InputLabel>
                    <Select
                      value={hdmiMode}
                      onChange={(event) => setHdmiMode(event.target.value)}
                      label="Content Mode"
                      disabled={loading}
                    >
                      <MenuItem value="structured_light">Structured Light</MenuItem>
                      <MenuItem value="overlay">Overlay</MenuItem>
                      <MenuItem value="blank">Blank</MenuItem>
                    </Select>
                  </FormControl>

                  {hdmiMode === 'structured_light' && (
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                      <FormControl fullWidth>
                        <InputLabel>Pattern Set</InputLabel>
                        <Select
                          value={hdmiPatternSet}
                          onChange={(event) => setHdmiPatternSet(event.target.value)}
                          label="Pattern Set"
                          disabled={loading}
                        >
                          <MenuItem value="gray_code">Gray Code</MenuItem>
                          <MenuItem value="calibration">Calibration</MenuItem>
                          <MenuItem value="grid">Grid</MenuItem>
                          <MenuItem value="checkerboard">Checkerboard</MenuItem>
                        </Select>
                      </FormControl>
                      <TextField
                        label="Frame ms"
                        type="number"
                        value={hdmiFrameDuration}
                        onChange={(event) => setHdmiFrameDuration(event.target.value)}
                        inputProps={{ min: 50, step: 50 }}
                        disabled={loading}
                        sx={{ minWidth: { sm: 132 } }}
                      />
                    </Stack>
                  )}

                  {hdmiMode === 'overlay' && (
                    <TextField
                      label="Overlay Config ID"
                      value={hdmiOverlayConfigId}
                      onChange={(event) => setHdmiOverlayConfigId(event.target.value)}
                      disabled={loading}
                    />
                  )}

                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                    <Button
                      variant="contained"
                      startIcon={<IdentifyIcon />}
                      onClick={handleIdentifyHdmiProjector}
                      disabled={loading || !selectedHdmiProjector}
                    >
                      Identify
                    </Button>
                    <Button
                      variant="contained"
                      color="secondary"
                      startIcon={<LightIcon />}
                      onClick={() => handleStartHdmiMode()}
                      disabled={loading || !selectedHdmiProjector}
                    >
                      Start Mode
                    </Button>
                    <Button
                      variant="outlined"
                      color="inherit"
                      onClick={() => handleStartHdmiMode('blank')}
                      disabled={loading || !selectedHdmiProjector}
                    >
                      Blank
                    </Button>
                  </Stack>

                  <Button
                    variant="outlined"
                    color="error"
                    startIcon={<StopIcon />}
                    onClick={() => handleStopRenderer(selectedHdmiProjector)}
                    disabled={loading || !isProjectorActive(selectedHdmiProjector)}
                  >
                    Stop Projection
                  </Button>
                </Stack>
              </Grid>

              <Grid item xs={12} md={4}>
                <Stack spacing={1.5}>
                  <Typography variant="subtitle2">Projector State</Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Chip
                      label={`power: ${selectedHdmiSenderStatus.power_state || 'unknown'}`}
                      color={getStatusColor(selectedHdmiSenderStatus.power_state || 'unknown')}
                      size="small"
                    />
                    <Chip
                      label={`connection: ${selectedHdmiSenderStatus.connection_state || 'detached'}`}
                      color={getStatusColor(selectedHdmiSenderStatus.connection_state || 'detached')}
                      size="small"
                    />
                    <Chip
                      label={`projection: ${selectedHdmiSenderStatus.projection_state || selectedHdmiRuntime?.status || 'idle'}`}
                      color={getStatusColor(selectedHdmiSenderStatus.projection_state || selectedHdmiRuntime?.status || 'idle')}
                      size="small"
                    />
                  </Box>
                  <Typography variant="body2" color="textSecondary">
                    Target: {selectedHdmiProjectorConfig?.target_name || selectedHdmiTarget || 'none'}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Display: {selectedHdmiDisplay ? formatDisplayGeometry(selectedHdmiDisplay) : 'not detected'}
                  </Typography>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                    <Button
                      variant="outlined"
                      startIcon={<PowerIcon />}
                      onClick={() => handleSetPowerState('manual_on')}
                      disabled={loading || !selectedHdmiProjector}
                    >
                      Mark On
                    </Button>
                    <Button
                      variant="outlined"
                      startIcon={<PowerIcon />}
                      onClick={() => handleSetPowerState('manual_off')}
                      disabled={loading || !selectedHdmiProjector}
                    >
                      Mark Off
                    </Button>
                  </Stack>
                </Stack>
              </Grid>
            </Grid>
          )}
        </Paper>
      </Grid>

      {/* Active Renderers Section */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Active Renderers</Typography>
          {activeRenderers.length === 0 ? (
            <Typography variant="body2" color="textSecondary" sx={{ py: 2 }}>
              No active renderers. Start a renderer using the form above.
            </Typography>
          ) : (
            <List>
              {activeRenderers.map((renderer) => {
                const projector = getProjectorById(renderer.projector_id);
                const scene = getSceneById(renderer.scene_id);
                
                return (
                  <ListItem key={renderer.id || renderer.projector_id} divider>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <Typography variant="subtitle1">
                            {projector ? projector.name : renderer.projector_id}
                          </Typography>
                          <Chip 
                            label={renderer.status} 
                            color={getStatusColor(renderer.status)}
                            size="small" 
                            sx={{ ml: 1 }}
                          />
                        </Box>
                      }
                      secondary={
                        <>
                          <Typography variant="body2" component="span">
                            Scene: {scene ? scene.name : renderer.scene_id}
                          </Typography>
                          <br />
                          <Typography variant="body2" component="span">
                            Sender: {projector ? projector.sender : 'Unknown'}
                          </Typography>
                          {renderer.target_name && (
                            <>
                              <br />
                              <Typography variant="body2" component="span">
                                Target: {renderer.target_name}
                              </Typography>
                            </>
                          )}
                        </>
                      }
                    />
                    <ListItemSecondaryAction>
                      <IconButton 
                        edge="end" 
                        aria-label="info"
                        onClick={() => handleViewStatus(renderer.projector_id)}
                        sx={{ mr: 1 }}
                      >
                        <InfoIcon />
                      </IconButton>
                      <IconButton 
                        edge="end" 
                        aria-label="pause"
                        onClick={() => handlePauseRenderer(renderer.projector_id)}
                        color="primary"
                        sx={{ mr: 1 }}
                        disabled={renderer.sender_type === 'hdmi' || renderer.status === 'paused'}
                      >
                        <PauseIcon />
                      </IconButton>
                      <IconButton 
                        edge="end" 
                        aria-label="resume"
                        onClick={() => handleResumeRenderer(renderer.projector_id)}
                        color="success"
                        sx={{ mr: 1 }}
                        disabled={renderer.sender_type === 'hdmi' || renderer.status !== 'paused'}
                      >
                        <ResumeIcon />
                      </IconButton>
                      <IconButton 
                        edge="end" 
                        aria-label="stop"
                        onClick={() => handleStopRenderer(renderer.projector_id)}
                        color="error"
                      >
                        <StopIcon />
                      </IconButton>
                    </ListItemSecondaryAction>
                  </ListItem>
                );
              })}
            </List>
          )}
        </Paper>
      </Grid>

      {/* Available Projectors Section */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Available Projectors</Typography>
          <Grid container spacing={2}>
            {projectors.map((projector) => (
              <Grid item xs={12} sm={6} md={4} key={projector.id}>
                <Card>
                  <CardHeader
                    title={projector.name}
                    subheader={`Sender: ${projector.sender}`}
                    action={
                      <IconButton aria-label="settings">
                        <SettingsIcon />
                      </IconButton>
                    }
                  />
                  <CardContent>
                    {(() => {
                      const runtime = getProjectorRuntimeStatus(projector) || {};
                      const senderStatus = runtime.sender_status || {};
                      const statusLabel = senderStatus.projection_state || runtime.status || 'idle';
                      return (
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
                          <Chip
                            label={statusLabel}
                            color={getStatusColor(statusLabel)}
                            size="small"
                          />
                          {projector.sender === 'hdmi' && (
                            <>
                              <Chip
                                label={senderStatus.connection_state || 'detached'}
                                color={getStatusColor(senderStatus.connection_state || 'detached')}
                                size="small"
                              />
                              <Chip
                                label={senderStatus.power_state || 'unknown'}
                                color={getStatusColor(senderStatus.power_state || 'unknown')}
                                size="small"
                              />
                            </>
                          )}
                        </Box>
                      );
                    })()}
                    <Typography variant="body2" color="textSecondary" gutterBottom component="div">
                      Status: <Chip 
                        label={isProjectorActive(projector.id) ? 'Active' : 'Inactive'} 
                        color={isProjectorActive(projector.id) ? 'success' : 'default'} 
                        size="small" 
                      />
                    </Typography>
                    <Typography variant="body2" color="textSecondary" gutterBottom>
                      Target: {projector.target_name}
                    </Typography>
                    {projector.scene && (
                      <Typography variant="body2" color="textSecondary" gutterBottom>
                        Default Scene: {projector.scene}
                      </Typography>
                    )}
                    {projector.fallback_sender && (
                      <Typography variant="body2" color="textSecondary" gutterBottom>
                        Fallback: {projector.fallback_sender} → {projector.fallback_target}
                      </Typography>
                    )}
                  </CardContent>
                  <CardActions>
                    <Button 
                      size="small" 
                      color="primary"
                      startIcon={<PlayIcon />}
                      onClick={() => handleStartProjector(projector.id)}
                      disabled={isProjectorActive(projector.id)}
                    >
                      Start with Default Scene
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Paper>
      </Grid>

      {/* Status Dialog */}
      <Dialog open={openStatusDialog} onClose={() => setOpenStatusDialog(false)} maxWidth="md">
        <DialogTitle>Renderer Status</DialogTitle>
        <DialogContent>
          {selectedRendererStatus ? (
            <Box>
              <Typography variant="h6" gutterBottom>
                {selectedRendererStatus.projector_name || 'Renderer'}
              </Typography>
              <Typography variant="body1" gutterBottom>
                Status: {selectedRendererStatus.status}
              </Typography>
              <Typography variant="body1" gutterBottom>
                Scene: {selectedRendererStatus.scene_name || selectedRendererStatus.scene_id}
              </Typography>
              <Typography variant="body1" gutterBottom>
                Sender Type: {selectedRendererStatus.sender_type || selectedRendererStatus.renderer_type || 'unknown'}
              </Typography>
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="h6" gutterBottom>
                Technical Details
              </Typography>
              
              <pre style={{ 
                backgroundColor: '#f5f5f5', 
                padding: '10px', 
                borderRadius: '4px',
                overflow: 'auto',
                maxHeight: '300px'
              }}>
                {JSON.stringify(selectedRendererStatus, null, 2)}
              </pre>
            </Box>
          ) : (
            <DialogContentText>
              Loading status information...
            </DialogContentText>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenStatusDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* AirPlay Discovery Button */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6">AirPlay Devices</Typography>
            <Button
              variant="contained"
              color="primary"
              startIcon={<SearchIcon />}
              onClick={() => {
                setOpenAirplayDialog(true);
                handleDiscoverAirPlayDevices();
              }}
            >
              Discover AirPlay Devices
            </Button>
          </Box>
        </Paper>
      </Grid>

      {/* AirPlay Discovery Dialog */}
      <Dialog 
        open={openAirplayDialog} 
        onClose={() => setOpenAirplayDialog(false)} 
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>AirPlay Devices</DialogTitle>
        <DialogContent>
          <Tabs 
            value={airplayTabValue} 
            onChange={(e, newValue) => setAirplayTabValue(newValue)}
            sx={{ mb: 2 }}
          >
            <Tab label="All Devices" />
            <Tab label="Network Discovery" />
            <Tab label="System Preferences" />
          </Tabs>

          <Box sx={{ mb: 2 }}>
            <Button
              variant="contained"
              color="primary"
              startIcon={<RefreshIcon />}
              onClick={handleDiscoverAirPlayDevices}
              disabled={airplayLoading}
              sx={{ mr: 1 }}
            >
              Refresh
            </Button>
          </Box>

          {airplayLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Box>
              {airplayTabValue === 0 && (
                <List>
                  {airplayDevices.length === 0 ? (
                    <Typography variant="body2" color="textSecondary" sx={{ py: 2 }}>
                      No AirPlay devices found. Click Refresh to discover devices.
                    </Typography>
                  ) : (
                    airplayDevices.map((device) => (
                      <ListItem key={device.id} divider>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              <Typography variant="subtitle1">
                                {device.name}
                              </Typography>
                              <Chip 
                                label={device.status} 
                                color={device.status === 'available' ? 'success' : 'default'} 
                                size="small" 
                                sx={{ ml: 1 }}
                              />
                            </Box>
                          }
                          secondary={
                            <Typography variant="body2" component="span">
                              Type: {device.type}
                            </Typography>
                          }
                        />
                        <ListItemSecondaryAction>
                          <IconButton 
                            edge="end" 
                            aria-label="cast"
                            color="primary"
                          >
                            <CastIcon />
                          </IconButton>
                        </ListItemSecondaryAction>
                      </ListItem>
                    ))
                  )}
                </List>
              )}

              {airplayTabValue === 1 && (
                <List>
                  {airplayDevices.filter(d => d.source === 'network').length === 0 ? (
                    <Typography variant="body2" color="textSecondary" sx={{ py: 2 }}>
                      No AirPlay devices found on the network. Click Refresh to discover devices.
                    </Typography>
                  ) : (
                    airplayDevices.filter(d => d.source === 'network').map((device) => (
                      <ListItem key={device.id} divider>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              <Typography variant="subtitle1">
                                {device.name}
                              </Typography>
                              <Chip 
                                label={device.status} 
                                color={device.status === 'available' ? 'success' : 'default'} 
                                size="small" 
                                sx={{ ml: 1 }}
                              />
                            </Box>
                          }
                          secondary={
                            <Typography variant="body2" component="span">
                              Type: {device.type}
                            </Typography>
                          }
                        />
                        <ListItemSecondaryAction>
                          <IconButton 
                            edge="end" 
                            aria-label="cast"
                            color="primary"
                          >
                            <CastIcon />
                          </IconButton>
                        </ListItemSecondaryAction>
                      </ListItem>
                    ))
                  )}
                </List>
              )}

              {airplayTabValue === 2 && (
                <List>
                  {airplayDevices.filter(d => d.source === 'system').length === 0 ? (
                    <Typography variant="body2" color="textSecondary" sx={{ py: 2 }}>
                      No AirPlay devices found in System Preferences. Click Refresh to discover devices.
                    </Typography>
                  ) : (
                    airplayDevices.filter(d => d.source === 'system').map((device) => (
                      <ListItem key={device.id} divider>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              <Typography variant="subtitle1">
                                {device.name}
                              </Typography>
                              <Chip 
                                label={device.status} 
                                color={device.status === 'available' ? 'success' : 'default'} 
                                size="small" 
                                sx={{ ml: 1 }}
                              />
                            </Box>
                          }
                          secondary={
                            <Typography variant="body2" component="span">
                              Type: {device.type}
                            </Typography>
                          }
                        />
                        <ListItemSecondaryAction>
                          <IconButton 
                            edge="end" 
                            aria-label="cast"
                            color="primary"
                          >
                            <CastIcon />
                          </IconButton>
                        </ListItemSecondaryAction>
                      </ListItem>
                    ))
                  )}
                </List>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenAirplayDialog(false)}>Close</Button>
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
    </Grid>
  );
}

export default Renderer;
