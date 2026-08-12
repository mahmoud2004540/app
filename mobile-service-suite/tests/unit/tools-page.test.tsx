import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { I18nProvider } from '@frontend/i18n/I18nProvider';
import { ToolsPage } from '@frontend/pages/ToolsPage';

describe('ToolsPage (PHASE 9)', () => {
  it('renders the header and the launcher/no-cracking notice', () => {
    render(
      <I18nProvider>
        <ToolsPage />
      </I18nProvider>,
    );
    expect(screen.getByText('Tools')).toBeInTheDocument();
    expect(screen.getByText(/never bundles, modifies, or circumvents/i)).toBeInTheDocument();
  });
});
