import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { I18nProvider } from '@frontend/i18n/I18nProvider';
import { AdbPage } from '@frontend/pages/AdbPage';

describe('AdbPage (PHASE 6)', () => {
  it('renders all operation groups and the console', () => {
    render(
      <I18nProvider>
        <AdbPage />
      </I18nProvider>,
    );
    for (const heading of ['Connection', 'Power', 'Applications', 'Files', 'Diagnostics', 'Console']) {
      expect(screen.getByText(heading)).toBeInTheDocument();
    }
    // Sensitive power actions are present.
    expect(screen.getByText('Reboot to Recovery')).toBeInTheDocument();
    expect(screen.getByText('Reboot to Bootloader')).toBeInTheDocument();
  });
});
