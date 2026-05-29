import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Layout from '../components/Layout';

test('labels nested routes with their parent workflow instead of Not Found', () => {
  render(
    <MemoryRouter initialEntries={['/devices/42']}>
      <Layout>
        <div>Device details</div>
      </Layout>
    </MemoryRouter>
  );

  expect(screen.getAllByText('Devices').length).toBeGreaterThan(0);
  expect(screen.queryByText('Not Found')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /help/i })).not.toBeInTheDocument();
});


test('labels hidden experimental direct routes from the full route map', () => {
  render(
    <MemoryRouter initialEntries={['/renderer']}>
      <Layout>
        <div>Renderer page</div>
      </Layout>
    </MemoryRouter>
  );

  expect(screen.getByText('Renderer')).toBeInTheDocument();
  expect(screen.queryByText('Not Found')).not.toBeInTheDocument();
});
