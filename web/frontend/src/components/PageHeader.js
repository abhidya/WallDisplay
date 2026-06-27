import React from 'react';
import { Box, Stack, Typography } from '@mui/material';

function PageHeader({ title, subtitle, actions, meta }) {
  return (
    <Box
      sx={{
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        boxShadow: 1,
        p: { xs: 2, md: 3 },
      }}
    >
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={2}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', md: 'center' }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h4" gutterBottom={Boolean(subtitle)}>
            {title}
          </Typography>
          {subtitle ? (
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 760 }}>
              {subtitle}
            </Typography>
          ) : null}
          {meta ? (
            <Box sx={{ mt: 1 }}>
              {meta}
            </Box>
          ) : null}
        </Box>
        {actions ? (
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {actions}
          </Stack>
        ) : null}
      </Stack>
    </Box>
  );
}

export default PageHeader;
