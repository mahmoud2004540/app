import { describe, it, expect } from 'vitest';
import { NAV_GROUPS, NAV_ITEMS } from '@frontend/config/navigation';

describe('navigation config', () => {
  it('exposes all 13 sidebar destinations', () => {
    expect(NAV_ITEMS).toHaveLength(13);
  });

  it('has a single dashboard route at "/"', () => {
    const roots = NAV_ITEMS.filter((i) => i.path === '/');
    expect(roots).toHaveLength(1);
    expect(roots[0]?.id).toBe('dashboard');
  });

  it('has unique ids and paths', () => {
    expect(new Set(NAV_ITEMS.map((i) => i.id)).size).toBe(NAV_ITEMS.length);
    expect(new Set(NAV_ITEMS.map((i) => i.path)).size).toBe(NAV_ITEMS.length);
  });

  it('flattening the groups yields the flat item list', () => {
    expect(NAV_GROUPS.flatMap((g) => g.items)).toEqual(NAV_ITEMS);
  });
});
