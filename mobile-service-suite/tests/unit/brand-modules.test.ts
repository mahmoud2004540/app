import { describe, it, expect } from 'vitest';
import {
  ALL_MODULES,
  createModuleRegistry,
  recommendToolsForDevice,
} from '@modules/registry';
import { toolDisplayName } from '@modules/toolNames';

describe('brand & platform modules', () => {
  it('registers all 18 modules (15 brands + 3 platforms) without id clashes', () => {
    expect(ALL_MODULES).toHaveLength(18);
    const registry = createModuleRegistry();
    expect(registry.size).toBe(18);
    expect(registry.list().filter((m) => m.kind === 'platform')).toHaveLength(3);
    expect(registry.list().filter((m) => m.kind === 'brand')).toHaveLength(15);
  });

  it('recommends Odin for Samsung and QFIL for a Qualcomm chipset', () => {
    const rec = recommendToolsForDevice({ brand: 'Samsung', chipset: 'Qualcomm Snapdragon SM8350' });
    expect(rec.brand?.id).toBe('samsung');
    expect(rec.platform?.id).toBe('qualcomm');
    expect(rec.tools).toEqual(expect.arrayContaining(['odin', 'qfil', 'adb', 'fastboot']));
  });

  it('recommends SP Flash Tool for MediaTek and Mi Flash for Xiaomi', () => {
    expect(recommendToolsForDevice({ chipset: 'mt6768' }).tools).toContain('spflash');
    expect(recommendToolsForDevice({ brand: 'Redmi' }).brand?.id).toBe('xiaomi');
    expect(recommendToolsForDevice({ brand: 'Redmi' }).tools).toContain('miflash');
  });

  it('recommends ResearchDownload for Unisoc', () => {
    expect(recommendToolsForDevice({ chipset: 'ums9230' }).tools).toContain('researchdownload');
  });

  it('always includes the adb/fastboot baseline even for unknown devices', () => {
    const rec = recommendToolsForDevice({ brand: 'UnknownBrand', chipset: 'mystery' });
    expect(rec.brand).toBeNull();
    expect(rec.platform).toBeNull();
    expect(rec.tools).toEqual(['adb', 'fastboot']);
  });

  it('maps tool keys to display names', () => {
    expect(toolDisplayName('odin')).toBe('Odin');
    expect(toolDisplayName('spflash')).toBe('SP Flash Tool');
    expect(toolDisplayName('mystery')).toBe('mystery');
  });
});
