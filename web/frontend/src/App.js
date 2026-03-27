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
        main: themeMode === 'dark' ? '#7cc6ff' : '#1976d2',
      },
      secondary: {
        main: themeMode === 'dark' ? '#ff7da5' : '#dc004e',
      },
      background: themeMode === 'dark'
        ? {
            default: '#111418',
            paper: '#1a2027',
          }
        : {
            default: '#f5f5f5',
            paper: '#ffffff',
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
