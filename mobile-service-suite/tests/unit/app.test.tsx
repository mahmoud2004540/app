import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { App } from '@frontend/App';
import { APP } from '@shared/constants/app';

describe('App (PHASE 2 shell)', () => {
  it('renders the sidebar brand and default Dashboard route', () => {
    render(<App />);
    // Brand name appears in the sidebar.
    expect(screen.getByText(APP.NAME)).toBeInTheDocument();
    // Dashboard is the default route ("/"), shown both in the nav and as the page title.
    expect(screen.getAllByText('Dashboard').length).toBeGreaterThan(0);
  });

  it('renders every navigation group heading', () => {
    render(<App />);
    for (const heading of ['Overview', 'Operations', 'Management', 'System']) {
      expect(screen.getByText(heading)).toBeInTheDocument();
    }
  });
});
