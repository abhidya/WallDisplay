import React from 'react';
import { Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { Home as HomeIcon } from '@mui/icons-material';
import StatusPanel from '../components/StatusPanel';

function NotFound() {
  const navigate = useNavigate();

  return (
    <StatusPanel
      severity="info"
      title="Page Not Found"
      description="The page you are looking for does not exist or has been moved."
      action={(
        <Button
          variant="contained"
          color="primary"
          startIcon={<HomeIcon />}
          onClick={() => navigate('/')}
        >
          Back to Dashboard
        </Button>
      )}
    />
  );
}

export default NotFound;
