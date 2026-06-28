import React, { useEffect, useMemo, useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

// Layout components
import Layout from './components/Layout';

// Pages
import Dashboard from './pages/Dashboard';
import Devices from './pages/Devices';
import DeviceDetail from './pages/DeviceDetail';
import PlayVideo from './pages/PlayVideo';
import PlayVideoOnDevice from './pages/PlayVideoOnDevice';
import Videos from './pages/Videos';
import Photos from './pages/Photos';
import Settings from './pages/Settings';
import NotFound from './pages/NotFound';
import Renderer from './pages/Renderer';
import DepthProcessing from './pages/DepthProcessing';
import ProjectionMapping from './pages/ProjectionMapping';
import OverlayProjection from './pages/OverlayProjection';
import ProjectionAnimation from './pages/ProjectionAnimation';
import Mappings from './pages/Mappings';
import StreamingDiagnostics from './pages/StreamingDiagnostics';
import StructuredLighting from './pages/StructuredLighting';
import SceneControl from './pages/SceneControl';
import MediaSources from './pages/MediaSources';

const UI_PREFS_KEY = 'nanoDlnaUiPrefs';

function getUiPrefs() {
  try {
    const raw = localStorage.getItem(UI_PREFS_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return {
      themeMode: parsed.themeMode === 'dark' ? 'dark' : 'light',
    };
  } catch (error) {
    return {
      themeMode: 'light',
    };
  }
}

function App() {
  const [themeMode, setThemeMode] = useState(() => getUiPrefs().themeMode);

  useEffect(() => {
    const syncPrefs = () => {
      setThemeMode(getUiPrefs().themeMode);
    };

    window.addEventListener('storage', syncPrefs);
    window.addEventListener('nanoDlnaUiPrefsChanged', syncPrefs);
    return () => {
      window.removeEventListener('storage', syncPrefs);
      window.removeEventListener('nanoDlnaUiPrefsChanged', syncPrefs);
    };
  }, []);

  const theme = useMemo(() => createTheme({
    palette: {
      mode: themeMode,
      primary: {
        main: themeMode === 'dark' ? '#fb923c' : '#ea580c',
        contrastText: '#ffffff',
      },
      secondary: {
        main: themeMode === 'dark' ? '#60a5fa' : '#2563eb',
        contrastText: '#ffffff',
      },
      error: {
        main: '#dc2626',
      },
      background: themeMode === 'dark'
        ? {
            default: '#111827',
            paper: '#1f2937',
          }
        : {
            default: '#fff7ed',
            paper: '#ffffff',
          },
      text: themeMode === 'dark'
        ? {
            primary: '#f8fafc',
            secondary: '#cbd5e1',
          }
        : {
            primary: '#0f172a',
            secondary: '#475569',
          },
      divider: themeMode === 'dark' ? '#334155' : '#fceae1',
    },
    typography: {
      fontFamily: '"Fira Sans", "Segoe UI", Arial, sans-serif',
      h1: { fontFamily: '"Fira Code", "Fira Sans", monospace', fontWeight: 700 },
      h2: { fontFamily: '"Fira Code", "Fira Sans", monospace', fontWeight: 700 },
      h3: { fontFamily: '"Fira Code", "Fira Sans", monospace', fontWeight: 700 },
      h4: { fontFamily: '"Fira Code", "Fira Sans", monospace', fontWeight: 700 },
      h5: { fontFamily: '"Fira Code", "Fira Sans", monospace', fontWeight: 600 },
      h6: { fontFamily: '"Fira Code", "Fira Sans", monospace', fontWeight: 600 },
      button: { fontWeight: 700, textTransform: 'none' },
    },
    shape: {
      borderRadius: 8,
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            minHeight: 44,
            borderRadius: 8,
            transition: 'background-color 200ms ease, border-color 200ms ease, box-shadow 200ms ease',
            '&:focus-visible': {
              boxShadow: '0 0 0 3px rgba(234, 88, 12, 0.28)',
            },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            minWidth: 44,
            minHeight: 44,
            transition: 'background-color 200ms ease, color 200ms ease',
            '&:focus-visible': {
              boxShadow: '0 0 0 3px rgba(234, 88, 12, 0.28)',
            },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: ({ theme }) => ({
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: theme.palette.mode === 'dark'
              ? '0 10px 24px rgba(0, 0, 0, 0.28)'
              : '0 4px 10px rgba(15, 23, 42, 0.1)',
            transition: 'border-color 200ms ease, box-shadow 200ms ease',
          }),
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundImage: 'none',
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: theme.palette.mode === 'dark'
              ? '0 10px 24px rgba(0, 0, 0, 0.24)'
              : '0 4px 10px rgba(15, 23, 42, 0.08)',
          }),
        },
      },
      MuiAccordion: {
        styleOverrides: {
          root: ({ theme }) => ({
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 8,
            boxShadow: 'none',
            '&:before': {
              display: 'none',
            },
          }),
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            fontWeight: 700,
          },
        },
      },
      MuiTextField: {
        defaultProps: {
          size: 'small',
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            transition: 'box-shadow 200ms ease',
            '&.Mui-focused': {
              boxShadow: '0 0 0 3px rgba(234, 88, 12, 0.18)',
            },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          head: ({ theme }) => ({
            color: theme.palette.text.secondary,
            fontWeight: 700,
            textTransform: 'uppercase',
            fontSize: '0.75rem',
          }),
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: ({ theme }) => ({
            minHeight: 44,
            borderRadius: 8,
            marginInline: 8,
            '&.Mui-selected': {
              backgroundColor: theme.palette.mode === 'dark'
                ? 'rgba(251, 146, 60, 0.18)'
                : 'rgba(234, 88, 12, 0.12)',
            },
          }),
        },
      },
    },
  }), [themeMode]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/devices" element={<Devices />} />
          <Route path="/devices/:id" element={<DeviceDetail />} />
          <Route path="/devices/:id/play" element={<PlayVideo />} />
          <Route path="/devices/discover" element={<Devices />} />
          <Route path="/videos" element={<Videos />} />
          <Route path="/photos" element={<Photos />} />
          <Route path="/videos/:id" element={<Videos />} />
          <Route path="/videos/:id/play" element={<PlayVideoOnDevice />} />
          <Route path="/videos/add" element={<Videos />} />
          <Route path="/videos/scan" element={<Videos />} />
          <Route path="/media-sources" element={<MediaSources />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/settings/load-config" element={<Settings />} />
          <Route path="/renderer" element={<Renderer />} />
          <Route path="/depth" element={<DepthProcessing />} />
          <Route path="/projection" element={<ProjectionMapping />} />
          <Route path="/mappings" element={<Mappings />} />
          <Route path="/overlay" element={<OverlayProjection />} />
          <Route path="/streaming" element={<StreamingDiagnostics />} />
          <Route path="/structured-lighting" element={<StructuredLighting />} />
          <Route path="/scene-control" element={<SceneControl />} />
          <Route path="/projection-animation" element={<ProjectionAnimation />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </ThemeProvider>
  );
}

export default App;
