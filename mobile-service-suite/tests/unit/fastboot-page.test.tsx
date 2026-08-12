import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { I18nProvider } from '@frontend/i18n/I18nProvider';
import { FastbootPage } from '@frontend/pages/FastbootPage';

describe('FastbootPage (PHASE 7)', () => {
  it('renders info, power, lock and partition groups', () => {
    render(
      <I18nProvider>
        <FastbootPage />
      </I18nProvider>,
    );
    for (const heading of ['Information', 'Power', 'Bootloader Lock', 'Partitions', 'Console']) {
      expect(screen.getByText(heading)).toBeInTheDocument();
    }
    expect(screen.getByText('Unlock Bootloader')).toBeInTheDocument();
    expect(screen.getByText('Flash Partition')).toBeInTheDocument();
  });
});
