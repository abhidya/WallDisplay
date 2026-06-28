import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  CardMedia,
  Chip,
  CircularProgress,
  Grid,
  Link,
  Paper,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import {
  Download as ImportIcon,
  Refresh as RefreshIcon,
  Search as SearchIcon,
} from '@mui/icons-material';
import PageHeader from '../components/PageHeader';
import StatusPanel from '../components/StatusPanel';
import { mediaSourceApi } from '../services/api';

function formatDate(value) {
  if (!value) return 'Never';
  try {
    return new Date(value).toLocaleString();
  } catch (error) {
    return value;
  }
}

function MediaSources() {
  const [status, setStatus] = useState(null);
  const [entries, setEntries] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [importingId, setImportingId] = useState(null);
  const [error, setError] = useState('');
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const loadData = useCallback(async (searchValue = query) => {
    setError('');
    try {
      const [statusResponse, entriesResponse] = await Promise.all([
        mediaSourceApi.getDesktopHutStatus(),
        mediaSourceApi.browseDesktopHut({ query: searchValue, limit: 48 }),
      ]);
      setStatus(statusResponse.data);
      setEntries(entriesResponse.data.entries || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load media sources.');
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    loadData('');
  }, [loadData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const response = await mediaSourceApi.refreshDesktopHut({ max_pages: 25 });
      setSnackbar({
        open: true,
        message: response.data.success ? `Refresh complete. Updated ${response.data.items_updated} entries.` : response.data.error || response.data.status,
        severity: response.data.success ? 'success' : 'warning',
      });
      await loadData(query);
    } catch (err) {
      setSnackbar({ open: true, message: err.response?.data?.detail || 'Refresh failed.', severity: 'error' });
    } finally {
      setRefreshing(false);
    }
  };

  const handleSearch = async (event) => {
    event.preventDefault();
    setLoading(true);
    await loadData(query);
  };

  const handleImport = async (entry) => {
    setImportingId(entry.id);
    try {
      const response = await mediaSourceApi.importDesktopHutEntry(entry.id);
      setSnackbar({
        open: true,
        message: response.data.duplicate ? 'Already in video library.' : 'Imported into video library.',
        severity: 'success',
      });
      await loadData(query);
    } catch (err) {
      setSnackbar({
        open: true,
        message: err.response?.data?.detail || 'Import failed.',
        severity: 'error',
      });
    } finally {
      setImportingId(null);
    }
  };

  if (loading && !status) {
    return <StatusPanel loading title="Loading media sources" message="Reading cached DesktopHut source metadata." />;
  }

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <PageHeader
          title="Media Sources"
          subtitle="Browse cached public provider metadata and explicitly import selected media into the local library."
          meta={(
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip label={`${status?.item_count || 0} DesktopHut items`} color="primary" />
              <Chip label={`Last refresh: ${formatDate(status?.last_refresh_at)}`} variant="outlined" />
            </Stack>
          )}
          actions={(
            <Button
              variant="contained"
              startIcon={refreshing ? <CircularProgress size={18} color="inherit" /> : <RefreshIcon />}
              onClick={handleRefresh}
              disabled={refreshing}
            >
              {refreshing ? 'Refreshing' : 'Refresh DesktopHut'}
            </Button>
          )}
        />
      </Grid>

      <Grid item xs={12}>
        <Paper sx={{ p: 2 }}>
          <Stack spacing={2}>
            <Box>
              <Typography variant="h6">DesktopHut</Typography>
              <Typography variant="body2" color="text.secondary">
                Status: {status?.status || 'idle'} • Last success: {formatDate(status?.last_success_at)}
              </Typography>
            </Box>
            {status?.last_error && <Alert severity="warning">{status.last_error}</Alert>}
            {status?.backoff_until && <Alert severity="info">Backoff until {formatDate(status.backoff_until)}</Alert>}
            {error && <Alert severity="error">{error}</Alert>}
            <Box component="form" onSubmit={handleSearch} sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <TextField
                label="Search cached entries"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                sx={{ minWidth: { xs: '100%', sm: 320 } }}
              />
              <Button type="submit" variant="outlined" startIcon={<SearchIcon />}>Search</Button>
            </Box>
          </Stack>
        </Paper>
      </Grid>

      {entries.map((entry) => (
        <Grid item xs={12} sm={6} md={4} lg={3} key={entry.id}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardMedia
              component={entry.thumbnail_url ? 'img' : 'div'}
              image={entry.thumbnail_url || undefined}
              alt={entry.title}
              sx={{
                height: 150,
                bgcolor: 'action.hover',
                objectFit: 'cover',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            />
            <CardContent sx={{ flexGrow: 1 }}>
              <Typography variant="subtitle1" noWrap title={entry.title}>{entry.title}</Typography>
              <Stack direction="row" spacing={1} sx={{ my: 1 }} flexWrap="wrap" useFlexGap>
                <Chip size="small" label={entry.cache_status} color={entry.cache_status === 'failed' ? 'error' : 'default'} />
                <Chip size="small" label={entry.import_status} color={entry.import_status === 'imported' ? 'success' : 'default'} />
              </Stack>
              {entry.category && <Typography variant="body2" color="text.secondary">{entry.category}</Typography>}
              {entry.failure_reason && <Alert severity="warning" sx={{ mt: 1 }}>{entry.failure_reason}</Alert>}
              <Link href={entry.page_url} target="_blank" rel="noreferrer" variant="body2">
                Source page
              </Link>
            </CardContent>
            <CardActions>
              <Button
                size="small"
                startIcon={importingId === entry.id ? <CircularProgress size={16} /> : <ImportIcon />}
                onClick={() => handleImport(entry)}
                disabled={importingId === entry.id || entry.import_status === 'imported' || !entry.media_url}
              >
                {entry.import_status === 'imported' ? 'Imported' : 'Import'}
              </Button>
            </CardActions>
          </Card>
        </Grid>
      ))}

      {!loading && entries.length === 0 && (
        <Grid item xs={12}>
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="h6" color="text.secondary">No cached DesktopHut entries</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Refresh DesktopHut to discover public sitemap entries.
            </Typography>
          </Paper>
        </Grid>
      )}

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar((current) => ({ ...current, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((current) => ({ ...current, open: false }))}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Grid>
  );
}

export default MediaSources;
