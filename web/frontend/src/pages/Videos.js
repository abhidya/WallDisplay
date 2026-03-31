import React, { useState, useEffect, useCallback } from 'react';
import {
  Grid,
  Paper,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  CardMedia,
  CardHeader,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  TextField,
  CircularProgress,
  Box,
  Divider,
  Alert,
  Snackbar,
  LinearProgress,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Chip,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Refresh as RefreshIcon,
  VideoLibrary as VideoIcon,
  PlayArrow as PlayIcon,
  Folder as FolderIcon,
  Upload as UploadIcon
} from '@mui/icons-material';
import { mediaLibraryApi, videoApi } from '../services/api';
import { useNavigate } from 'react-router-dom';

function Videos() {
  const navigate = useNavigate();
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openAddDialog, setOpenAddDialog] = useState(false);
  const [openDeleteDialog, setOpenDeleteDialog] = useState(false);
  const [openScanDialog, setOpenScanDialog] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [newVideo, setNewVideo] = useState({
    name: '',
    path: '',
  });
  const [scanDirectory, setScanDirectory] = useState('');
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success'
  });
  const [scanning, setScanning] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [mediaDirectories, setMediaDirectories] = useState([]);
  const [openDirectoryDialog, setOpenDirectoryDialog] = useState(false);
  const [openDirectoryBrowserDialog, setOpenDirectoryBrowserDialog] = useState(false);
  const [directoryBrowserLoading, setDirectoryBrowserLoading] = useState(false);
  const [directoryBrowserError, setDirectoryBrowserError] = useState('');
  const [directoryBrowserCurrentPath, setDirectoryBrowserCurrentPath] = useState('');
  const [directoryBrowserParentPath, setDirectoryBrowserParentPath] = useState(null);
  const [directoryBrowserEntries, setDirectoryBrowserEntries] = useState([]);
  const [openMediaListDialog, setOpenMediaListDialog] = useState(false);
  const [openMediaChannelDialog, setOpenMediaChannelDialog] = useState(false);
  const [directoryForm, setDirectoryForm] = useState({
    name: '',
    path: '',
    category: 'background',
  });
  const [mediaLists, setMediaLists] = useState([]);
  const [mediaChannels, setMediaChannels] = useState([]);
  const [editingMediaListId, setEditingMediaListId] = useState(null);
  const [editingMediaChannelId, setEditingMediaChannelId] = useState(null);
  const [mediaListForm, setMediaListForm] = useState({
    name: '',
    category: 'background',
    video_ids: [],
    playback_mode: 'sequence',
    shuffle: false,
    loop: true,
  });
  const [mediaChannelForm, setMediaChannelForm] = useState({
    name: '',
    media_list_id: '',
    current_index: 0,
  });

  const getPreprocessingStatusMeta = (status) => {
    switch (status) {
      case 'ready':
        return { label: 'Processed', color: 'success' };
      case 'processing':
        return { label: 'Processing', color: 'warning' };
      case 'failed':
        return { label: 'Failed', color: 'error' };
      case 'pending':
      default:
        return { label: 'Unprocessed', color: 'default' };
    }
  };

  const processingCounts = videos.reduce((counts, video) => {
    const status = video.preprocessing_status || 'pending';
    counts.total += 1;
    counts[status] = (counts[status] || 0) + 1;
    return counts;
  }, { total: 0, pending: 0, processing: 0, ready: 0, failed: 0 });

  const hasActivePreprocessing = videos.some((video) => {
    const status = video.preprocessing_status || 'pending';
    return status === 'pending' || status === 'processing';
  });

  const fetchVideos = useCallback(async ({ showLoader = true } = {}) => {
    try {
      if (showLoader) {
        setLoading(true);
        setError(null);
      }
      const response = await videoApi.getVideos(categoryFilter === 'all' ? {} : { category: categoryFilter });
      setVideos(response.data.videos);
      if (showLoader) {
        setLoading(false);
      }
    } catch (err) {
      console.error('Error fetching videos:', err);
      if (showLoader) {
        setError('Failed to load videos. Please try again later.');
        setLoading(false);
      }
    }
  }, [categoryFilter]);

  useEffect(() => {
    fetchVideos();
    fetchMediaDirectories();
    fetchMediaLists();
    fetchMediaChannels();
  }, [fetchVideos]);

  useEffect(() => {
    if (!hasActivePreprocessing) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      fetchVideos({ showLoader: false });
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, [fetchVideos, hasActivePreprocessing]);

  const fetchMediaDirectories = async () => {
    try {
      const response = await mediaLibraryApi.listDirectories();
      setMediaDirectories(response.data || []);
    } catch (err) {
      console.error('Error fetching media directories:', err);
    }
  };

  const fetchMediaLists = async () => {
    try {
      const response = await mediaLibraryApi.listMediaLists();
      setMediaLists(response.data || []);
    } catch (err) {
      console.error('Error fetching media lists:', err);
    }
  };

  const fetchMediaChannels = async () => {
    try {
      const response = await mediaLibraryApi.listMediaChannels();
      setMediaChannels(response.data || []);
    } catch (err) {
      console.error('Error fetching media channels:', err);
    }
  };

  const handleAddVideo = async () => {
    try {
      await videoApi.createVideo(newVideo);
      setOpenAddDialog(false);
      setNewVideo({
        name: '',
        path: '',
      });
      setSnackbar({
        open: true,
        message: 'Video added successfully',
        severity: 'success'
      });
      fetchVideos();
    } catch (err) {
      console.error('Error adding video:', err);
      setSnackbar({
        open: true,
        message: 'Failed to add video',
        severity: 'error'
      });
    }
  };

  const handleDeleteVideo = async () => {
    try {
      await videoApi.deleteVideo(selectedVideo.id);
      setOpenDeleteDialog(false);
      setSelectedVideo(null);
      setSnackbar({
        open: true,
        message: 'Video deleted successfully',
        severity: 'success'
      });
      fetchVideos();
    } catch (err) {
      console.error('Error deleting video:', err);
      setSnackbar({
        open: true,
        message: 'Failed to delete video',
        severity: 'error'
      });
    }
  };

  const handleScanDirectory = async () => {
    try {
      setScanning(true);
      const response = await videoApi.scanDirectory(scanDirectory);
      setOpenScanDialog(false);
      setScanDirectory('');
      setSnackbar({
        open: true,
        message: `Scan completed. Found ${response.data.videos.length} videos.`,
        severity: 'success'
      });
      fetchVideos();
    } catch (err) {
      console.error('Error scanning directory:', err);
      setSnackbar({
        open: true,
        message: 'Failed to scan directory',
        severity: 'error'
      });
    } finally {
      setScanning(false);
    }
  };

  const handleCreateDirectory = async () => {
    try {
      await mediaLibraryApi.createDirectory(directoryForm);
      setOpenDirectoryDialog(false);
      setDirectoryForm({ name: '', path: '', category: 'background' });
      fetchMediaDirectories();
      setSnackbar({
        open: true,
        message: 'Media directory saved',
        severity: 'success'
      });
    } catch (err) {
      console.error('Error creating media directory:', err);
      setSnackbar({
        open: true,
        message: 'Failed to save media directory',
        severity: 'error'
      });
    }
  };

  const handleCreateMediaList = async () => {
    try {
      if (editingMediaListId) {
        await mediaLibraryApi.updateMediaList(editingMediaListId, mediaListForm);
      } else {
        await mediaLibraryApi.createMediaList(mediaListForm);
      }
      setOpenMediaListDialog(false);
      setEditingMediaListId(null);
      setMediaListForm({
        name: '',
        category: 'background',
        video_ids: [],
        playback_mode: 'sequence',
        shuffle: false,
        loop: true,
      });
      fetchMediaLists();
      setSnackbar({
        open: true,
        message: editingMediaListId ? 'Media list updated' : 'Media list created',
        severity: 'success'
      });
    } catch (err) {
      console.error('Error creating media list:', err);
      setSnackbar({
        open: true,
        message: 'Failed to create media list',
        severity: 'error'
      });
    }
  };

  const handleCreateMediaChannel = async () => {
    try {
      const payload = {
        ...mediaChannelForm,
        media_list_id: Number(mediaChannelForm.media_list_id),
      };
      if (editingMediaChannelId) {
        await mediaLibraryApi.updateMediaChannel(editingMediaChannelId, payload);
      } else {
        await mediaLibraryApi.createMediaChannel(payload);
      }
      setOpenMediaChannelDialog(false);
      setEditingMediaChannelId(null);
      setMediaChannelForm({
        name: '',
        media_list_id: '',
        current_index: 0,
      });
      fetchMediaChannels();
      setSnackbar({
        open: true,
        message: editingMediaChannelId ? 'Media channel updated' : 'Media channel created',
        severity: 'success'
      });
    } catch (err) {
      console.error('Error creating media channel:', err);
      setSnackbar({
        open: true,
        message: 'Failed to create media channel',
        severity: 'error'
      });
    }
  };

  const handleScanSavedDirectory = async (directory) => {
    try {
      setScanning(true);
      const response = await mediaLibraryApi.scanDirectory(directory.id);
      setSnackbar({
        open: true,
        message: `Scanned ${directory.name}. Found ${response.data.count} new videos.`,
        severity: 'success'
      });
      fetchVideos();
    } catch (err) {
      console.error('Error scanning saved directory:', err);
      setSnackbar({
        open: true,
        message: 'Failed to scan saved media directory',
        severity: 'error'
      });
    } finally {
      setScanning(false);
    }
  };

  const handleDeleteSavedDirectory = async (directory) => {
    try {
      await mediaLibraryApi.deleteDirectory(directory.id);
      setMediaDirectories((current) => current.filter((item) => item.id !== directory.id));
      setSnackbar({
        open: true,
        message: `Deleted media folder "${directory.name}"`,
        severity: 'success'
      });
    } catch (err) {
      console.error('Error deleting media directory:', err);
      setSnackbar({
        open: true,
        message: err.response?.data?.detail || 'Failed to delete media folder',
        severity: 'error'
      });
    }
  };

  const handleUploadVideo = async () => {
    if (!uploadFile) return;

    // Validate file size (500MB limit)
    const maxSize = 500 * 1024 * 1024; // 500MB in bytes
    if (uploadFile.size > maxSize) {
      setSnackbar({
        open: true,
        message: `File size exceeds 500MB limit. Your file is ${(uploadFile.size / 1024 / 1024).toFixed(2)}MB`,
        severity: 'error'
      });
      return;
    }

    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('name', uploadFile.name.split('.')[0]);

    setIsUploading(true);
    setUploadProgress(0);

    try {
      await videoApi.uploadVideo(formData, {
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percentCompleted);
        }
      });
      
      setSnackbar({
        open: true,
        message: 'Video uploaded successfully',
        severity: 'success'
      });
      setUploadFile(null);
      setUploadProgress(0);
      fetchVideos();
    } catch (err) {
      console.error('Error uploading video:', err);
      
      // Extract error message from response
      let errorMessage = 'Failed to upload video';
      if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setSnackbar({
        open: true,
        message: errorMessage,
        severity: 'error'
      });
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setNewVideo(prev => ({
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

  const getDirectoryLabelFromPath = (path) => {
    const normalized = (path || '').replace(/\\/g, '/');
    const parts = normalized.split('/').filter(Boolean);
    return parts[parts.length - 1] || path || '';
  };

  const loadDirectoryBrowser = async (path = null) => {
    setDirectoryBrowserLoading(true);
    setDirectoryBrowserError('');
    try {
      const response = await mediaLibraryApi.browseDirectories(path);
      setDirectoryBrowserCurrentPath(response.data.current_path || '');
      setDirectoryBrowserParentPath(response.data.parent_path || null);
      setDirectoryBrowserEntries(response.data.directories || []);
    } catch (err) {
      console.error('Error browsing directories:', err);
      setDirectoryBrowserError(err.response?.data?.detail || 'Failed to browse directories');
    } finally {
      setDirectoryBrowserLoading(false);
    }
  };

  const handleOpenDirectoryBrowser = () => {
    setOpenDirectoryBrowserDialog(true);
    loadDirectoryBrowser(directoryForm.path || null);
  };

  const handleSelectBrowsedDirectory = () => {
    setDirectoryForm((current) => ({
      ...current,
      path: directoryBrowserCurrentPath,
      name: current.name || getDirectoryLabelFromPath(directoryBrowserCurrentPath),
    }));
    setOpenDirectoryBrowserDialog(false);
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'Unknown';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return 'Unknown';
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 Byte';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
    return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
  };

  const resetMediaListDialog = () => {
    setEditingMediaListId(null);
    setMediaListForm({
      name: '',
      category: 'background',
      video_ids: [],
      playback_mode: 'sequence',
      shuffle: false,
      loop: true,
    });
    setOpenMediaListDialog(false);
  };

  const resetMediaChannelDialog = () => {
    setEditingMediaChannelId(null);
    setMediaChannelForm({
      name: '',
      media_list_id: '',
      current_index: 0,
    });
    setOpenMediaChannelDialog(false);
  };

  const openEditMediaListDialog = (list) => {
    setEditingMediaListId(list.id);
    setMediaListForm({
      name: list.name || '',
      category: list.category || 'background',
      video_ids: list.video_ids || [],
      playback_mode: list.playback_mode || 'sequence',
      shuffle: Boolean(list.shuffle),
      loop: list.loop !== false,
    });
    setOpenMediaListDialog(true);
  };

  const openEditMediaChannelDialog = (channel) => {
    setEditingMediaChannelId(channel.id);
    setMediaChannelForm({
      name: channel.name || '',
      media_list_id: channel.media_list_id || '',
      current_index: channel.current_index || 0,
    });
    setOpenMediaChannelDialog(true);
  };

  const addVideoToMediaList = (video) => {
    const targetList = mediaLists.find((list) => list.category === video.category) || mediaLists[0];
    if (targetList) {
      const nextIds = Array.from(new Set([...(targetList.video_ids || []), video.id]));
      openEditMediaListDialog({ ...targetList, video_ids: nextIds });
      return;
    }

    setEditingMediaListId(null);
    setMediaListForm({
      name: `${video.category || 'background'} list`,
      category: video.category || 'background',
      video_ids: [video.id],
      playback_mode: 'sequence',
      shuffle: false,
      loop: true,
    });
    setOpenMediaListDialog(true);
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
        <Button variant="contained" onClick={fetchVideos}>
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
          <Typography variant="h4">Videos</Typography>
          <Box>
            <Button
              variant="contained"
              color="secondary"
              startIcon={<FolderIcon />}
              onClick={() => setOpenDirectoryDialog(true)}
              sx={{ mr: 1 }}
            >
              Add Media Folder
            </Button>
            <Button
              variant="contained"
              color="secondary"
              startIcon={<AddIcon />}
              onClick={() => {
                setEditingMediaListId(null);
                setMediaListForm({
                  name: '',
                  category: 'background',
                  video_ids: [],
                  playback_mode: 'sequence',
                  shuffle: false,
                  loop: true,
                });
                setOpenMediaListDialog(true);
              }}
              sx={{ mr: 1 }}
            >
              Add Media List
            </Button>
            <Button
              variant="contained"
              color="secondary"
              startIcon={<AddIcon />}
              onClick={() => {
                setEditingMediaChannelId(null);
                setMediaChannelForm({
                  name: '',
                  media_list_id: '',
                  current_index: 0,
                });
                setOpenMediaChannelDialog(true);
              }}
              sx={{ mr: 1 }}
            >
              Add Media Channel
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={<RefreshIcon />}
              onClick={fetchVideos}
              sx={{ mr: 1 }}
            >
              Refresh
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={<FolderIcon />}
              onClick={() => setOpenScanDialog(true)}
              sx={{ mr: 1 }}
            >
              Scan Directory
            </Button>
            <Button
              variant="contained"
              color="secondary"
              startIcon={<AddIcon />}
              onClick={() => setOpenAddDialog(true)}
            >
              Add Video
            </Button>
          </Box>
        </Box>
        <Divider sx={{ mb: 2 }} />
      </Grid>

      {/* Upload Video */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ md: 'center' }}>
            <FormControl sx={{ minWidth: 220 }}>
              <InputLabel>Category Filter</InputLabel>
              <Select
                value={categoryFilter}
                label="Category Filter"
                onChange={(event) => setCategoryFilter(event.target.value)}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="displays">Displays</MenuItem>
                <MenuItem value="background">Background</MenuItem>
                <MenuItem value="sky">Sky</MenuItem>
                <MenuItem value="patterns">Patterns</MenuItem>
              </Select>
            </FormControl>
            <Typography variant="body2" color="text.secondary">
              Organize shared media libraries for mappings and overlay backgrounds.
            </Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
              <Chip label={`${processingCounts.pending} unprocessed`} size="small" />
              <Chip label={`${processingCounts.processing} processing`} size="small" color="warning" />
              <Chip label={`${processingCounts.ready} processed`} size="small" color="success" />
              <Chip label={`${processingCounts.failed} failed`} size="small" color="error" />
            </Stack>
          </Stack>
          {hasActivePreprocessing && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Video preprocessing is running in the background. This page refreshes automatically while items are pending.
            </Alert>
          )}
        </Paper>
      </Grid>

      <Grid item xs={12}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Saved Media Folders</Typography>
          {mediaDirectories.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No saved media folders yet.</Typography>
          ) : (
            <List>
              {mediaDirectories.map((directory) => (
                <ListItem
                  key={directory.id}
                  secondaryAction={(
                    <Stack direction="row" spacing={1}>
                      <Button variant="outlined" onClick={() => handleScanSavedDirectory(directory)} disabled={scanning}>
                        Scan
                      </Button>
                      <IconButton edge="end" color="error" onClick={() => handleDeleteSavedDirectory(directory)}>
                        <DeleteIcon />
                      </IconButton>
                    </Stack>
                  )}
                >
                  <ListItemAvatar>
                    <Avatar><FolderIcon /></Avatar>
                  </ListItemAvatar>
                  <ListItemText primary={directory.name} secondary={`${directory.path} • ${directory.category}`} />
                </ListItem>
              ))}
            </List>
          )}
        </Paper>
      </Grid>

      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Media Lists</Typography>
          {mediaLists.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No media lists yet.</Typography>
          ) : (
            <List>
              {mediaLists.map((list) => (
                <ListItem
                  key={list.id}
                  secondaryAction={(
                    <IconButton edge="end" onClick={() => openEditMediaListDialog(list)}>
                      <EditIcon />
                    </IconButton>
                  )}
                >
                  <ListItemText primary={list.name} secondary={`${list.video_ids.length} videos • ${list.category}`} />
                </ListItem>
              ))}
            </List>
          )}
        </Paper>
      </Grid>

      <Grid item xs={12} md={6}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Media Channels</Typography>
          {mediaChannels.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No media channels yet.</Typography>
          ) : (
            <List>
              {mediaChannels.map((channel) => (
                <ListItem
                  key={channel.id}
                  secondaryAction={(
                    <IconButton edge="end" onClick={() => openEditMediaChannelDialog(channel)}>
                      <EditIcon />
                    </IconButton>
                  )}
                >
                  <ListItemText primary={channel.name} secondary={`List ${channel.media_list_id} • current index ${channel.current_index}`} />
                </ListItem>
              ))}
            </List>
          )}
        </Paper>
      </Grid>

      <Grid item xs={12}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Upload Video
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', mt: 2 }}>
            <TextField
              type="file"
              inputProps={{ accept: 'video/*' }}
              onChange={(e) => setUploadFile(e.target.files[0])}
              fullWidth
              variant="outlined"
              sx={{ mr: 2 }}
              disabled={isUploading}
            />
            <Button
              variant="contained"
              color="primary"
              onClick={handleUploadVideo}
              disabled={!uploadFile || isUploading}
              startIcon={isUploading ? <CircularProgress size={20} color="inherit" /> : <UploadIcon />}
            >
              {isUploading ? `Uploading ${uploadProgress}%` : 'Upload'}
            </Button>
          </Box>
          {uploadFile && (
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              Selected: {uploadFile.name} ({(uploadFile.size / 1024 / 1024).toFixed(2)} MB)
            </Typography>
          )}
          {isUploading && (
            <Box sx={{ mt: 2 }}>
              <LinearProgress variant="determinate" value={uploadProgress} />
              <Typography variant="body2" color="textSecondary" align="center" sx={{ mt: 1 }}>
                {uploadProgress}% uploaded
              </Typography>
            </Box>
          )}
        </Paper>
      </Grid>

      {/* Video List */}
      {videos.length === 0 ? (
        <Grid item xs={12}>
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="h6" color="textSecondary">
              No videos found
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              Add a video manually, upload a video, or scan a directory for videos
            </Typography>
          </Paper>
        </Grid>
      ) : (
        videos.map(video => (
          <Grid item xs={12} sm={6} md={4} key={video.id}>
            <Card>
              <CardHeader
                title={video.name}
                subheader={`Format: ${video.format || 'Unknown'}`}
                action={
                  <IconButton onClick={() => { setSelectedVideo(video); setOpenDeleteDialog(true); }}>
                    <DeleteIcon />
                  </IconButton>
                }
              />
              <CardMedia
                component="div"
                sx={{
                  height: 140,
                  backgroundColor: 'rgba(0, 0, 0, 0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <VideoIcon sx={{ fontSize: 60, opacity: 0.7 }} />
              </CardMedia>
              <CardContent>
                <Box sx={{ mb: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Chip
                    label={getPreprocessingStatusMeta(video.preprocessing_status).label}
                    size="small"
                    color={getPreprocessingStatusMeta(video.preprocessing_status).color}
                  />
                  {video.overlay_optimized && (
                    <Chip label="Overlay Optimized" size="small" color="success" variant="outlined" />
                  )}
                </Box>
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  Duration: {formatDuration(video.duration)}
                </Typography>
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  Size: {formatFileSize(video.file_size)}
                </Typography>
                {video.resolution && (
                  <Typography variant="body2" color="textSecondary" gutterBottom>
                    Resolution: {video.resolution}
                  </Typography>
                )}
                {video.has_subtitle && (
                  <Chip label="Has Subtitles" size="small" color="primary" sx={{ mt: 1 }} />
                )}
                {video.preprocessing_error && (
                  <Alert severity="error" sx={{ mt: 1 }}>
                    {video.preprocessing_error}
                  </Alert>
                )}
                <Box sx={{ mt: 1 }}>
                  <Chip label={video.category} size="small" color="secondary" sx={{ mr: 1 }} />
                  <Chip label={video.source_type} size="small" variant="outlined" />
                </Box>
              </CardContent>
              <CardActions>
                <Button 
                  size="small" 
                  color="primary"
                  onClick={() => navigate(`/videos/${video.id}`)}
                >
                  Details
                </Button>
                <Button 
                  size="small" 
                  color="primary"
                  startIcon={<PlayIcon />}
                  onClick={() => navigate(`/videos/${video.id}/play`)}
                >
                  Play
                </Button>
                <Button
                  size="small"
                  color="secondary"
                  onClick={() => addVideoToMediaList(video)}
                >
                  Add To List
                </Button>
              </CardActions>
            </Card>
          </Grid>
        ))
      )}

      {/* Add Video Dialog */}
      <Dialog open={openAddDialog} onClose={() => setOpenAddDialog(false)}>
        <DialogTitle>Add New Video</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Enter the details of the video you want to add.
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            name="name"
            label="Video Name"
            type="text"
            fullWidth
            variant="outlined"
            value={newVideo.name}
            onChange={handleInputChange}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            name="path"
            label="Video Path"
            type="text"
            fullWidth
            variant="outlined"
            value={newVideo.path}
            onChange={handleInputChange}
            helperText="Full path to the video file"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenAddDialog(false)}>Cancel</Button>
          <Button onClick={handleAddVideo} variant="contained" color="primary">Add</Button>
        </DialogActions>
      </Dialog>

      {/* Delete Video Dialog */}
      <Dialog open={openDeleteDialog} onClose={() => setOpenDeleteDialog(false)}>
        <DialogTitle>Delete Video</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete the video "{selectedVideo?.name}"? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDeleteDialog(false)}>Cancel</Button>
          <Button onClick={handleDeleteVideo} variant="contained" color="error">Delete</Button>
        </DialogActions>
      </Dialog>

      {/* Scan Directory Dialog */}
      <Dialog open={openScanDialog} onClose={() => setOpenScanDialog(false)}>
        <DialogTitle>Scan Directory for Videos</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Enter the directory path to scan for video files.
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            name="directory"
            label="Directory Path"
            type="text"
            fullWidth
            variant="outlined"
            value={scanDirectory}
            onChange={(e) => setScanDirectory(e.target.value)}
            helperText="Full path to the directory containing videos"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenScanDialog(false)}>Cancel</Button>
          <Button 
            onClick={handleScanDirectory} 
            variant="contained" 
            color="primary"
            disabled={scanning}
            startIcon={scanning ? <CircularProgress size={20} /> : null}
          >
            {scanning ? 'Scanning...' : 'Scan'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={openDirectoryDialog} onClose={() => setOpenDirectoryDialog(false)}>
        <DialogTitle>Add Media Folder</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Save a local directory as a reusable media source configuration.
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            label="Name"
            fullWidth
            value={directoryForm.name}
            onChange={(event) => setDirectoryForm((current) => ({ ...current, name: event.target.value }))}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="Directory Path"
            fullWidth
            value={directoryForm.path}
            onChange={(event) => setDirectoryForm((current) => ({ ...current, path: event.target.value }))}
            sx={{ mb: 2 }}
            helperText="Use Browse to select a folder on the backend host."
          />
          <Button
            variant="outlined"
            startIcon={<FolderIcon />}
            onClick={handleOpenDirectoryBrowser}
            sx={{ mb: 2 }}
          >
            Browse Folders
          </Button>
          <FormControl fullWidth>
            <InputLabel>Category</InputLabel>
            <Select
              value={directoryForm.category}
              label="Category"
              onChange={(event) => setDirectoryForm((current) => ({ ...current, category: event.target.value }))}
            >
              <MenuItem value="displays">Displays</MenuItem>
              <MenuItem value="background">Background</MenuItem>
              <MenuItem value="sky">Sky</MenuItem>
              <MenuItem value="patterns">Patterns</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDirectoryDialog(false)}>Cancel</Button>
          <Button onClick={handleCreateDirectory} variant="contained">Save Folder</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={openDirectoryBrowserDialog} onClose={() => setOpenDirectoryBrowserDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Select Media Folder</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            Browse folders on this machine, then choose one to populate the media folder path.
          </DialogContentText>
          <TextField
            label="Current Path"
            fullWidth
            value={directoryBrowserCurrentPath}
            InputProps={{ readOnly: true }}
            sx={{ mb: 2 }}
          />
          {directoryBrowserError && <Alert severity="error" sx={{ mb: 2 }}>{directoryBrowserError}</Alert>}
          {directoryBrowserLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress size={24} />
            </Box>
          ) : (
            <List dense>
              {directoryBrowserParentPath && (
                <ListItem disablePadding>
                  <ListItemButton onClick={() => loadDirectoryBrowser(directoryBrowserParentPath)}>
                    <ListItemText primary=".." secondary={directoryBrowserParentPath} />
                  </ListItemButton>
                </ListItem>
              )}
              {directoryBrowserEntries.map((entry) => (
                <ListItem key={entry.path} disablePadding>
                  <ListItemButton onClick={() => loadDirectoryBrowser(entry.path)}>
                    <ListItemAvatar>
                      <Avatar>
                        <FolderIcon />
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText primary={entry.name} secondary={entry.path} />
                  </ListItemButton>
                </ListItem>
              ))}
              {!directoryBrowserParentPath && directoryBrowserEntries.length === 0 && (
                <ListItem>
                  <ListItemText primary="No subfolders available." />
                </ListItem>
              )}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDirectoryBrowserDialog(false)}>Cancel</Button>
          <Button
            onClick={handleSelectBrowsedDirectory}
            variant="contained"
            disabled={!directoryBrowserCurrentPath}
          >
            Use This Folder
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={openMediaListDialog} onClose={resetMediaListDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{editingMediaListId ? 'Edit Media List' : 'Create Media List'}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Name"
            fullWidth
            value={mediaListForm.name}
            onChange={(event) => setMediaListForm((current) => ({ ...current, name: event.target.value }))}
            sx={{ mb: 2 }}
          />
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Category</InputLabel>
            <Select
              value={mediaListForm.category}
              label="Category"
              onChange={(event) => setMediaListForm((current) => ({ ...current, category: event.target.value }))}
            >
              <MenuItem value="displays">Displays</MenuItem>
              <MenuItem value="background">Background</MenuItem>
              <MenuItem value="sky">Sky</MenuItem>
              <MenuItem value="patterns">Patterns</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>Videos</InputLabel>
            <Select
              multiple
              value={mediaListForm.video_ids}
              label="Videos"
              onChange={(event) => setMediaListForm((current) => ({ ...current, video_ids: event.target.value }))}
            >
              {videos.map((video) => (
                <MenuItem key={video.id} value={video.id}>{video.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControlLabel
            control={
              <Switch
                checked={Boolean(mediaListForm.shuffle)}
                onChange={(event) => setMediaListForm((current) => ({ ...current, shuffle: event.target.checked }))}
              />
            }
            label="Shuffle video order"
          />
          <FormControlLabel
            control={
              <Switch
                checked={Boolean(mediaListForm.loop)}
                onChange={(event) => setMediaListForm((current) => ({ ...current, loop: event.target.checked }))}
              />
            }
            label="Loop list"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={resetMediaListDialog}>Cancel</Button>
          <Button onClick={handleCreateMediaList} variant="contained">{editingMediaListId ? 'Save' : 'Create'}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={openMediaChannelDialog} onClose={resetMediaChannelDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{editingMediaChannelId ? 'Edit Media Channel' : 'Create Media Channel'}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Name"
            fullWidth
            value={mediaChannelForm.name}
            onChange={(event) => setMediaChannelForm((current) => ({ ...current, name: event.target.value }))}
            sx={{ mb: 2 }}
          />
          <FormControl fullWidth>
            <InputLabel>Media List</InputLabel>
            <Select
              value={mediaChannelForm.media_list_id}
              label="Media List"
              onChange={(event) => setMediaChannelForm((current) => ({ ...current, media_list_id: event.target.value }))}
            >
              {mediaLists.map((list) => (
                <MenuItem key={list.id} value={list.id}>{list.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={resetMediaChannelDialog}>Cancel</Button>
          <Button onClick={handleCreateMediaChannel} variant="contained">{editingMediaChannelId ? 'Save' : 'Create'}</Button>
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

export default Videos;
