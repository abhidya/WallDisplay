import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Box,
  Alert,
  Tabs,
  Tab,
  Grid,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Paper,
  Divider,
  Switch,
  FormControlLabel,
  Chip,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  Save as SaveIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { discoveryV2Api } from '../services/api';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`config-tabpanel-${index}`}
      aria-labelledby={`config-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

function ConfigurationManager({ open, onClose }) {
  const [tabValue, setTabValue] = useState(0);
  const [deviceConfigs, setDeviceConfigs] = useState({});
  const [globalConfig, setGlobalConfig] = useState({});
  const [backends, setBackends] = useState({});
  const [editingDevice, setEditingDevice] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    if (open) {
      fetchConfigurations();
    }
  }, [open]);

  const fetchConfigurations = async () => {
    try {
      const [deviceConfigsRes, globalConfigRes, backendsRes] = await Promise.all([
        discoveryV2Api.getDeviceConfigs(),
        discoveryV2Api.getGlobalConfig(),
        discoveryV2Api.getBackends(),
      ]);

      setDeviceConfigs(deviceConfigsRes.data || {});
      setGlobalConfig(globalConfigRes.data || {});
      setBackends(backendsRes.data || {});
    } catch (err) {
      setError('Failed to fetch configurations');
      console.error(err);
    }
  };

  const handleSaveDeviceConfig = async () => {
    try {
      await discoveryV2Api.updateDeviceConfig(editingDevice.name, editingDevice);
      setSuccess(`Device ${editingDevice.name} configuration saved`);
      setEditingDevice(null);
      fetchConfigurations();
    } catch (err) {
      setError(`Failed to save device configuration: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleDeleteDeviceConfig = async (deviceName) => {
    if (!window.confirm(`Delete configuration for ${deviceName}?`)) return;
    
    try {
      await discoveryV2Api.deleteDeviceConfig(deviceName);
      setSuccess(`Device ${deviceName} configuration deleted`);
      fetchConfigurations();
    } catch (err) {
      setError(`Failed to delete device configuration: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleSaveGlobalConfig = async () => {
    try {
      await discoveryV2Api.updateGlobalConfig(globalConfig);
      setSuccess('Global configuration saved');
    } catch (err) {
      setError(`Failed to save global configuration: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleToggleBackend = async (backendName, enabled) => {
    try {
      if (enabled) {
        await discoveryV2Api.enableBackend(backendName);
      } else {
        await discoveryV2Api.disableBackend(backendName);
      }
      setSuccess(`Backend ${backendName} ${enabled ? 'enabled' : 'disabled'}`);
      fetchConfigurations();
    } catch (err) {
      setError(`Failed to toggle backend: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
    setError(null);
    setSuccess(null);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Discovery Configuration Manager
        <IconButton
          aria-label="close"
          onClick={onClose}
          sx={{
            position: 'absolute',
            right: 8,
            top: 8,
          }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
        
        <Tabs value={tabValue} onChange={handleTabChange} aria-label="configuration tabs">
          <Tab label="Device Configs" />
          <Tab label="Global Config" />
          <Tab label="Backends" />
        </Tabs>
        
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6">Device Configurations</Typography>
            <Button
              startIcon={<AddIcon />}
              variant="contained"
              size="small"
              onClick={() => setEditingDevice({ 
                name: '', 
                type: 'dlna',
                hostname: '',
                port: null,
                group: '',
                zone: '',
                capabilities: []
              })}
            >
              Add Device
            </Button>
          </Box>
          
          <List>
            {Object.entries(deviceConfigs).map(([name, config]) => (
              <ListItem key={name} component={Paper} sx={{ mb: 1 }}>
                <ListItemText
                  primary={name}
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Type: {config.type} | Host: {config.hostname}
                        {config.port && ` | Port: ${config.port}`}
                      </Typography>
                      {config.group && <Chip label={`Group: ${config.group}`} size="small" sx={{ mr: 1 }} />}
                      {config.zone && <Chip label={`Zone: ${config.zone}`} size="small" />}
                    </Box>
                  }
                />
                <ListItemSecondaryAction>
                  <IconButton edge="end" onClick={() => setEditingDevice(config)}>
                    <EditIcon />
                  </IconButton>
                  <IconButton edge="end" onClick={() => handleDeleteDeviceConfig(name)}>
                    <DeleteIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
          
          {editingDevice && (
            <Dialog open={true} onClose={() => setEditingDevice(null)} maxWidth="sm" fullWidth>
              <DialogTitle>
                {editingDevice.name ? `Edit ${editingDevice.name}` : 'Add New Device'}
              </DialogTitle>
              <DialogContent>
                <Grid container spacing={2} sx={{ mt: 1 }}>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Device Name"
                      value={editingDevice.name || ''}
                      onChange={(e) => setEditingDevice({ ...editingDevice, name: e.target.value })}
                      disabled={!!deviceConfigs[editingDevice.name]}
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <FormControl fullWidth>
                      <InputLabel>Type</InputLabel>
                      <Select
                        value={editingDevice.type || 'dlna'}
                        label="Type"
                        onChange={(e) => setEditingDevice({ ...editingDevice, type: e.target.value })}
                      >
                        <MenuItem value="dlna">DLNA</MenuItem>
                        <MenuItem value="airplay">AirPlay</MenuItem>
                        <MenuItem value="transcreen">TranScreen</MenuItem>
                        <MenuItem value="overlay">Overlay</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Hostname/IP"
                      value={editingDevice.hostname || ''}
                      onChange={(e) => setEditingDevice({ ...editingDevice, hostname: e.target.value })}
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Port (optional)"
                      type="number"
                      value={editingDevice.port || ''}
                      onChange={(e) => setEditingDevice({ ...editingDevice, port: e.target.value ? parseInt(e.target.value) : null })}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      fullWidth
                      label="Group (optional)"
                      value={editingDevice.group || ''}
                      onChange={(e) => setEditingDevice({ ...editingDevice, group: e.target.value })}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      fullWidth
                      label="Zone (optional)"
                      value={editingDevice.zone || ''}
                      onChange={(e) => setEditingDevice({ ...editingDevice, zone: e.target.value })}
                    />
                  </Grid>
                </Grid>
              </DialogContent>
              <DialogActions>
                <Button onClick={() => setEditingDevice(null)}>Cancel</Button>
                <Button onClick={handleSaveDeviceConfig} variant="contained" startIcon={<SaveIcon />}>
                  Save
                </Button>
              </DialogActions>
            </Dialog>
          )}
        </TabPanel>
        
        <TabPanel value={tabValue} index={1}>
          <Typography variant="h6" gutterBottom>Global Configuration</Typography>
          
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={globalConfig.discovery?.enabled !== false}
                    onChange={(e) => setGlobalConfig({
                      ...globalConfig,
                      discovery: { ...globalConfig.discovery, enabled: e.target.checked }
                    })}
                  />
                }
                label="Enable Discovery"
              />
            </Grid>
            
            <Grid item xs={6}>
              <TextField
                fullWidth
                label="Discovery Interval (seconds)"
                type="number"
                value={globalConfig.discovery?.interval || 30}
                onChange={(e) => setGlobalConfig({
                  ...globalConfig,
                  discovery: { ...globalConfig.discovery, interval: parseInt(e.target.value) || 30 }
                })}
              />
            </Grid>
            
            <Grid item xs={6}>
              <TextField
                fullWidth
                label="Discovery Timeout (seconds)"
                type="number"
                value={globalConfig.discovery?.timeout || 5}
                onChange={(e) => setGlobalConfig({
                  ...globalConfig,
                  discovery: { ...globalConfig.discovery, timeout: parseInt(e.target.value) || 5 }
                })}
              />
            </Grid>
            
            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle1" gutterBottom>Casting Settings</Typography>
            </Grid>
            
            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel>Default Video Format</InputLabel>
                <Select
                  value={globalConfig.casting?.default_format || 'original'}
                  label="Default Video Format"
                  onChange={(e) => setGlobalConfig({
                    ...globalConfig,
                    casting: { ...globalConfig.casting, default_format: e.target.value }
                  })}
                >
                  <MenuItem value="original">Original</MenuItem>
                  <MenuItem value="transcode">Transcode</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel>Default Audio Format</InputLabel>
                <Select
                  value={globalConfig.casting?.default_audio || 'original'}
                  label="Default Audio Format"
                  onChange={(e) => setGlobalConfig({
                    ...globalConfig,
                    casting: { ...globalConfig.casting, default_audio: e.target.value }
                  })}
                >
                  <MenuItem value="original">Original</MenuItem>
                  <MenuItem value="aac">AAC</MenuItem>
                  <MenuItem value="mp3">MP3</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={globalConfig.casting?.enable_subtitles !== false}
                    onChange={(e) => setGlobalConfig({
                      ...globalConfig,
                      casting: { ...globalConfig.casting, enable_subtitles: e.target.checked }
                    })}
                  />
                }
                label="Enable Subtitles"
              />
            </Grid>
            
            <Grid item xs={12}>
              <Button 
                variant="contained" 
                startIcon={<SaveIcon />}
                onClick={handleSaveGlobalConfig}
                sx={{ mt: 2 }}
              >
                Save Global Config
              </Button>
            </Grid>
          </Grid>
        </TabPanel>
        
        <TabPanel value={tabValue} index={2}>
          <Typography variant="h6" gutterBottom>Discovery Backends</Typography>
          
          <List>
            {Object.entries(backends).map(([name, info]) => (
              <ListItem key={name} component={Paper} sx={{ mb: 1 }}>
                <ListItemText
                  primary={name}
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Status: {info.status} | Devices: {info.device_count}
                      </Typography>
                      {info.last_discovery && (
                        <Typography variant="caption" color="text.secondary">
                          Last discovery: {new Date(info.last_discovery).toLocaleString()}
                        </Typography>
                      )}
                    </Box>
                  }
                />
                <ListItemSecondaryAction>
                  <Switch
                    checked={info.enabled}
                    onChange={(e) => handleToggleBackend(name, e.target.checked)}
                  />
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </TabPanel>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

export default ConfigurationManager;
