import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { I18nProvider } from '@frontend/i18n/I18nProvider';
import { DriversPage } from '@frontend/pages/DriversPage';

describe('DriversPage (PHASE 8)', () => {
  it('renders the header, consent banner and Device Manager action', () => {
    render(
      <I18nProvider>
        <DriversPage />
      </I18nProvider>,
    );
    expect(screen.getByText('Drivers')).toBeInTheDocument();
    expect(screen.getByText(/never installs drivers automatically/i)).toBeInTheDocument();
    expect(screen.getByText('Open Device Manager')).toBeInTheDocument();
  });
});
