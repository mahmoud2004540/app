import { describe, it, expect } from 'vitest';
import { TRANSLATION_KEYS } from '@frontend/i18n/keys';
import { en } from '@frontend/i18n/locales/en';
import { ar } from '@frontend/i18n/locales/ar';
import { it as itLocale } from '@frontend/i18n/locales/it';
import { SUPPORTED_LOCALES } from '@shared/constants/app';

describe('i18n locales', () => {
  const locales = { en, ar, it: itLocale };

  it('supports exactly the declared locales', () => {
    expect(Object.keys(locales).sort()).toEqual([...SUPPORTED_LOCALES].sort());
  });

  it('every locale defines every translation key with a non-empty string', () => {
    for (const [name, dict] of Object.entries(locales)) {
      for (const key of TRANSLATION_KEYS) {
        expect(dict[key], `${name} is missing "${key}"`).toBeTruthy();
      }
    }
  });

  it('interpolation placeholder is preserved in the phase templates', () => {
    for (const dict of Object.values(locales)) {
      expect(dict['page.wipBody']).toContain('{phase}');
    }
  });
});
