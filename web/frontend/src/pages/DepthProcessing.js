import React, { useState } from 'react';
import {
  Grid,
  Paper,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  CardMedia,
  Box,
  CircularProgress,
  Alert,
  Snackbar,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Chip,
  Stack
} from '@mui/material';
import {
  Upload as UploadIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
  Refresh as RefreshIcon,
  Visibility as VisibilityIcon
} from '@mui/icons-material';
import PageHeader from '../components/PageHeader';
import { depthApi } from '../services/api';

function DepthProcessing() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [uploadedDepthMap, setUploadedDepthMap] = useState(null);
  const [segmentationMethod, setSegmentationMethod] = useState('kmeans');
  const [numClusters, setNumClusters] = useState(5);
  const [thresholds, setThresholds] = useState([0.25, 0.5, 0.75]);
  const [numBands, setNumBands] = useState(5);
  const [segmentationResult, setSegmentationResult] = useState(null);
  const [selectedSegments, setSelectedSegments] = useState([]);
  const [overlayAlpha, setOverlayAlpha] = useState(0.5);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'success'
  });

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('normalize', 'true');

    try {
      setLoading(true);
      setError(null);
      const response = await depthApi.uploadDepthMap(formData);
      setUploadedDepthMap(response.data);
      setSnackbar({
        open: true,
        message: 'Depth map uploaded successfully',
        severity: 'success'
      });
    } catch (err) {
      console.error('Error uploading depth map:', err);
      setError('Failed to upload depth map. Please try again.');
      setSnackbar({
        open: true,
        message: 'Failed to upload depth map',
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSegmentation = async () => {
    if (!uploadedDepthMap) {
      setSnackbar({
        open: true,
        message: 'Please upload a depth map first',
        severity: 'warning'
      });
      return;
    }

    const segmentationParams = {
      method: segmentationMethod,
      n_clusters: numClusters,
      thresholds: thresholds,
      n_bands: numBands
    };

    try {
      setLoading(true);
      setError(null);
      const response = await depthApi.segmentDepthMap(uploadedDepthMap.depth_id, segmentationParams);
      setSegmentationResult(response.data);
      setSelectedSegments([]); // Reset selected segments
      setSnackbar({
        open: true,
        message: `Segmentation completed with ${response.data.segment_count} segments`,
        severity: 'success'
      });
    } catch (err) {
      console.error('Error segmenting depth map:', err);
      setError('Failed to segment depth map. Please try again.');
      setSnackbar({
        open: true,
        message: 'Failed to segment depth map',
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSegmentToggle = (segmentId) => {
    setSelectedSegments(prev => {
      if (prev.includes(segmentId)) {
        return prev.filter(id => id !== segmentId);
      } else {
        return [...prev, segmentId];
      }
    });
  };

  const handleExportMasks = async () => {
    if (!segmentationResult || selectedSegments.length === 0) {
      setSnackbar({
        open: true,
        message: 'Please select at least one segment to export',
        severity: 'warning'
      });
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      // Create a link element to trigger the download
      const link = document.createElement('a');
      link.href = `/api/depth/export_masks/${segmentationResult.depth_id}?segment_ids=${selectedSegments.join(',')}&clean_mask=true&min_area=100&kernel_size=3`;
      link.download = 'depth_masks.zip';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      setSnackbar({
        open: true,
        message: 'Masks exported successfully',
        severity: 'success'
      });
    } catch (err) {
      console.error('Error exporting masks:', err);
      setError('Failed to export masks. Please try again.');
      setSnackbar({
        open: true,
        message: 'Failed to export masks',
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDepthMap = async () => {
    if (!uploadedDepthMap) return;

    try {
      setLoading(true);
      setError(null);
      await depthApi.deleteDepthMap(uploadedDepthMap.depth_id);
      setUploadedDepthMap(null);
      setSegmentationResult(null);
      setSelectedSegments([]);
      setSnackbar({
        open: true,
        message: 'Depth map deleted successfully',
        severity: 'success'
      });
    } catch (err) {
      console.error('Error deleting depth map:', err);
      setError('Failed to delete depth map. Please try again.');
      setSnackbar({
        open: true,
        message: 'Failed to delete depth map',
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({
      ...prev,
      open: false
    }));
  };

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <PageHeader
          title="Depth Processing"
          subtitle="Upload depth maps, segment surfaces, and prepare masks for projection workflows."
          meta={(
            <>
              <Chip label={uploadedDepthMap ? 'depth map loaded' : 'awaiting upload'} color={uploadedDepthMap ? 'success' : 'default'} />
              <Chip label={segmentationResult ? `${segmentationResult.segment_count} segments` : 'no segments'} variant="outlined" />
              <Chip label={`${selectedSegments.length} selected`} variant="outlined" />
            </>
          )}
        />
      </Grid>

      {error && (
        <Grid item xs={12}>
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        </Grid>
      )}

      {/* Upload Section */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Upload Depth Map</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Button
              variant="contained"
              component="label"
              startIcon={<UploadIcon />}
              disabled={loading}
            >
              Upload Depth Map
              <input
                type="file"
                hidden
                accept=".png,.jpg,.jpeg,.tif,.tiff,.exr"
                onChange={handleFileUpload}
              />
            </Button>
            {uploadedDepthMap && (
              <Typography variant="body2" sx={{ ml: 2 }}>
                Uploaded: {uploadedDepthMap.message}
              </Typography>
            )}
          </Box>
          {uploadedDepthMap && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
              <Card sx={{ maxWidth: 500 }}>
                <CardMedia
                  component="img"
                  image={depthApi.previewDepthMap(uploadedDepthMap.depth_id)}
                  alt="Depth Map Preview"
                  sx={{ height: 300, objectFit: 'contain' }}
                />
                <CardActions>
                  <Button 
                    size="small" 
                    color="error" 
                    startIcon={<DeleteIcon />}
                    onClick={handleDeleteDepthMap}
                  >
                    Delete
                  </Button>
                </CardActions>
              </Card>
            </Box>
          )}
        </Paper>
      </Grid>

      {/* Segmentation Section */}
      {uploadedDepthMap && (
        <Grid item xs={12}>
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>Segment Depth Map</Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <FormControl fullWidth>
                  <InputLabel>Segmentation Method</InputLabel>
                  <Select
                    value={segmentationMethod}
                    onChange={(e) => setSegmentationMethod(e.target.value)}
                    label="Segmentation Method"
                  >
                    <MenuItem value="kmeans">K-Means Clustering</MenuItem>
                    <MenuItem value="threshold">Threshold</MenuItem>
                    <MenuItem value="bands">Depth Bands</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              {segmentationMethod === 'kmeans' && (
                <Grid item xs={12} sm={6} md={3}>
                  <TextField
                    label="Number of Clusters"
                    type="number"
                    value={numClusters}
                    onChange={(e) => setNumClusters(parseInt(e.target.value))}
                    InputProps={{ inputProps: { min: 2, max: 20 } }}
                    fullWidth
                  />
                </Grid>
              )}

              {segmentationMethod === 'threshold' && (
                <Grid item xs={12} sm={6} md={6}>
                  <Typography gutterBottom>Thresholds</Typography>
                  <Box sx={{ px: 2 }}>
                    <Slider
                      value={thresholds}
                      onChange={(e, newValue) => setThresholds(newValue)}
                      valueLabelDisplay="auto"
                      step={0.05}
                      marks
                      min={0}
                      max={1}
                      multiple
                    />
                  </Box>
                </Grid>
              )}

              {segmentationMethod === 'bands' && (
                <Grid item xs={12} sm={6} md={3}>
                  <TextField
                    label="Number of Bands"
                    type="number"
                    value={numBands}
                    onChange={(e) => setNumBands(parseInt(e.target.value))}
                    InputProps={{ inputProps: { min: 2, max: 20 } }}
                    fullWidth
                  />
                </Grid>
              )}

              <Grid item xs={12}>
                <Button
                  variant="contained"
                  onClick={handleSegmentation}
                  disabled={loading}
                  startIcon={loading ? <CircularProgress size={20} /> : <RefreshIcon />}
                >
                  {loading ? 'Processing...' : 'Segment Depth Map'}
                </Button>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      )}

      {/* Segmentation Results */}
      {segmentationResult && (
        <Grid item xs={12}>
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>Segmentation Results</Typography>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" gutterBottom>
                Segments Found: {segmentationResult.segment_count}
              </Typography>
              <Typography variant="body2" gutterBottom>
                Method: {segmentationResult.message}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
              <Card sx={{ maxWidth: 500 }}>
                <CardMedia
                  component="img"
                  image={depthApi.previewSegmentation(segmentationResult.depth_id, overlayAlpha)}
                  alt="Segmentation Preview"
                  sx={{ height: 300, objectFit: 'contain' }}
                />
                <CardContent>
                  <Typography gutterBottom>Overlay Transparency</Typography>
                  <Slider
                    value={overlayAlpha}
                    onChange={(e, newValue) => setOverlayAlpha(newValue)}
                    valueLabelDisplay="auto"
                    step={0.1}
                    marks
                    min={0}
                    max={1}
                  />
                </CardContent>
              </Card>
            </Box>

            <Typography variant="subtitle1" gutterBottom>Select Segments to Export</Typography>
            <Box sx={{ mb: 2 }}>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {segmentationResult.segments.map((segmentId) => (
                  <Chip
                    key={segmentId}
                    label={`Segment ${segmentId}`}
                    onClick={() => handleSegmentToggle(segmentId)}
                    color={selectedSegments.includes(segmentId) ? 'primary' : 'default'}
                    sx={{ m: 0.5 }}
                  />
                ))}
              </Stack>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
              <Button
                variant="contained"
                onClick={handleExportMasks}
                disabled={loading || selectedSegments.length === 0}
                startIcon={<SaveIcon />}
              >
                Export Selected Masks
              </Button>
              
              {selectedSegments.length === 1 && (
                <Button
                  variant="outlined"
                  component="a"
                  href={depthApi.getMask(segmentationResult.depth_id, selectedSegments[0])}
                  target="_blank"
                  startIcon={<VisibilityIcon />}
                >
                  Preview Mask
                </Button>
              )}
            </Box>
          </Paper>
        </Grid>
      )}

      {/* Projection Section - Placeholder for future implementation */}
      {segmentationResult && (
        <Grid item xs={12}>
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="h6" gutterBottom>Projection Mapping</Typography>
            <Typography variant="body2" color="text.secondary">
              Create projection mapping configurations using the segmented depth map.
              This feature allows you to map videos to specific surfaces detected in the depth map.
            </Typography>
            <Button
              variant="contained"
              sx={{ mt: 2 }}
              disabled={true} // Disabled for now
            >
              Create Projection (Coming Soon)
            </Button>
          </Paper>
        </Grid>
      )}

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

export default DepthProcessing;
