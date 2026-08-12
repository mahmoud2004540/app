import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from './theme/ThemeProvider';
import { I18nProvider } from './i18n/I18nProvider';
import { AppLayout } from './components/layout/AppLayout';
import { PagePlaceholder } from './components/PagePlaceholder';
import { NAV_ITEMS } from './config/navigation';

/**
 * Root component.
 *
 * PHASE 2 wires the full application shell: providers (theme + i18n), the
 * sidebar/top-bar layout, and hash-based routing over every navigation item.
 * Each route currently renders a placeholder; feature pages replace them in
 * their respective phases (Dashboard in PHASE 3, and so on).
 */
export function App(): JSX.Element {
  return (
    <ThemeProvider>
      <I18nProvider>
        <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route element={<AppLayout />}>
              {NAV_ITEMS.map((item) => (
                <Route key={item.id} path={item.path} element={<PagePlaceholder item={item} />} />
              ))}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </HashRouter>
      </I18nProvider>
    </ThemeProvider>
  );
}
