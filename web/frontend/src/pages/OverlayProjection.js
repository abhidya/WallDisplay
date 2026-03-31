import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Grid,
    Paper,
    Typography,
    Button,
    Card,
    CardContent,
    CardHeader,
    Box,
    Alert,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    TextField,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemSecondaryAction,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Chip,
    CircularProgress,
    Tooltip,
    Slider,
    Stack,
    Divider
} from '@mui/material';
import {
    Add as AddIcon,
    Delete as DeleteIcon,
    Videocam as VideoIcon,
    Launch as LaunchIcon,
    Settings as SettingsIcon,
    WbSunny as WeatherIcon,
    Schedule as TimeIcon,
    DirectionsBus as TransitIcon,
    MusicNote as MusicIcon,
    Email as EmailIcon,
    SportsEsports as SteamIcon,
    MonitorHeart as HealthIcon,
    Event as EventIcon,
    NightsStay as NightsStayIcon,
    Brightness4 as BrightnessIcon,
    LightMode as LightModeIcon,
    DarkMode as DarkModeIcon,
    Sync as SyncIcon
} from '@mui/icons-material';
import { api, discoveryV2Api, mappingsApi, overlayApi } from '../services/api';

function OverlayProjection() {
    const [videos, setVideos] = useState([]);
    const [mappingScenes, setMappingScenes] = useState([]);
    const [backgroundType, setBackgroundType] = useState('video');
    const [selectedVideo, setSelectedVideo] = useState(null);
    const [selectedMapping, setSelectedMapping] = useState(null);
    const [overlayConfigs, setOverlayConfigs] = useState([]);
    const [selectedConfig, setSelectedConfig] = useState(null);
    const [projectionWindow, setProjectionWindow] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [configNameDialog, setConfigNameDialog] = useState(false);
    const [newConfigName, setNewConfigName] = useState('');
    const [brightness, setBrightness] = useState(100);
    const [brightnessLoading, setBrightnessLoading] = useState(false);
    const [castDevices, setCastDevices] = useState([]);
    const [selectedCastDeviceId, setSelectedCastDeviceId] = useState('');
    const [castSession, setCastSession] = useState(null);
    const [castSessions, setCastSessions] = useState([]);
    const [castLoading, setCastLoading] = useState(false);
    const [castDebugOpen, setCastDebugOpen] = useState(true);
    const [exportLoading, setExportLoading] = useState(false);
    const [exportDurationSeconds, setExportDurationSeconds] = useState(30);
    const navigate = useNavigate();
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
        steam_api_key: '',
        steam_id: '',
    });

    const widgetTemplates = {
        weather: {
            type: 'weather',
            size: { width: 400, height: 200 },
            config: { city: 'San Francisco', units: 'imperial' },
        },
        time: {
            type: 'time',
            size: { width: 300, height: 100 },
            config: { format: '12h', showSeconds: true, timezone: 'PST' },
        },
        transit: {
            type: 'transit',
            size: { width: 400, height: 200 },
            config: { stopName: 'Carl St & Stanyan St', routeFilter: 'N Judah' },
        },
        lights: {
            type: 'lights',
            size: { width: 120, height: 60 },
            config: {},
        },
        spotify: {
            type: 'spotify',
            size: { width: 420, height: 140 },
            config: { theme: 'minimal' },
        },
        apple_health: {
            type: 'apple_health',
            size: { width: 520, height: 300 },
            config: {
                metric: 'steps',
                days: 7,
                showTrend: true,
                showComparison: true,
                title: 'Apple Health',
            },
        },
        calendar: {
            type: 'calendar',
            size: { width: 420, height: 220 },
            config: { maxItems: 4 },
        },
        steam: {
            type: 'steam',
            size: { width: 360, height: 140 },
            config: { showAvatar: true },
        },
        dothebay_lgbtq: {
            type: 'dothebay_lgbtq',
            size: { width: 520, height: 320 },
            config: { title: 'DoTheBay LGBTQ', rotateMs: 6500 },
        },
    };
    
    useEffect(() => {
        fetchVideos();
        fetchMappingScenes();
        fetchBrightness();
        fetchCastDevices();
        fetchCastSessions();
        fetchGlobalApiConfigs();
    }, []);
    
    useEffect(() => {
        if (backgroundType === 'video' && selectedVideo) {
            fetchOverlayConfigs({ video_id: selectedVideo.id });
        } else if (backgroundType === 'mapping' && selectedMapping) {
            fetchOverlayConfigs({ mapping_scene_id: selectedMapping.id });
        }
    }, [selectedVideo, selectedMapping, backgroundType]);
    
    const fetchVideos = async () => {
        try {
            const response = await api.get('/videos');
            console.log("Videos API response:", response.data);
            setVideos(response.data.videos);
        } catch (error) {
            console.error('Error fetching videos:', error);
            setError('Failed to load videos');
        }
    };

    const fetchMappingScenes = async () => {
        try {
            const response = await mappingsApi.listScenes();
            setMappingScenes(response.data || []);
        } catch (error) {
            console.error('Error fetching mapping scenes:', error);
        }
    };
    
    const fetchOverlayConfigs = async (params) => {
        try {
            const response = await api.get('/overlay/configs', { params });
            setOverlayConfigs(response.data);
        } catch (error) {
            console.error('Error fetching overlay configs:', error);
            // If endpoint doesn't exist yet, just set empty array
            setOverlayConfigs([]);
        }
    };
    
    const fetchBrightness = async () => {
        try {
            const response = await api.get('/overlay/brightness');
            setBrightness(response.data.brightness);
        } catch (error) {
            console.error('Error fetching brightness:', error);
        }
    };

    const fetchCastDevices = async () => {
        try {
            const response = await discoveryV2Api.getDevices({
                casting_method: 'dlna',
            });
            const devices = Array.isArray(response.data) ? response.data : [];
            const sortedDevices = [...devices].sort((left, right) => {
                const leftRank = left.is_online ? 0 : 1;
                const rightRank = right.is_online ? 0 : 1;
                if (leftRank !== rightRank) {
                    return leftRank - rightRank;
                }
                return (left.friendly_name || left.name || '').localeCompare(right.friendly_name || right.name || '');
            });
            setCastDevices(sortedDevices);
            setSelectedCastDeviceId((current) => {
                if (current && sortedDevices.some((device) => device.id === current)) {
                    return current;
                }
                return sortedDevices[0]?.id || '';
            });
        } catch (error) {
            console.error('Error fetching cast devices:', error);
        }
    };

    const fetchCastSessions = async () => {
        try {
            const response = await overlayApi.listCastSessions();
            const sessions = Array.isArray(response.data) ? response.data : [];
            setCastSessions(sessions);
            const sessionForSelection = selectedConfig
                ? sessions.find((session) => !session.archived && session.config_id === selectedConfig.id) || null
                : sessions.find((session) => !session.archived) || null;
            setCastSession(sessionForSelection);
        } catch (error) {
            console.error('Error fetching cast sessions:', error);
        }
    };

    const fetchGlobalApiConfigs = async () => {
        try {
            const response = await overlayApi.getGlobalApiConfigs();
            setGlobalApiConfigs((current) => ({
                ...current,
                ...(response.data || {}),
            }));
        } catch (error) {
            console.error('Error fetching global API configs:', error);
        }
    };

    useEffect(() => {
        if (!castLoading && !castSession) {
            return undefined;
        }

        const intervalId = window.setInterval(() => {
            fetchCastSessions();
        }, 1500);

        return () => window.clearInterval(intervalId);
    }, [castLoading, castSession, selectedConfig]);
    
    const updateBrightness = async (value) => {
        setBrightness(value);
        setBrightnessLoading(true);
        try {
            await api.post(`/overlay/brightness?brightness=${value}`);
        } catch (error) {
            console.error('Error updating brightness:', error);
            setError('Failed to update brightness');
        } finally {
            setBrightnessLoading(false);
        }
    };
    
    const createNewConfig = async () => {
        const newConfig = {
            name: newConfigName || `Config ${new Date().toLocaleString()}`,
            background_type: backgroundType,
            video_id: backgroundType === 'video' ? selectedVideo.id : null,
            mapping_scene_id: backgroundType === 'mapping' ? selectedMapping.id : null,
            video_transform: { x: 0, y: 0, scale: 1, rotation: 0 },
            widgets: [
                {
                    id: 'weather-1',
                    type: 'weather',
                    position: { x: 50, y: 50 },
                    size: { width: 400, height: 200 },
                    config: {
                        city: 'San Francisco',
                        units: 'imperial'
                    },
                    visible: true
                },
                {
                    id: 'time-1',
                    type: 'time',
                    position: { x: 1470, y: 50 },
                    size: { width: 300, height: 100 },
                    config: {
                        format: '12h',
                        showSeconds: true,
                        timezone: 'PST'
                    },
                    visible: true
                },
                {
                    id: 'transit-1',
                    type: 'transit',
                    position: { x: 50, y: 830 },
                    size: { width: 400, height: 200 },
                    config: {
                        stopName: 'Carl St & Stanyan St',
                        routeFilter: 'N Judah'
                    },
                    visible: true
                },
                {
                    id: 'lights-1',
                    type: 'lights',
                    position: { x: 50, y: 950 },
                    size: { width: 120, height: 60 },
                    config: {},
                    visible: true,
                    rotation: 0
                },
                {
                    id: 'spotify-1',
                    type: 'spotify',
                    position: { x: 520, y: 50 },
                    size: { width: 420, height: 140 },
                    config: { theme: 'minimal' },
                    visible: true,
                    rotation: 0
                },
                {
                    id: 'calendar-1',
                    type: 'calendar',
                    position: { x: 980, y: 50 },
                    size: { width: 420, height: 220 },
                    config: { maxItems: 4 },
                    visible: true,
                    rotation: 0
                },
                {
                    id: 'dothebay-lgbtq-1',
                    type: 'dothebay_lgbtq',
                    position: { x: 40, y: 260 },
                    size: { width: 520, height: 320 },
                    config: { title: 'DoTheBay LGBTQ', rotateMs: 6500 },
                    visible: true,
                    rotation: 0
                },
                {
                    id: 'apple-health-1',
                    type: 'apple_health',
                    position: { x: 590, y: 320 },
                    size: { width: 520, height: 300 },
                    config: {
                        metric: 'steps',
                        days: 7,
                        showTrend: true,
                        showComparison: true,
                        title: 'Apple Health'
                    },
                    visible: true,
                    rotation: 0
                },
                {
                    id: 'steam-1',
                    type: 'steam',
                    position: { x: 520, y: 870 },
                    size: { width: 360, height: 140 },
                    config: { showAvatar: true },
                    visible: true,
                    rotation: 0
                }
            ],
            api_configs: {
                ...globalApiConfigs,
            }
        };
        
        try {
            const response = await api.post('/overlay/configs', newConfig);
            setOverlayConfigs([...overlayConfigs, response.data]);
            setSelectedConfig(response.data);
            setConfigNameDialog(false);
            setNewConfigName('');
        } catch (error) {
            console.error('Error creating config:', error);
            setError('Failed to create configuration');
        }
    };
    
    const updateConfig = useCallback(async (config) => {
        try {
            // Extract only the fields that the backend expects
            const updateData = {
                name: config.name,
                background_type: config.background_type,
                video_id: config.video_id,
                mapping_scene_id: config.mapping_scene_id,
                video_transform: config.video_transform,
                widgets: config.widgets,
                api_configs: config.api_configs
            };
            
            const response = await api.put(`/overlay/configs/${config.id}`, updateData);
            setOverlayConfigs((current) => current.map((entry) =>
                entry.id === config.id ? response.data : entry
            ));
            setSelectedConfig(response.data);
        } catch (error) {
            console.error('Error updating config:', error);
        }
    }, []);
    
    const deleteConfig = async (configId) => {
        try {
            await api.delete(`/overlay/configs/${configId}`);
            setOverlayConfigs(overlayConfigs.filter(c => c.id !== configId));
            if (selectedConfig?.id === configId) {
                setSelectedConfig(null);
            }
        } catch (error) {
            console.error('Error deleting config:', error);
            setError('Failed to delete configuration');
        }
    };

    const launchProjection = async (usePopupFeatures = true) => {
        if (!selectedConfig) return;
        if (backgroundType === 'video' && !selectedVideo) return;
        if (backgroundType === 'mapping' && !selectedMapping) return;
        
        setLoading(true);
        setError('');
        
        try {
            const windowUrl = `/backend-static/overlay_window.html?config_id=${selectedConfig.id}&controls=hidden`;
            const windowName = `overlay_projection_${selectedConfig.id}_${Date.now()}`;

            const projWindow = usePopupFeatures
                ? window.open(windowUrl, windowName, 'width=1920,height=1080')
                : window.open(windowUrl, windowName);

            if (!projWindow) {
                throw new Error('Projection window failed to open');
            }
            
            setProjectionWindow(projWindow);
            const initPayloadPromise = api.get('/overlay/window-init', {
                params: { config_id: selectedConfig.id }
            });
            const streamResponsePromise = api.post('/overlay/stream', {
                video_id: selectedVideo?.id || null,
                config_id: selectedConfig.id
            });
            
            // Function to send configuration
            const sendConfiguration = async () => {
                if (projWindow.closed) return; // Don't send if window was closed
                
                try {
                    const initPayloadResponse = await initPayloadPromise;
                    const streamResponse = await streamResponsePromise;
                    const initPayload = initPayloadResponse.data || {};
                    
                    projWindow.postMessage({
                        type: 'init',
                        config: initPayload.config || selectedConfig,
                        backgroundType: streamResponse.data.background_type || initPayload.background_type,
                        streamingUrl: streamResponse.data.streaming_url || initPayload.streaming_url,
                        mappingScene: streamResponse.data.mapping_scene || initPayload.mapping_scene || null,
                        videoPath: streamResponse.data.video_path || initPayload.video_path || selectedVideo?.path || null
                    }, '*');
                } catch (error) {
                    console.error('Error getting streaming URL:', error);
                    // Fallback to direct URL if backend fails
                    let streamingUrl = '';
                    let fallbackMappingScene = null;
                    if (selectedVideo && selectedVideo.path) {
                        streamingUrl = `http://localhost:9000/file_video/${selectedVideo.path.split('/').pop()}`;
                    }
                    if (backgroundType === 'mapping' && selectedMapping) {
                        fallbackMappingScene = {
                            ...selectedMapping,
                            masks: (selectedMapping.masks || []).map((mask) => ({
                                ...mask,
                                url: `/api/mappings/scenes/${selectedMapping.id}/masks/${mask.id}/file`,
                            })),
                        };
                    }
                    projWindow.postMessage({
                        type: 'init',
                        config: selectedConfig,
                        backgroundType,
                        streamingUrl: streamingUrl,
                        mappingScene: fallbackMappingScene,
                        videoPath: selectedVideo ? selectedVideo.path : ''
                    }, '*');
                }
            };
            
            // Send config immediately and then retry to ensure delivery
            setTimeout(sendConfiguration, 100);
            setTimeout(sendConfiguration, 500);
            setTimeout(sendConfiguration, 1000);
            
            setLoading(false);
        } catch (error) {
            console.error('Error launching projection:', error);
            setError('Failed to launch projection window');
            setLoading(false);
        }
    };

    const startProjectorCast = async () => {
        if (!selectedConfig || !selectedCastDeviceId) {
            return;
        }

        setCastLoading(true);
        setError('');
        try {
            const response = await overlayApi.startCast({
                device_id: selectedCastDeviceId,
                config_id: selectedConfig.id,
                overlay_base_url: `${window.location.protocol}//${window.location.host}`,
                controls_hidden: true,
                frame_rate: 15,
            });
            setCastSession(response.data);
        } catch (error) {
            console.error('Error starting projector cast:', error);
            await fetchCastSessions();
            setError(error.response?.data?.detail || 'Failed to start projector cast');
        } finally {
            setCastLoading(false);
        }
    };

    const stopProjectorCast = async () => {
        if (!castSession?.session_id) {
            return;
        }

        setCastLoading(true);
        setError('');
        try {
            await overlayApi.stopCastSession(castSession.session_id);
            setCastSession(null);
        } catch (error) {
            console.error('Error stopping projector cast:', error);
            setError(error.response?.data?.detail || 'Failed to stop projector cast');
        } finally {
            setCastLoading(false);
        }
    };

    const exportProjectionMp4 = async () => {
        if (!selectedConfig) {
            return;
        }

        setExportLoading(true);
        setError('');
        try {
            const response = await overlayApi.exportMp4({
                config_id: selectedConfig.id,
                overlay_base_url: `${window.location.protocol}//${window.location.host}`,
                controls_hidden: true,
                hide_widgets: true,
                viewport_width: 1280,
                viewport_height: 720,
                capture_width: 1280,
                capture_height: 720,
                quality: 80,
                frame_rate: 24,
                duration_seconds: exportDurationSeconds,
                bitrate_kbps: 2500,
            });
            const blob = new Blob([response.data], { type: 'video/mp4' });
            const downloadUrl = window.URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = downloadUrl;
            anchor.download = `overlay_config_${selectedConfig.id}_${exportDurationSeconds}s.mp4`;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            console.error('Error exporting projection mp4:', error);
            setError(error.response?.data?.detail || 'Failed to export projection mp4');
        } finally {
            setExportLoading(false);
        }
    };
    
    // Listen for updates from projection window
    useEffect(() => {
        const handleMessage = async (event) => {
            if (event.data.type === 'updateConfig' && selectedConfig) {
                updateConfig(event.data.config);
            }
        };
        
        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [selectedConfig, updateConfig]);

    useEffect(() => {
        fetchCastSessions();
    }, [selectedConfig]);
    
    const addWidget = (type) => {
        if (!selectedConfig || !widgetTemplates[type]) {
            return;
        }
        const template = widgetTemplates[type];
        const count = selectedConfig.widgets.filter((widget) => widget.type === type).length + 1;
        const updatedConfig = {
            ...selectedConfig,
            widgets: [
                ...selectedConfig.widgets,
                {
                    id: `${type}-${count}`,
                    type: template.type,
                    position: { x: 120 + (count * 20), y: 120 + (count * 20) },
                    size: template.size,
                    config: template.config,
                    visible: true,
                    rotation: 0,
                }
            ]
        };
        updateConfig(updatedConfig);
    };

    const getWidgetIcon = (type) => {
        switch(type) {
            case 'weather': return <WeatherIcon />;
            case 'time': return <TimeIcon />;
            case 'transit': return <TransitIcon />;
            case 'lights': return <NightsStayIcon />;
            case 'spotify': return <MusicIcon />;
            case 'dothebay_lgbtq': return <EventIcon />;
            case 'apple_health': return <HealthIcon />;
            case 'calendar': return <EmailIcon />;
            case 'steam': return <SteamIcon />;
            default: return <SettingsIcon />;
        }
    };

    const removeWidget = (widgetId) => {
        if (!selectedConfig) {
            return;
        }
        const updatedConfig = {
            ...selectedConfig,
            widgets: selectedConfig.widgets.filter((widget) => widget.id !== widgetId),
        };
        updateConfig(updatedConfig);
    };
    
    return (
        <Grid container spacing={3}>
            <Grid item xs={12}>
                <Paper sx={{ p: 3 }}>
                    <Typography variant="h4" gutterBottom>
                        Overlay Projection
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        Select a background source and configure live information overlays for projection via AirPlay
                    </Typography>
                </Paper>
            </Grid>
            
            {/* Background Selection */}
            <Grid item xs={12} md={6}>
                <Card>
                    <CardHeader 
                        title="Background Selection"
                        avatar={<VideoIcon />}
                    />
                    <CardContent>
                        <FormControl fullWidth sx={{ mb: 2 }}>
                            <InputLabel>Background Type</InputLabel>
                            <Select
                                value={backgroundType}
                                label="Background Type"
                                onChange={(e) => {
                                    setBackgroundType(e.target.value);
                                    setSelectedConfig(null);
                                }}
                            >
                                <MenuItem value="video">Video</MenuItem>
                                <MenuItem value="mapping">Mapping</MenuItem>
                            </Select>
                        </FormControl>

                        {backgroundType === 'video' ? (
                        <FormControl fullWidth>
                            <InputLabel>Select Video</InputLabel>
                            <Select
                                value={selectedVideo?.id || ''}
                                onChange={(e) => {
                                    const video = videos.find(v => v.id === e.target.value);
                                    setSelectedVideo(video);
                                    setSelectedMapping(null);
                                    setSelectedConfig(null);
                                }}
                                label="Select Video"
                            >
                                <MenuItem value="">
                                    <em>Choose a video...</em>
                                </MenuItem>
                                {videos.map(video => (
                                    <MenuItem key={video.id} value={video.id}>
                                        {video.name}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        ) : (
                        <FormControl fullWidth>
                            <InputLabel>Select Mapping</InputLabel>
                            <Select
                                value={selectedMapping?.id || ''}
                                onChange={(e) => {
                                    const mapping = mappingScenes.find(scene => scene.id === e.target.value);
                                    setSelectedMapping(mapping);
                                    setSelectedVideo(null);
                                    setSelectedConfig(null);
                                }}
                                label="Select Mapping"
                            >
                                <MenuItem value="">
                                    <em>Choose a mapping...</em>
                                </MenuItem>
                                {mappingScenes.map(scene => (
                                    <MenuItem key={scene.id} value={scene.id}>
                                        {scene.name}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        )}
                        
                        {backgroundType === 'video' && selectedVideo && (
                            <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                                <Typography variant="body2">
                                    <strong>File:</strong> {selectedVideo.path}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>Duration:</strong> {selectedVideo.duration || 'Unknown'}
                                </Typography>
                            </Box>
                        )}

                        {backgroundType === 'mapping' && selectedMapping && (
                            <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                                <Typography variant="body2">
                                    <strong>Masks:</strong> {selectedMapping.masks?.length || 0}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>Groups:</strong> {selectedMapping.groups?.length || 0}
                                </Typography>
                            </Box>
                        )}
                    </CardContent>
                </Card>
            </Grid>
            
            {/* Configuration Selection */}
            <Grid item xs={12} md={6}>
                <Card>
                    <CardHeader 
                        title="Overlay Configurations"
                        action={
                            <Tooltip title="Create new configuration">
                                <span>
                                    <IconButton 
                                        onClick={() => setConfigNameDialog(true)}
                                        disabled={backgroundType === 'video' ? !selectedVideo : !selectedMapping}
                                    >
                                        <AddIcon />
                                    </IconButton>
                                </span>
                            </Tooltip>
                        }
                    />
                    <CardContent>
                        {backgroundType === 'video' && !selectedVideo ? (
                            <Alert severity="info">
                                Select a video to view configurations
                            </Alert>
                        ) : backgroundType === 'mapping' && !selectedMapping ? (
                            <Alert severity="info">
                                Select a mapping to view configurations
                            </Alert>
                        ) : overlayConfigs.length === 0 ? (
                            <Alert severity="info">
                                No configurations yet. Click + to create one.
                            </Alert>
                        ) : (
                            <List>
                                {overlayConfigs.map(config => (
                                    <ListItem
                                        key={config.id}
                                        button
                                        selected={selectedConfig?.id === config.id}
                                        onClick={() => setSelectedConfig(config)}
                                    >
                                        <ListItemText
                                            primary={config.name}
                                            secondary={`${config.widgets.filter(w => w.visible).length} active widgets`}
                                        />
                                        <ListItemSecondaryAction>
                                            <IconButton
                                                edge="end"
                                                onClick={() => deleteConfig(config.id)}
                                            >
                                                <DeleteIcon />
                                            </IconButton>
                                        </ListItemSecondaryAction>
                                    </ListItem>
                                ))}
                            </List>
                        )}
                    </CardContent>
                </Card>
            </Grid>
            
            {/* Widget Configuration */}
            {selectedConfig && (
                <Grid item xs={12}>
                    <Card>
                        <CardHeader 
                            title="Widget Configuration"
                            action={
                                <Stack direction="row" spacing={1}>
                                    <Button
                                        startIcon={<SettingsIcon />}
                                        onClick={() => navigate('/settings')}
                                    >
                                        API Settings
                                    </Button>
                                </Stack>
                            }
                        />
                        <CardContent>
                            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
                                {['weather', 'time', 'transit', 'lights', 'spotify', 'dothebay_lgbtq', 'apple_health', 'calendar', 'steam'].map((type) => (
                                    <Button key={type} size="small" variant="outlined" onClick={() => addWidget(type)} startIcon={getWidgetIcon(type)}>
                                        Add {type}
                                    </Button>
                                ))}
                            </Stack>
                            <List>
                                {selectedConfig.widgets.map(widget => (
                                    <ListItem key={widget.id}>
                                        <ListItemIcon>
                                            {getWidgetIcon(widget.type)}
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={widget.type.charAt(0).toUpperCase() + widget.type.slice(1)}
                                            secondary={
                                                <Box>
                                                    Position: ({widget.position.x}, {widget.position.y}) • 
                                                    Size: {widget.size.width}x{widget.size.height}
                                                </Box>
                                            }
                                        />
                                        <ListItemSecondaryAction>
                                            <IconButton onClick={() => removeWidget(widget.id)} color="error">
                                                <DeleteIcon />
                                            </IconButton>
                                        </ListItemSecondaryAction>
                                    </ListItem>
                                ))}
                            </List>
                        </CardContent>
                    </Card>
                </Grid>
            )}
            
            {/* Launch Controls */}
            <Grid item xs={12}>
                <Paper sx={{ p: 3 }}>
                    {/* Brightness Control */}
                    <Box sx={{ mb: 4 }}>
                        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <BrightnessIcon />
                            Brightness Control
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            Adjust brightness for all overlay projections
                        </Typography>
                        
                        <Box sx={{ px: 2 }}>
                            <Stack spacing={2} direction="row" sx={{ mb: 2 }} alignItems="center">
                                <DarkModeIcon />
                                <Slider
                                    value={brightness}
                                    onChange={(e, value) => updateBrightness(value)}
                                    aria-labelledby="brightness-slider"
                                    valueLabelDisplay="auto"
                                    step={5}
                                    marks={[
                                        { value: 0, label: '0%' },
                                        { value: 25, label: '25%' },
                                        { value: 50, label: '50%' },
                                        { value: 75, label: '75%' },
                                        { value: 100, label: '100%' }
                                    ]}
                                    min={0}
                                    max={100}
                                    disabled={brightnessLoading}
                                    sx={{
                                        '& .MuiSlider-valueLabel': {
                                            backgroundColor: 'primary.main',
                                        }
                                    }}
                                />
                                <LightModeIcon />
                            </Stack>
                            
                            <Stack direction="row" spacing={1} justifyContent="center">
                                <Button
                                    variant="outlined"
                                    size="small"
                                    onClick={() => updateBrightness(0)}
                                    disabled={brightnessLoading}
                                >
                                    Lights Off
                                </Button>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    onClick={() => updateBrightness(25)}
                                    disabled={brightnessLoading}
                                >
                                    Dim
                                </Button>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    onClick={() => updateBrightness(75)}
                                    disabled={brightnessLoading}
                                >
                                    Normal
                                </Button>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    onClick={() => updateBrightness(100)}
                                    disabled={brightnessLoading}
                                >
                                    Full
                                </Button>
                            </Stack>
                        </Box>
                    </Box>
                    
                    {/* Sync Button */}
                    <Box sx={{ mb: 2, display: 'flex', justifyContent: 'center' }}>
                        <Button
                            variant="outlined"
                            startIcon={<SyncIcon />}
                            onClick={async () => {
                                try {
                                    await api.post('/overlay/sync', null, {
                                        params: {
                                            triggered_by: 'manual',
                                            video_name: selectedVideo?.name
                                        }
                                    });
                                    // Visual feedback
                                    setError('');
                                } catch (error) {
                                    console.error('Sync error:', error);
                                    setError('Failed to sync overlays');
                                }
                            }}
                        >
                            Sync All Overlays
                        </Button>
                    </Box>
                    
                    {/* Launch Button */}
                    <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', alignItems: 'center' }}>
                        <Button
                            variant="contained"
                            color="primary"
                            size="large"
                            startIcon={loading ? <CircularProgress size={20} /> : <LaunchIcon />}
                            onClick={() => launchProjection(true)}
                            disabled={(!selectedConfig) || (backgroundType === 'video' ? !selectedVideo : !selectedMapping) || loading}
                        >
                            Launch Projection Window
                        </Button>
                        <Button
                            variant="outlined"
                            color="primary"
                            size="large"
                            startIcon={loading ? <CircularProgress size={20} /> : <LaunchIcon />}
                            onClick={() => launchProjection(false)}
                            disabled={(!selectedConfig) || (backgroundType === 'video' ? !selectedVideo : !selectedMapping) || loading}
                        >
                            Open Projection Tab
                        </Button>
                        
                        {projectionWindow && !projectionWindow.closed && (
                            <Chip
                                label="Projection Active"
                                color="success"
                                onDelete={() => {
                                    projectionWindow.close();
                                    setProjectionWindow(null);
                                }}
                            />
                        )}
                    </Box>

                    <Divider sx={{ my: 3 }} />

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <Typography variant="h6">
                            DLNA Projector Cast
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Render the selected overlay config in a headless browser and cast the live relay stream to a discovered DLNA renderer.
                        </Typography>

                        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
                            <TextField
                                label="Export Seconds"
                                type="number"
                                size="small"
                                value={exportDurationSeconds}
                                onChange={(e) => setExportDurationSeconds(Math.max(1, Number(e.target.value) || 1))}
                                inputProps={{ min: 1, max: 900 }}
                                sx={{ width: 180 }}
                                disabled={exportLoading}
                            />
                            <Button
                                variant="outlined"
                                onClick={exportProjectionMp4}
                                disabled={!selectedConfig || exportLoading}
                            >
                                {exportLoading ? 'Exporting MP4...' : 'Export MP4'}
                            </Button>
                        </Box>

                        <FormControl fullWidth disabled={castLoading}>
                            <InputLabel>Target Projector</InputLabel>
                            <Select
                                value={selectedCastDeviceId}
                                label="Target Projector"
                                onChange={(e) => setSelectedCastDeviceId(e.target.value)}
                            >
                                <MenuItem value="">
                                    <em>Choose a DLNA projector...</em>
                                </MenuItem>
                                {castDevices.map((device) => (
                                    <MenuItem key={device.id} value={device.id}>
                                        {(device.friendly_name || device.name)}{device.is_online ? ' - online' : ' - offline'}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap' }}>
                            <Button
                                variant="contained"
                                color="secondary"
                                startIcon={castLoading ? <CircularProgress size={20} /> : <LaunchIcon />}
                                onClick={startProjectorCast}
                                disabled={!selectedConfig || !selectedCastDeviceId || castLoading}
                            >
                                Cast To Projector
                            </Button>
                            <Button
                                variant="outlined"
                                color="secondary"
                                onClick={stopProjectorCast}
                                disabled={!castSession || castLoading}
                            >
                                Stop Cast
                            </Button>
                            <Button
                                variant="text"
                                onClick={fetchCastDevices}
                                disabled={castLoading}
                            >
                                Refresh Devices
                            </Button>
                        </Box>

                        {castSession && (
                            <Box sx={{ p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                                <Typography variant="body2">
                                    <strong>Status:</strong> {castSession.status}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>Current Step:</strong> {castSession.current_step}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>Active Clients:</strong> {castSession.active_clients}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>FFmpeg Speed:</strong> {castSession.ffmpeg_speed ? `${castSession.ffmpeg_speed.toFixed(2)}x` : 'n/a'}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>Encoder FPS:</strong> {castSession.ffmpeg_fps ? castSession.ffmpeg_fps.toFixed(1) : 'n/a'}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>Bitrate:</strong> {castSession.ffmpeg_bitrate_kbps ? `${Math.round(castSession.ffmpeg_bitrate_kbps)} kbps` : 'n/a'}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>Relay:</strong> {castSession.relay_url}
                                </Typography>
                                <Typography variant="body2">
                                    <strong>Overlay URL:</strong> {castSession.overlay_url}
                                </Typography>
                                {castSession.error && (
                                    <Typography variant="body2" color="error">
                                        <strong>Error:</strong> {castSession.error}
                                    </Typography>
                                )}
                                <Button
                                    size="small"
                                    sx={{ mt: 1 }}
                                    onClick={() => setCastDebugOpen((current) => !current)}
                                >
                                    {castDebugOpen ? 'Hide Cast Debug' : 'Show Cast Debug'}
                                </Button>
                                {castDebugOpen && (
                                    <Box sx={{ mt: 1, p: 1.5, bgcolor: '#111', color: '#d7f7d7', borderRadius: 1, fontFamily: 'monospace', fontSize: 12, maxHeight: 220, overflow: 'auto' }}>
                                        {(castSession.debug_log || []).length > 0 ? (
                                            (castSession.debug_log || []).map((entry, index) => (
                                                <Box key={`${entry}-${index}`}>{entry}</Box>
                                            ))
                                        ) : (
                                            <Box>No cast debug entries yet.</Box>
                                        )}
                                    </Box>
                                )}
                            </Box>
                        )}

                        {castSessions.length > 0 && (
                            <Box sx={{ mt: 2 }}>
                                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                                    Overlay Capture Sessions
                                </Typography>
                                <List dense>
                                    {castSessions.map((session) => (
                                        <ListItem
                                            key={session.session_id}
                                            sx={{
                                                mb: 1,
                                                borderRadius: 1,
                                                bgcolor: session.archived ? 'grey.100' : 'grey.50',
                                                alignItems: 'flex-start',
                                            }}
                                        >
                                            <ListItemText
                                                primary={`${session.device_id} • config ${session.config_id}`}
                                                secondary={
                                                    <Box component="span" sx={{ display: 'block' }}>
                                                        <Box component="span" sx={{ display: 'block' }}>
                                                            Status: {session.status} • Step: {session.current_step} • Clients: {session.active_clients}
                                                        </Box>
                                                        <Box component="span" sx={{ display: 'block' }}>
                                                            Speed: {session.ffmpeg_speed ? `${session.ffmpeg_speed.toFixed(2)}x` : 'n/a'} • FPS: {session.ffmpeg_fps ? session.ffmpeg_fps.toFixed(1) : 'n/a'} • Bitrate: {session.ffmpeg_bitrate_kbps ? `${Math.round(session.ffmpeg_bitrate_kbps)} kbps` : 'n/a'}
                                                        </Box>
                                                        <Box component="span" sx={{ display: 'block' }}>
                                                            Relay: {session.relay_url}
                                                        </Box>
                                                        {session.error && (
                                                            <Box component="span" sx={{ display: 'block', color: 'error.main' }}>
                                                                Error: {session.error}
                                                            </Box>
                                                        )}
                                                        <Box component="span" sx={{ display: 'block', mt: 1, fontFamily: 'monospace', fontSize: 12, maxHeight: 120, overflow: 'auto', backgroundColor: '#111', color: '#d7f7d7', p: 1, borderRadius: 1 }}>
                                                            {(session.debug_log || []).slice(-8).map((entry, index) => (
                                                                <Box component="span" key={`${session.session_id}-${index}`} sx={{ display: 'block' }}>
                                                                    {entry}
                                                                </Box>
                                                            ))}
                                                        </Box>
                                                    </Box>
                                                }
                                            />
                                            <ListItemSecondaryAction>
                                                {!session.archived && (
                                                    <Button
                                                        size="small"
                                                        color="secondary"
                                                        onClick={() => overlayApi.stopCastSession(session.session_id).then(fetchCastSessions)}
                                                    >
                                                        Stop
                                                    </Button>
                                                )}
                                            </ListItemSecondaryAction>
                                        </ListItem>
                                    ))}
                                </List>
                            </Box>
                        )}
                    </Box>
                    
                    {error && (
                        <Alert severity="error" sx={{ mt: 2 }}>
                            {error}
                        </Alert>
                    )}
                    
                    <Alert severity="info" sx={{ mt: 2 }}>
                        After launching, use AirPlay to extend the projection window to your projector
                    </Alert>
                </Paper>
            </Grid>
            
            {/* Config Name Dialog */}
            <Dialog open={configNameDialog} onClose={() => setConfigNameDialog(false)}>
                <DialogTitle>New Configuration</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Configuration Name"
                        fullWidth
                        variant="outlined"
                        value={newConfigName}
                        onChange={(e) => setNewConfigName(e.target.value)}
                        placeholder="e.g., Living Room Display"
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setConfigNameDialog(false)}>Cancel</Button>
                    <Button onClick={createNewConfig} variant="contained">Create</Button>
                </DialogActions>
            </Dialog>
        </Grid>
    );
}

export default OverlayProjection;
