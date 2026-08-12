import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from './theme/ThemeProvider';
import { I18nProvider } from './i18n/I18nProvider';
import { AppLayout } from './components/layout/AppLayout';
import { PagePlaceholder } from './components/PagePlaceholder';
import { DashboardPage } from './pages/DashboardPage';
import { AdbPage } from './pages/AdbPage';
import { FastbootPage } from './pages/FastbootPage';
import { NAV_ITEMS } from './config/navigation';

/**
 * Root component.
 *
 * PHASE 2 wires the full application shell: providers (theme + i18n), the
 * sidebar/top-bar layout, and hash-based routing over every navigation item.
 * Each route currently renders a placeholder; feature pages replace them in
 * their respective phases (Dashboard in PHASE 3, and so on).
 */
/** Map a nav id to its implemented page, or null to fall back to a placeholder. */
function pageForItem(id: string): JSX.Element | null {
  switch (id) {
    case 'dashboard':
      return <DashboardPage />;
    case 'adb':
      return <AdbPage />;
    case 'fastboot':
      return <FastbootPage />;
    default:
      return null;
  }
}

export function App(): JSX.Element {
  return (
    <ThemeProvider>
      <I18nProvider>
        <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route element={<AppLayout />}>
              {NAV_ITEMS.map((item) => (
                <Route
                  key={item.id}
                  path={item.path}
                  element={pageForItem(item.id) ?? <PagePlaceholder item={item} />}
                />
              ))}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </HashRouter>
      </I18nProvider>
    </ThemeProvider>
  );
}
