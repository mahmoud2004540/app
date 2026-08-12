import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { App } from '@frontend/App';

describe('App (PHASE 1 shell)', () => {
  it('renders the application name and phase status', () => {
    render(<App />);
    expect(screen.getByText('Mobile Service Suite')).toBeInTheDocument();
    expect(screen.getByText(/PHASE 1/)).toBeInTheDocument();
  });
});
