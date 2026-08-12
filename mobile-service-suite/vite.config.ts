import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// Renderer (React) build configuration.
// The Electron main process is compiled separately via `tsc` (see electron/tsconfig.json).
export default defineConfig({
  // Relative base so the packaged app can load assets from the file:// protocol.
  base: './',
  root: 'frontend',
  plugins: [react()],
  resolve: {
    alias: {
      '@core': fileURLToPath(new URL('./core', import.meta.url)),
      '@shared': fileURLToPath(new URL('./shared', import.meta.url)),
      '@modules': fileURLToPath(new URL('./modules', import.meta.url)),
      '@frontend': fileURLToPath(new URL('./frontend/src', import.meta.url)),
    },
  },
  build: {
    outDir: '../dist/renderer',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
