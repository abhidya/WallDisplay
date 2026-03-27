import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar,
  Box,
  CssBaseline,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Button,
  Tooltip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Devices as DevicesIcon,
  VideoLibrary as VideoLibraryIcon,
  PhotoLibrary as PhotoLibraryIcon,
  Settings as SettingsIcon,
  ViewInAr as RendererIcon,
  Layers as DepthIcon,
  CameraAlt as ProjectionIcon,
  GridOn as OverlayIcon,
  Animation as AnimationIcon,
  AccountTree as MappingIcon,
  Insights as DiagnosticsIcon,
  QrCode2 as StructuredLightingIcon,
  ViewAgenda as SceneControlIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
} from '@mui/icons-material';

const drawerWidth = 240;
const collapsedDrawerWidth = 64;

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Devices', icon: <DevicesIcon />, path: '/devices' },
  { text: 'Videos', icon: <VideoLibraryIcon />, path: '/videos' },
  { text: 'Photos', icon: <PhotoLibraryIcon />, path: '/photos' },
  { text: 'Renderer', icon: <RendererIcon />, path: '/renderer' },
  { text: 'Depth Processing', icon: <DepthIcon />, path: '/depth' },
  { text: 'Projection Mapping', icon: <ProjectionIcon />, path: '/projection' },
  { text: 'Mappings', icon: <MappingIcon />, path: '/mappings' },
  { text: 'Structured Lighting', icon: <StructuredLightingIcon />, path: '/structured-lighting' },
  { text: 'Scene Control', icon: <SceneControlIcon />, path: '/scene-control' },
  { text: 'Overlay', icon: <OverlayIcon />, path: '/overlay' },
  { text: 'Streaming', icon: <DiagnosticsIcon />, path: '/streaming' },
  { text: 'Projection Animation', icon: <AnimationIcon />, path: '/projection-animation' },
  { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
];

function Layout({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [drawerCollapsed, setDrawerCollapsed] = useState(() => {
    // Initialize from localStorage
    const saved = localStorage.getItem('drawerCollapsed');
    return saved === 'true';
  });
  const navigate = useNavigate();
  const location = useLocation();

  // Save collapsed state to localStorage when it changes
  useEffect(() => {
    localStorage.setItem('drawerCollapsed', drawerCollapsed.toString());
  }, [drawerCollapsed]);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleDrawerCollapse = () => {
    setDrawerCollapsed(!drawerCollapsed);
  };

  const handleNavigation = (path) => {
    navigate(path);
    setMobileOpen(false);
  };

  const drawer = (
    <div>
      <Toolbar sx={{ justifyContent: drawerCollapsed ? 'center' : 'space-between' }}>
        {!drawerCollapsed && (
          <Typography variant="h6" noWrap component="div">
            nano-dlna
          </Typography>
        )}
        <IconButton onClick={handleDrawerCollapse} sx={{ ml: drawerCollapsed ? 0 : 'auto' }}>
          {drawerCollapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
        </IconButton>
      </Toolbar>
      <Divider />
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <Tooltip title={drawerCollapsed ? item.text : ''} placement="right">
              <ListItemButton
                selected={location.pathname === item.path}
                onClick={() => handleNavigation(item.path)}
                sx={{
                  justifyContent: drawerCollapsed ? 'center' : 'flex-start',
                  px: drawerCollapsed ? 1 : 2,
                }}
              >
                <ListItemIcon sx={{ 
                  minWidth: drawerCollapsed ? 0 : 56,
                  justifyContent: 'center' 
                }}>
                  {item.icon}
                </ListItemIcon>
                {!drawerCollapsed && <ListItemText primary={item.text} />}
              </ListItemButton>
            </Tooltip>
          </ListItem>
        ))}
      </List>
    </div>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerCollapsed ? collapsedDrawerWidth : drawerWidth}px)` },
          ml: { sm: `${drawerCollapsed ? collapsedDrawerWidth : drawerWidth}px` },
          transition: theme => theme.transitions.create(['margin', 'width'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            {menuItems.find((item) => item.path === location.pathname)?.text || 'Not Found'}
          </Typography>
          <Button color="inherit">Help</Button>
        </Toolbar>
      </AppBar>
      <Box
        component="nav"
        sx={{ 
          width: { sm: drawerCollapsed ? collapsedDrawerWidth : drawerWidth }, 
          flexShrink: { sm: 0 },
          transition: theme => theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
        aria-label="mailbox folders"
      >
        {/* The implementation can be swapped with js to avoid SEO duplication of links. */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile.
          }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': { 
              boxSizing: 'border-box', 
              width: drawerCollapsed ? collapsedDrawerWidth : drawerWidth,
              transition: theme => theme.transitions.create('width', {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.leavingScreen,
              }),
              overflowX: 'hidden',
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
      <Box
        component="main"
        sx={{ 
          flexGrow: 1, 
          p: 3, 
          width: { sm: `calc(100% - ${drawerCollapsed ? collapsedDrawerWidth : drawerWidth}px)` },
          ml: { sm: `${drawerCollapsed ? collapsedDrawerWidth : drawerWidth}px` },
          transition: theme => theme.transitions.create(['margin', 'width'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}

export default Layout;
