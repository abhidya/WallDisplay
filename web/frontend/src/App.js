import React from 'react';
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

// Create a theme instance
const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
});

function App() {
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
          <Route path="/projection-animation" element={<ProjectionAnimation />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </ThemeProvider>
  );
}

export default App;
