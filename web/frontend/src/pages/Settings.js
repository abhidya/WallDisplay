import React, { useEffect, useState } from 'react';
import {
  Grid,
  Paper,
  Typography,
  Button,
  TextField,
  Box,
  Divider,
  Alert,
  Snackbar,
  List,
  ListItem,
  ListItemText,
  Switch,
  FormControlLabel,
  Card,
  CardContent,
  CardActions,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  CircularProgress
} from '@mui/material';
import {
  Save as SaveIcon,
  Folder as FolderIcon,
  Upload as UploadIcon,
  Download as DownloadIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import axios from 'axios';

const UI_PREFS_KEY = 'nanoDlnaUiPrefs';

function loadUiPrefs() {
  try {
    const raw = localStorage.getItem(UI_PREFS_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return {
      themeMode: parsed.themeMode === 'dark' ? 'dark' : 'light',
      showExperimentalTabs: Boolean(parsed.showExperimentalTabs),
    };
  } catch (error) {
    return {
      themeMode: 'light',
      showExperimentalTabs: false,
    };
  }
}

function Settings() {
  const [configFile, setConfigFile] = useState('');
  const [openLoadDialog, setOpenLoadDialog] = useState(false);
  const [openSaveDialog, setOpenSaveDialog] = useState(false);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success'
  });
  const [settings, setSettings] = useState({
    autoDiscoverDevices: true,
    defaultVideoDirectory: '/tmp/nanodlna/uploads',
    enableLogging: true,
    logLevel: 'info',
    serverPort: 8000,
    enableSubtitles: true,
    themeMode: 'light',
    showExperimentalTabs: false,
  });

  useEffect(() => {
    const uiPrefs = loadUiPrefs();
    setSettings((current) => ({
      ...current,
      themeMode: uiPrefs.themeMode,
      showExperimentalTabs: uiPrefs.showExperimentalTabs,
    }));
  }, []);

  const handleLoadConfig = async () => {
    try {
      setLoading(true);
      const response = await axios.post('/api/devices/load-config', null, {
        params: { config_file: configFile }
      });
      setOpenLoadDialog(false);
      setConfigFile('');
      setSnackbar({
        open: true,
        message: `Configuration loaded successfully. Found ${response.data.devices.length} devices.`,
        severity: 'success'
      });
    } catch (err) {
      console.error('Error loading configuration:', err);
      setSnackbar({
        open: true,
        message: 'Failed to load configuration',
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveConfig = async () => {
    try {
      setLoading(true);
      await axios.post('/api/devices/save-config', null, {
        params: { config_file: configFile }
      });
      setOpenSaveDialog(false);
      setConfigFile('');
      setSnackbar({
        open: true,
        message: 'Configuration saved successfully',
        severity: 'success'
      });
    } catch (err) {
      console.error('Error saving configuration:', err);
      setSnackbar({
        open: true,
        message: 'Failed to save configuration',
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSettingChange = (setting, value) => {
    setSettings(prev => ({
      ...prev,
      [setting]: value
    }));
  };

  const handleSaveSettings = () => {
    localStorage.setItem(
      UI_PREFS_KEY,
      JSON.stringify({
        themeMode: settings.themeMode,
        showExperimentalTabs: settings.showExperimentalTabs,
      }),
    );
    window.dispatchEvent(new Event('nanoDlnaUiPrefsChanged'));
    setSnackbar({
      open: true,
      message: 'Settings saved successfully',
      severity: 'success'
    });
  };

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({
      ...prev,
      open: false
    }));
  };

  return (
    <Grid container spacing={3}>
      {/* Header */}
      <Grid item xs={12}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h4">Settings</Typography>
          <Button
            variant="contained"
            color="primary"
            startIcon={<SaveIcon />}
            onClick={handleSaveSettings}
          >
            Save Settings
          </Button>
        </Box>
        <Divider sx={{ mb: 2 }} />
      </Grid>

      {/* General Settings */}
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            <SettingsIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
            General Settings
          </Typography>
          <Divider sx={{ my: 1 }} />
          <List>
            <ListItem>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.themeMode === 'dark'}
                    onChange={(e) => handleSettingChange('themeMode', e.target.checked ? 'dark' : 'light')}
                    color="primary"
                  />
                }
                label="Dark theme"
              />
            </ListItem>
            <ListItem>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.autoDiscoverDevices}
                    onChange={(e) => handleSettingChange('autoDiscoverDevices', e.target.checked)}
                    color="primary"
                  />
                }
                label="Auto-discover devices on startup"
              />
            </ListItem>
            <ListItem>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enableLogging}
                    onChange={(e) => handleSettingChange('enableLogging', e.target.checked)}
                    color="primary"
                  />
                }
                label="Enable logging"
              />
            </ListItem>
            <ListItem>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enableSubtitles}
                    onChange={(e) => handleSettingChange('enableSubtitles', e.target.checked)}
                    color="primary"
                  />
                }
                label="Enable subtitles"
              />
            </ListItem>
            <ListItem>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showExperimentalTabs}
                    onChange={(e) => handleSettingChange('showExperimentalTabs', e.target.checked)}
                    color="primary"
                  />
                }
                label="Show experimental tools (Renderer, Depth Processing, Projection Mapping, Projection Animation)"
              />
            </ListItem>
            <ListItem>
              <TextField
                label="Server Port"
                type="number"
                value={settings.serverPort}
                onChange={(e) => handleSettingChange('serverPort', e.target.value)}
                fullWidth
                variant="outlined"
                sx={{ mt: 1 }}
              />
            </ListItem>
            <ListItem>
              <TextField
                label="Default Video Directory"
                value={settings.defaultVideoDirectory}
                onChange={(e) => handleSettingChange('defaultVideoDirectory', e.target.value)}
                fullWidth
                variant="outlined"
                sx={{ mt: 1 }}
              />
            </ListItem>
          </List>
        </Paper>
      </Grid>

      {/* Configuration Management */}
      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            <FolderIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
            Configuration Management
          </Typography>
          <Divider sx={{ my: 1 }} />
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6">Load Configuration</Typography>
                  <Typography variant="body2" color="textSecondary">
                    Load devices from a configuration file
                  </Typography>
                </CardContent>
                <CardActions>
                  <Button
                    size="small"
                    color="primary"
                    startIcon={<UploadIcon />}
                    onClick={() => setOpenLoadDialog(true)}
                  >
                    Load
                  </Button>
                </CardActions>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6">Save Configuration</Typography>
                  <Typography variant="body2" color="textSecondary">
                    Save devices to a configuration file
                  </Typography>
                </CardContent>
                <CardActions>
                  <Button
                    size="small"
                    color="primary"
                    startIcon={<DownloadIcon />}
                    onClick={() => setOpenSaveDialog(true)}
                  >
                    Save
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          </Grid>
        </Paper>

        {/* System Information */}
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            <RefreshIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
            System Information
          </Typography>
          <Divider sx={{ my: 1 }} />
          <List>
            <ListItem>
              <ListItemText
                primary="Version"
                secondary="nano-dlna Dashboard v1.0.0"
              />
            </ListItem>
            <ListItem>
              <ListItemText
                primary="Backend"
                secondary="FastAPI + SQLite"
              />
            </ListItem>
            <ListItem>
              <ListItemText
                primary="Frontend"
                secondary="React + Material-UI"
              />
            </ListItem>
            <ListItem>
              <Button
                variant="outlined"
                color="primary"
                fullWidth
                onClick={() => window.open('/docs', '_blank')}
              >
                API Documentation
              </Button>
            </ListItem>
          </List>
        </Paper>
      </Grid>

      {/* Load Config Dialog */}
      <Dialog open={openLoadDialog} onClose={() => setOpenLoadDialog(false)}>
        <DialogTitle>Load Configuration</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Enter the path to the configuration file to load.
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            label="Configuration File Path"
            type="text"
            fullWidth
            variant="outlined"
            value={configFile}
            onChange={(e) => setConfigFile(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenLoadDialog(false)}>Cancel</Button>
          <Button
            onClick={handleLoadConfig}
            variant="contained"
            color="primary"
            disabled={loading || !configFile}
            startIcon={loading ? <CircularProgress size={20} /> : null}
          >
            {loading ? 'Loading...' : 'Load'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Save Config Dialog */}
      <Dialog open={openSaveDialog} onClose={() => setOpenSaveDialog(false)}>
        <DialogTitle>Save Configuration</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Enter the path where you want to save the configuration file.
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            label="Configuration File Path"
            type="text"
            fullWidth
            variant="outlined"
            value={configFile}
            onChange={(e) => setConfigFile(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenSaveDialog(false)}>Cancel</Button>
          <Button
            onClick={handleSaveConfig}
            variant="contained"
            color="primary"
            disabled={loading || !configFile}
            startIcon={loading ? <CircularProgress size={20} /> : null}
          >
            {loading ? 'Saving...' : 'Save'}
          </Button>
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

export default Settings;
