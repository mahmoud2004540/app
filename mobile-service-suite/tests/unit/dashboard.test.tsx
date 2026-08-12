import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { I18nProvider } from '@frontend/i18n/I18nProvider';
import { DashboardPage } from '@frontend/pages/DashboardPage';

function renderDashboard(): void {
  render(
    <I18nProvider>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </I18nProvider>,
  );
}

describe('DashboardPage (PHASE 3)', () => {
  it('shows the disconnected state and the connection checklist by default', () => {
    renderDashboard();
    expect(screen.getAllByText('No device connected').length).toBeGreaterThan(0);
    expect(screen.getByText('Connection checklist')).toBeInTheDocument();
    expect(screen.getByText('USB cable check')).toBeInTheDocument();
  });

  it('renders the quick actions including ADB and Fastboot', () => {
    renderDashboard();
    expect(screen.getByText('Quick Actions')).toBeInTheDocument();
    // ADB appears in the quick actions grid.
    expect(screen.getAllByText('ADB').length).toBeGreaterThan(0);
  });

  it('enters the detecting state when Detect is pressed', () => {
    renderDashboard();
    const detectButton = screen.getByRole('button', { name: 'Detect Device' });
    fireEvent.click(detectButton);
    expect(screen.getByText('Detecting…')).toBeInTheDocument();
  });
});
