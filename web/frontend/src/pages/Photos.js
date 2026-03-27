import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardMedia,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon, Refresh as RefreshIcon, Upload as UploadIcon } from '@mui/icons-material';

import { photoApi, photoListApi } from '../services/api';

function Photos() {
  const [photos, setPhotos] = useState([]);
  const [photoLists, setPhotoLists] = useState([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [openAddDialog, setOpenAddDialog] = useState(false);
  const [openScanDialog, setOpenScanDialog] = useState(false);
  const [openListDialog, setOpenListDialog] = useState(false);
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

  const handleCreatePhotoList = async () => {
    try {
      await photoListApi.createPhotoList(photoListForm);
      setOpenListDialog(false);
      setPhotoListForm({
        name: '',
        category: 'background',
        photo_ids: [],
        playback_mode: 'sequence',
        shuffle: false,
        loop: true,
      });
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

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="h4">Photos</Typography>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchPhotos}>Refresh</Button>
          <Button variant="outlined" startIcon={<AddIcon />} onClick={() => setOpenAddDialog(true)}>Add Photo</Button>
          <Button variant="outlined" startIcon={<UploadIcon />} component="label">
            Pick File
            <input hidden type="file" accept="image/*" onChange={(event) => setUploadFile(event.target.files?.[0] || null)} />
          </Button>
          <Button variant="contained" onClick={handleUploadPhoto} disabled={!uploadFile}>Upload</Button>
          <Button variant="outlined" onClick={() => setOpenScanDialog(true)}>Scan Directory</Button>
          <Button variant="contained" onClick={() => setOpenListDialog(true)}>Create Photo List</Button>
        </Stack>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      {message && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMessage('')}>{message}</Alert>}

      <Typography variant="h6" sx={{ mb: 2 }}>Library</Typography>
      <Grid container spacing={2} sx={{ mb: 4 }}>
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

      <Typography variant="h6" sx={{ mb: 2 }}>Photo Lists</Typography>
      <Stack spacing={1}>
        {photoLists.map((list) => (
          <Stack key={list.id} direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2, border: '1px solid #ddd', borderRadius: 1 }}>
            <Box>
              <Typography variant="subtitle1">{list.name}</Typography>
              <Typography variant="body2" color="text.secondary">{list.photo_ids.length} photos</Typography>
            </Box>
            <Button color="error" startIcon={<DeleteIcon />} onClick={() => handleDeletePhotoList(list.id)}>Delete</Button>
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

      <Dialog open={openListDialog} onClose={() => setOpenListDialog(false)} fullWidth maxWidth="sm">
        <DialogTitle>Create Photo List</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Name" value={photoListForm.name} onChange={(event) => setPhotoListForm((current) => ({ ...current, name: event.target.value }))} />
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
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenListDialog(false)}>Cancel</Button>
          <Button onClick={handleCreatePhotoList} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default Photos;
