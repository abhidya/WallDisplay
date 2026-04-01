import React, { useEffect, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  CircularProgress,
  Stack,
  InputAdornment,
  Tooltip,
  Chip,
  IconButton,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow
} from '@mui/material';
import {
  Save as SaveIcon,
  Folder as FolderIcon,
  Upload as UploadIcon,
  Download as DownloadIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import {
  InfoOutlined as InfoIcon,
} from '@mui/icons-material';
import axios from 'axios';
import { overlayApi } from '../services/api';

const UI_PREFS_KEY = 'nanoDlnaUiPrefs';
const DEFAULT_REDIRECT_TARGET = '/backend-static/overlay_window.html?config_id=5&controls=hidden';
const createRedirectRule = (index = 1) => ({
  id: `rule-${Date.now()}-${index}`,
  name: `Projector ${index}`,
  enabled: index === 1,
  client_ip: '',
  target_path: DEFAULT_REDIRECT_TARGET,
});

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
  const [globalApiConfigs, setGlobalApiConfigs] = useState({
    weather_api_key: '',
    transit_stop_id: '13915',
    timezone: 'America/Los_Angeles',
    apple_health_stats_json: '',
    spotify_client_id: '',
    spotify_client_secret: '',
    spotify_refresh_token: '',
    spotify_access_token: '',
    google_calendar_api_key: '',
    google_calendar_id: '',
    gmail_client_id: '',
    gmail_client_secret: '',
    gmail_refresh_token: '',
    gmail_access_token: '',
    steam_api_key: '',
    steam_id: '',
    tuya_access_id: '',
    tuya_access_secret: '',
    tuya_device_id: '',
    tuya_api_base_url: 'https://openapi.tuyaus.com',
  });
  const [projectorRedirect, setProjectorRedirect] = useState({
    enabled: false,
    client_ip: '',
    target_path: DEFAULT_REDIRECT_TARGET,
    rules: [createRedirectRule()],
  });
  const [overlayConfigs, setOverlayConfigs] = useState([]);
  const [recentProjectorRequests, setRecentProjectorRequests] = useState([]);

  const apiFieldHelp = {
    weather_api_key: 'Get your API key from openweathermap.org/api.',
    transit_stop_id: 'Transit stop code, e.g. 13915 for Carl St & Stanyan St.',
    timezone: 'IANA timezone string, e.g. America/Los_Angeles.',
    apple_health_stats_json: 'Paste a JSON array of Apple Health day records.',
    spotify_client_id: 'From your Spotify developer app dashboard.',
    spotify_client_secret: 'From your Spotify developer app dashboard.',
    spotify_refresh_token: 'OAuth refresh token for the Spotify account you want to display.',
    spotify_access_token: 'Optional manual override. Usually leave blank.',
    google_calendar_api_key: 'Google Calendar API key from Google Cloud.',
    google_calendar_id: 'Calendar ID or email-like calendar identifier.',
    gmail_client_id: 'Google OAuth client ID for Gmail access.',
    gmail_client_secret: 'Google OAuth client secret for Gmail access.',
    gmail_refresh_token: 'OAuth refresh token for Gmail.',
    gmail_access_token: 'Optional Gmail access token override.',
    steam_api_key: 'Get from steamcommunity.com/dev/apikey.',
    steam_id: 'Numeric SteamID64 for the account to display.',
    tuya_access_id: 'Tuya IoT Cloud access ID.',
    tuya_access_secret: 'Tuya IoT Cloud access secret.',
    tuya_device_id: 'Target Tuya device id.',
    tuya_api_base_url: 'Usually https://openapi.tuyaus.com unless your region differs.',
  };

  useEffect(() => {
    const uiPrefs = loadUiPrefs();
    setSettings((current) => ({
      ...current,
      themeMode: uiPrefs.themeMode,
      showExperimentalTabs: uiPrefs.showExperimentalTabs,
    }));
    overlayApi.getGlobalApiConfigs()
      .then((response) => {
        setGlobalApiConfigs((current) => ({
          ...current,
          ...(response.data || {}),
        }));
      })
      .catch((error) => {
        console.error('Error loading global API configs:', error);
      });
    overlayApi.getProjectorRedirectConfig()
      .then((response) => {
        const nextConfig = response.data || {};
        setProjectorRedirect((current) => ({
          ...current,
          ...nextConfig,
          rules: Array.isArray(nextConfig.rules) && nextConfig.rules.length
            ? nextConfig.rules
            : [{
              id: 'rule-1',
              name: 'Default projector',
              enabled: Boolean(nextConfig.enabled),
              client_ip: nextConfig.client_ip || '',
              target_path: nextConfig.target_path || DEFAULT_REDIRECT_TARGET,
            }],
        }));
      })
      .catch((error) => {
        console.error('Error loading projector redirect config:', error);
      });
    overlayApi.listConfigs()
      .then((response) => {
        setOverlayConfigs(response.data || []);
      })
      .catch((error) => {
        console.error('Error loading overlay configs:', error);
      });
    overlayApi.getRecentProjectorRedirectRequests()
      .then((response) => {
        setRecentProjectorRequests(response.data?.items || []);
      })
      .catch((error) => {
        console.error('Error loading recent projector requests:', error);
      });
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

  const handleSaveSettings = async () => {
    try {
      localStorage.setItem(
        UI_PREFS_KEY,
        JSON.stringify({
          themeMode: settings.themeMode,
          showExperimentalTabs: settings.showExperimentalTabs,
        }),
      );
      window.dispatchEvent(new Event('nanoDlnaUiPrefsChanged'));
      await overlayApi.updateGlobalApiConfigs(globalApiConfigs);
      await overlayApi.updateProjectorRedirectConfig(projectorRedirect);
      const recentResponse = await overlayApi.getRecentProjectorRedirectRequests();
      setRecentProjectorRequests(recentResponse.data?.items || []);
      setSnackbar({
        open: true,
        message: 'Settings saved successfully',
        severity: 'success'
      });
    } catch (error) {
      console.error('Error saving settings:', error);
      setSnackbar({
        open: true,
        message: 'Failed to save settings',
        severity: 'error'
      });
    }
  };

  const renderApiConfigField = (key, label, extra = {}) => (
    <TextField
      key={key}
      label={label}
      value={globalApiConfigs[key] || ''}
      onChange={(event) => setGlobalApiConfigs((current) => ({ ...current, [key]: event.target.value }))}
      fullWidth
      variant="outlined"
      multiline={extra.multiline}
      minRows={extra.minRows}
      helperText={extra.helperText}
      InputProps={{
        endAdornment: (
          <InputAdornment position="end">
            <Tooltip title={apiFieldHelp[key] || ''}>
              <InfoIcon fontSize="small" color="action" />
            </Tooltip>
          </InputAdornment>
        ),
      }}
    />
  );

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({
      ...prev,
      open: false
    }));
  };

  const updateRedirectRule = (ruleId, patch) => {
    setProjectorRedirect((current) => {
      const nextRules = (current.rules || []).map((rule) => (
        rule.id === ruleId ? { ...rule, ...patch } : rule
      ));
      return {
        ...current,
        rules: nextRules,
        enabled: nextRules.some((rule) => rule.enabled),
        client_ip: nextRules.find((rule) => rule.enabled)?.client_ip || nextRules[0]?.client_ip || '',
        target_path: nextRules.find((rule) => rule.enabled)?.target_path || nextRules[0]?.target_path || DEFAULT_REDIRECT_TARGET,
      };
    });
  };

  const addRedirectRule = () => {
    setProjectorRedirect((current) => {
      const nextRules = [...(current.rules || []), createRedirectRule((current.rules || []).length + 1)];
      return { ...current, rules: nextRules };
    });
  };

  const removeRedirectRule = (ruleId) => {
    setProjectorRedirect((current) => {
      const nextRules = (current.rules || []).filter((rule) => rule.id !== ruleId);
      const safeRules = nextRules.length ? nextRules : [createRedirectRule()];
      return {
        ...current,
        rules: safeRules,
        enabled: safeRules.some((rule) => rule.enabled),
        client_ip: safeRules.find((rule) => rule.enabled)?.client_ip || safeRules[0]?.client_ip || '',
        target_path: safeRules.find((rule) => rule.enabled)?.target_path || safeRules[0]?.target_path || DEFAULT_REDIRECT_TARGET,
      };
    });
  };

  const handleQuickTargetChange = (ruleId, targetPath) => {
    updateRedirectRule(ruleId, { target_path: targetPath });
  };

  const refreshRecentProjectorRequests = async () => {
    try {
      const response = await overlayApi.getRecentProjectorRedirectRequests();
      setRecentProjectorRequests(response.data?.items || []);
    } catch (error) {
      console.error('Error refreshing recent projector requests:', error);
    }
  };

  const quickRedirectTargets = [
    { label: 'Overlay Window (config 5)', value: DEFAULT_REDIRECT_TARGET },
    { label: 'API Docs', value: '/docs' },
    ...overlayConfigs.map((config) => ({
      label: `Overlay: ${config.name}`,
      value: `/backend-static/overlay_window.html?config_id=${config.id}&controls=hidden`,
    })),
  ];

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }}>
          <Box>
            <Typography variant="h4">Settings</Typography>
            <Typography variant="body2" color="text.secondary">
              Tidy global settings, data sources, and projector redirect routing in one place.
            </Typography>
          </Box>
          <Button variant="contained" color="primary" startIcon={<SaveIcon />} onClick={handleSaveSettings}>
            Save Settings
          </Button>
        </Stack>
      </Grid>

      <Grid item xs={12}>
        <Paper sx={{ p: 2.5 }}>
          <Stack spacing={2}>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }}>
              <Box>
                <Typography variant="h6">
                  <SettingsIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                  Projector Redirect
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Route known client IPs to a target page and inspect recent navigation attempts.
                </Typography>
              </Box>
              <Stack direction="row" spacing={1}>
                <Button variant="outlined" startIcon={<RefreshIcon />} onClick={refreshRecentProjectorRequests}>
                  Refresh Recent
                </Button>
                <Button variant="outlined" startIcon={<AddIcon />} onClick={addRedirectRule}>
                  Add Rule
                </Button>
              </Stack>
            </Stack>
            <FormControlLabel
              control={(
                <Switch
                  checked={projectorRedirect.enabled}
                  onChange={(e) => setProjectorRedirect((current) => ({ ...current, enabled: e.target.checked }))}
                  color="primary"
                />
              )}
              label="Enable projector auto-redirect"
            />
            <Grid container spacing={2}>
              {(projectorRedirect.rules || []).map((rule, index) => (
                <Grid item xs={12} md={6} key={rule.id || index}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Stack spacing={1.5}>
                      <Stack direction="row" spacing={1} justifyContent="space-between" alignItems="center">
                        <TextField
                          label="Rule Name"
                          value={rule.name || ''}
                          onChange={(event) => updateRedirectRule(rule.id, { name: event.target.value })}
                          size="small"
                          fullWidth
                        />
                        <IconButton color="error" onClick={() => removeRedirectRule(rule.id)} disabled={(projectorRedirect.rules || []).length <= 1}>
                          <DeleteIcon />
                        </IconButton>
                      </Stack>
                      <FormControlLabel
                        control={(
                          <Switch
                            checked={Boolean(rule.enabled)}
                            onChange={(event) => updateRedirectRule(rule.id, { enabled: event.target.checked })}
                          />
                        )}
                        label="Rule enabled"
                      />
                      <TextField
                        label="Client IP"
                        value={rule.client_ip || ''}
                        onChange={(event) => updateRedirectRule(rule.id, { client_ip: event.target.value })}
                        fullWidth
                        size="small"
                        helperText="Exact forwarded client IP to match."
                      />
                      <TextField
                        select
                        label="Quick Target"
                        value={quickRedirectTargets.some((option) => option.value === rule.target_path) ? rule.target_path : '__custom__'}
                        onChange={(event) => {
                          if (event.target.value !== '__custom__') {
                            handleQuickTargetChange(rule.id, event.target.value);
                          }
                        }}
                        fullWidth
                        size="small"
                      >
                        {quickRedirectTargets.map((option) => (
                          <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                        ))}
                        <MenuItem value="__custom__">Custom path</MenuItem>
                      </TextField>
                      <TextField
                        label="Redirect Target Path"
                        value={rule.target_path || ''}
                        onChange={(event) => updateRedirectRule(rule.id, { target_path: event.target.value })}
                        fullWidth
                        size="small"
                        helperText="Example: /backend-static/overlay_window.html?config_id=5&controls=hidden"
                      />
                    </Stack>
                  </Paper>
                </Grid>
              ))}
            </Grid>
            <Divider />
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="subtitle1">Recent projector client requests</Typography>
              <Chip size="small" label={`${recentProjectorRequests.length} cached`} />
            </Stack>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Time</TableCell>
                    <TableCell>Client IP</TableCell>
                    <TableCell>Request</TableCell>
                    <TableCell>Rule</TableCell>
                    <TableCell>Redirect</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {recentProjectorRequests.length ? recentProjectorRequests.map((item, index) => (
                    <TableRow key={`${item.timestamp}-${index}`}>
                      <TableCell>{item.timestamp?.replace('T', ' ').replace(/\.\d+.*$/, 'Z') || '-'}</TableCell>
                      <TableCell>{item.client_ip || '-'}</TableCell>
                      <TableCell>{item.method} {item.path}{item.query ? `?${item.query}` : ''}</TableCell>
                      <TableCell>{item.matched_rule_name || '-'}</TableCell>
                      <TableCell>{item.redirected ? item.redirect_target : '-'}</TableCell>
                    </TableRow>
                  )) : (
                    <TableRow>
                      <TableCell colSpan={5}>
                        <Typography variant="body2" color="text.secondary">
                          No recent projector navigation requests recorded yet.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Stack>
        </Paper>
      </Grid>

      <Grid item xs={12} md={4}>
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
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            <FolderIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
            Configuration Management
          </Typography>
          <Divider sx={{ my: 1 }} />
          <Stack spacing={1.5} sx={{ mt: 1 }}>
            <Button variant="outlined" startIcon={<UploadIcon />} onClick={() => setOpenLoadDialog(true)}>
              Load device configuration
            </Button>
            <Button variant="outlined" startIcon={<DownloadIcon />} onClick={() => setOpenSaveDialog(true)}>
              Save device configuration
            </Button>
          </Stack>
        </Paper>

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

      <Grid item xs={12} md={8}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            <SettingsIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
            Global API Settings
          </Typography>
          <Divider sx={{ my: 1 }} />
          <Stack spacing={1.5}>
            <Accordion defaultExpanded disableGutters>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle1">Core data sources</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Stack spacing={2}>
                  {renderApiConfigField('weather_api_key', 'Weather API Key (OpenWeatherMap)', {
                    helperText: 'Used by weather widgets across the app.',
                  })}
                  {renderApiConfigField('transit_stop_id', 'Transit Stop ID')}
                  {renderApiConfigField('timezone', 'Timezone')}
                  {renderApiConfigField('apple_health_stats_json', 'Apple Health Stats JSON', {
                    multiline: true,
                    minRows: 6,
                  })}
                </Stack>
              </AccordionDetails>
            </Accordion>
            <Accordion disableGutters>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle1">Spotify + Google</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Stack spacing={2}>
                  {renderApiConfigField('spotify_client_id', 'Spotify Client ID')}
                  {renderApiConfigField('spotify_client_secret', 'Spotify Client Secret')}
                  {renderApiConfigField('spotify_refresh_token', 'Spotify Refresh Token')}
                  {renderApiConfigField('spotify_access_token', 'Spotify Access Token Override')}
                  <Divider />
                  {renderApiConfigField('google_calendar_api_key', 'Google Calendar API Key')}
                  {renderApiConfigField('google_calendar_id', 'Google Calendar ID')}
                  {renderApiConfigField('gmail_client_id', 'Gmail Client ID')}
                  {renderApiConfigField('gmail_client_secret', 'Gmail Client Secret')}
                  {renderApiConfigField('gmail_refresh_token', 'Gmail Refresh Token')}
                  {renderApiConfigField('gmail_access_token', 'Gmail Access Token Override')}
                </Stack>
              </AccordionDetails>
            </Accordion>
            <Accordion disableGutters>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle1">Gaming + Tuya</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Stack spacing={2}>
                  {renderApiConfigField('steam_api_key', 'Steam API Key')}
                  {renderApiConfigField('steam_id', 'Steam ID')}
                  <Divider />
                  {renderApiConfigField('tuya_access_id', 'Tuya Access ID')}
                  {renderApiConfigField('tuya_access_secret', 'Tuya Access Secret')}
                  {renderApiConfigField('tuya_device_id', 'Tuya Device ID')}
                  {renderApiConfigField('tuya_api_base_url', 'Tuya API Base URL')}
                </Stack>
              </AccordionDetails>
            </Accordion>
          </Stack>
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
