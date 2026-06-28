import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardMedia,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Refresh as RefreshIcon, Upload as UploadIcon } from '@mui/icons-material';

import { photoApi, photoListApi } from '../services/api';
import PageHeader from '../components/PageHeader';

function Photos() {
  const [photos, setPhotos] = useState([]);
  const [photoLists, setPhotoLists] = useState([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [openAddDialog, setOpenAddDialog] = useState(false);
  const [openScanDialog, setOpenScanDialog] = useState(false);
  const [openListDialog, setOpenListDialog] = useState(false);
  const [editingPhotoListId, setEditingPhotoListId] = useState(null);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [newPhoto, setNewPhoto] = useState({ name: '', path: '', category: 'background' });
  const [scanDirectory, setScanDirectory] = useState('');
  const [photoListForm, setPhotoListForm] = useState({
    name: '',
    category: 'background',
    photo_ids: [],
    playback_mode: 'sequence',
    shuffle: false,
    loop: true,
  });

  const fetchPhotos = useCallback(async () => {
    try {
      const [photoResponse, photoListResponse] = await Promise.all([
        photoApi.getPhotos(),
        photoListApi.listPhotoLists(),
      ]);
      setPhotos(photoResponse.data.photos || []);
      setPhotoLists(photoListResponse.data || []);
    } catch (err) {
      console.error(err);
      setError('Failed to load photos');
    }
  }, []);

  useEffect(() => {
    fetchPhotos();
  }, [fetchPhotos]);

  const handleAddPhoto = async () => {
    try {
      await photoApi.createPhoto(newPhoto);
      setOpenAddDialog(false);
      setNewPhoto({ name: '', path: '', category: 'background' });
      setMessage('Photo added');
      fetchPhotos();
    } catch (err) {
      console.error(err);
      setError('Failed to add photo');
    }
  };

  const handleUploadPhoto = async () => {
    if (!uploadFile) {
      return;
    }
    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('upload_dir', 'uploads/photos');
    try {
      await photoApi.uploadPhoto(formData);
      setUploadFile(null);
      setMessage('Photo uploaded');
      fetchPhotos();
    } catch (err) {
      console.error(err);
      setError('Failed to upload photo');
    }
  };

  const handleDeletePhoto = async (photo = selectedPhoto) => {
    if (!photo) {
      return;
    }
    try {
      await photoApi.deletePhoto(photo.id);
      if (selectedPhoto?.id === photo.id) {
        setSelectedPhoto(null);
      }
      setMessage('Photo deleted');
      fetchPhotos();
    } catch (err) {
      console.error(err);
      setError('Failed to delete photo');
    }
  };

  const handleScanDirectory = async () => {
    try {
      await photoApi.scanDirectory(scanDirectory);
      setOpenScanDialog(false);
      setScanDirectory('');
      setMessage('Photo directory scanned');
      fetchPhotos();
    } catch (err) {
      console.error(err);
      setError('Failed to scan photo directory');
    }
  };

  const resetPhotoListDialog = () => {
    setOpenListDialog(false);
    setEditingPhotoListId(null);
    setPhotoListForm({
      name: '',
      category: 'background',
      photo_ids: [],
      playback_mode: 'sequence',
      shuffle: false,
      loop: true,
    });
  };

  const handleCreatePhotoList = async () => {
    try {
      if (editingPhotoListId) {
        await photoListApi.updatePhotoList(editingPhotoListId, photoListForm);
      } else {
        await photoListApi.createPhotoList(photoListForm);
      }
      resetPhotoListDialog();
      setMessage('Photo list saved');
      fetchPhotos();
    } catch (err) {
      console.error(err);
      setError('Failed to save photo list');
    }
  };

  const handleDeletePhotoList = async (listId) => {
    try {
      await photoListApi.deletePhotoList(listId);
      setMessage('Photo list deleted');
      fetchPhotos();
    } catch (err) {
      console.error(err);
      setError('Failed to delete photo list');
    }
  };

  const openEditPhotoList = (list) => {
    setEditingPhotoListId(list.id);
    setPhotoListForm({
      name: list.name || '',
      category: list.category || 'background',
      photo_ids: list.photo_ids || [],
      playback_mode: list.playback_mode || 'sequence',
      shuffle: Boolean(list.shuffle),
      loop: list.loop !== false,
    });
    setOpenListDialog(true);
  };

  return (
    <Box sx={{ display: 'grid', gap: 3 }}>
      <PageHeader
        title="Photos"
        subtitle="Curate still-image assets and photo lists for background, pattern, and projection workflows."
        meta={(
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip label={`${photos.length} photos`} color="primary" />
            <Chip label={`${photoLists.length} lists`} color="secondary" variant="outlined" />
            {selectedPhoto ? <Chip label={`Selected: ${selectedPhoto.name}`} variant="outlined" /> : null}
          </Stack>
        )}
        actions={(
          <>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchPhotos}>Refresh</Button>
          <Button variant="outlined" startIcon={<AddIcon />} onClick={() => setOpenAddDialog(true)}>Add Photo</Button>
          <Button variant="outlined" startIcon={<UploadIcon />} component="label">
            Pick File
            <input hidden type="file" accept="image/*" onChange={(event) => setUploadFile(event.target.files?.[0] || null)} />
          </Button>
          <Button variant="contained" onClick={handleUploadPhoto} disabled={!uploadFile}>Upload</Button>
          <Button variant="outlined" onClick={() => setOpenScanDialog(true)}>Scan Directory</Button>
          <Button
            variant="contained"
            onClick={() => {
              setEditingPhotoListId(null);
              setPhotoListForm({
                name: '',
                category: 'background',
                photo_ids: [],
                playback_mode: 'sequence',
                shuffle: false,
                loop: true,
              });
              setOpenListDialog(true);
            }}
          >
            Create Photo List
          </Button>
          </>
        )}
      />

      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {message && <Alert severity="success" onClose={() => setMessage('')}>{message}</Alert>}

      <Box>
        <Typography variant="h6" sx={{ mb: 2 }}>Library</Typography>
        {photos.length === 0 ? (
          <Box
            sx={{
              bgcolor: 'background.paper',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 2,
              p: 3,
            }}
          >
            <Typography variant="subtitle1" fontWeight={700}>No photos found</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Add, upload, or scan a directory to create photo assets.
            </Typography>
          </Box>
        ) : null}
      </Box>
      <Grid container spacing={2}>
        {photos.map((photo) => (
          <Grid item xs={12} sm={6} md={4} lg={3} key={photo.id}>
            <Card variant={selectedPhoto?.id === photo.id ? 'elevation' : 'outlined'}>
              <CardMedia component="img" height="180" image={`/api/photos/${photo.id}/file`} alt={photo.name} />
              <CardContent>
                <Typography variant="subtitle1">{photo.name}</Typography>
                <Typography variant="body2" color="text.secondary">{photo.resolution || 'Unknown size'}</Typography>
                <Typography variant="body2" color="text.secondary">{photo.category}</Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                  <Button size="small" onClick={() => setSelectedPhoto(photo)}>Select</Button>
                  <Button size="small" color="error" startIcon={<DeleteIcon />} onClick={() => handleDeletePhoto(photo)}>
                    Delete
                  </Button>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Typography variant="h6">Photo Lists</Typography>
      <Stack spacing={1}>
        {photoLists.map((list) => (
          <Stack
            key={list.id}
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1.5}
            justifyContent="space-between"
            alignItems={{ xs: 'flex-start', sm: 'center' }}
            sx={{
              bgcolor: 'background.paper',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 2,
              p: 2,
            }}
          >
            <Box>
              <Typography variant="subtitle1">{list.name}</Typography>
              <Typography variant="body2" color="text.secondary">
                {list.photo_ids.length} photos • {Boolean(list.shuffle) ? 'shuffle' : 'sequence'}
              </Typography>
            </Box>
            <Stack direction="row" spacing={1}>
              <Button onClick={() => openEditPhotoList(list)}>Edit</Button>
              <Button color="error" startIcon={<DeleteIcon />} onClick={() => handleDeletePhotoList(list.id)}>Delete</Button>
            </Stack>
          </Stack>
        ))}
      </Stack>

      <Dialog open={openAddDialog} onClose={() => setOpenAddDialog(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add Photo</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Name" value={newPhoto.name} onChange={(event) => setNewPhoto((current) => ({ ...current, name: event.target.value }))} />
            <TextField label="Path" value={newPhoto.path} onChange={(event) => setNewPhoto((current) => ({ ...current, path: event.target.value }))} />
            <FormControl fullWidth>
              <InputLabel>Category</InputLabel>
              <Select label="Category" value={newPhoto.category} onChange={(event) => setNewPhoto((current) => ({ ...current, category: event.target.value }))}>
                <MenuItem value="background">Background</MenuItem>
                <MenuItem value="displays">Displays</MenuItem>
                <MenuItem value="patterns">Patterns</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenAddDialog(false)}>Cancel</Button>
          <Button onClick={handleAddPhoto} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={openScanDialog} onClose={() => setOpenScanDialog(false)} fullWidth maxWidth="sm">
        <DialogTitle>Scan Directory for Photos</DialogTitle>
        <DialogContent>
          <TextField fullWidth label="Directory Path" value={scanDirectory} onChange={(event) => setScanDirectory(event.target.value)} sx={{ mt: 1 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenScanDialog(false)}>Cancel</Button>
          <Button onClick={handleScanDirectory} variant="contained">Scan</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={openListDialog} onClose={resetPhotoListDialog} fullWidth maxWidth="sm">
        <DialogTitle>{editingPhotoListId ? 'Edit Photo List' : 'Create Photo List'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Name" value={photoListForm.name} onChange={(event) => setPhotoListForm((current) => ({ ...current, name: event.target.value }))} />
            <FormControl fullWidth>
              <InputLabel>Playback Mode</InputLabel>
              <Select
                value={photoListForm.playback_mode}
                label="Playback Mode"
                onChange={(event) => setPhotoListForm((current) => ({ ...current, playback_mode: event.target.value }))}
              >
                <MenuItem value="sequence">Sequence</MenuItem>
                <MenuItem value="manual">Manual</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Photos</InputLabel>
              <Select
                multiple
                value={photoListForm.photo_ids}
                label="Photos"
                onChange={(event) => setPhotoListForm((current) => ({ ...current, photo_ids: event.target.value }))}
              >
                {photos.map((photo) => (
                  <MenuItem key={photo.id} value={photo.id}>{photo.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControlLabel
              control={
                <Switch
                  checked={Boolean(photoListForm.shuffle)}
                  onChange={(event) => setPhotoListForm((current) => ({ ...current, shuffle: event.target.checked }))}
                />
              }
              label="Shuffle photo order"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={Boolean(photoListForm.loop)}
                  onChange={(event) => setPhotoListForm((current) => ({ ...current, loop: event.target.checked }))}
                />
              }
              label="Loop list"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={resetPhotoListDialog}>Cancel</Button>
          <Button onClick={handleCreatePhotoList} variant="contained">{editingPhotoListId ? 'Save' : 'Create'}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default Photos;
