import React from 'react';
import { Box, Button, CircularProgress, Typography } from '@mui/material';

function StatusPanel({
  action,
  title,
  description,
  icon,
  message,
  actionLabel,
  onAction,
  severity = 'info',
  loading = false,
}) {
  const color = severity === 'error' ? 'error.main' : 'text.primary';
  const body = description || message;

  return (
    <Box
      sx={{
        alignItems: 'flex-start',
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        boxShadow: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        maxWidth: '100%',
        p: { xs: 2, md: 3 },
        width: { xs: '100%', sm: 560 },
      }}
    >
      {icon || null}
      {loading ? <CircularProgress size={28} /> : null}
      <Typography color={color} variant="subtitle1" fontWeight={700}>
        {title}
      </Typography>
      {body ? (
        <Typography variant="body2" color="text.secondary">
          {body}
        </Typography>
      ) : null}
      {action || null}
      {actionLabel && onAction ? (
        <Button variant="contained" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </Box>
  );
}

export default StatusPanel;
