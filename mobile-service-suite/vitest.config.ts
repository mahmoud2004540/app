import { defineConfig } from 'vitest/config';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  resolve: {
    alias: {
      '@core': fileURLToPath(new URL('./core', import.meta.url)),
      '@shared': fileURLToPath(new URL('./shared', import.meta.url)),
      '@modules': fileURLToPath(new URL('./modules', import.meta.url)),
      '@frontend': fileURLToPath(new URL('./frontend/src', import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
    coverage: {
      provider: 'v8',
      reportsDirectory: './coverage',
      include: ['core/**', 'shared/**', 'modules/**'],
    },
  },
});
