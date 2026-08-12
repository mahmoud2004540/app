/** @type {import('tailwindcss').Config} */
export default {
  content: ['./frontend/index.html', './frontend/src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Brand palette for the Mobile Service Suite dark UI.
        brand: {
          50: '#e8f0ff',
          100: '#c7d9ff',
          200: '#94b4ff',
          300: '#5f8dff',
          400: '#3a6dff',
          500: '#1f4fe0',
          600: '#173db0',
          700: '#122f88',
          800: '#0d2160',
          900: '#08143c',
        },
        surface: {
          DEFAULT: '#0f1420',
          raised: '#161c2b',
          overlay: '#1e2636',
          border: '#28324a',
        },
        status: {
          good: '#22c55e',
          warning: '#f59e0b',
          error: '#ef4444',
          info: '#3b82f6',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
