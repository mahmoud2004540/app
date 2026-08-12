import { describe, it, expect, beforeEach } from 'vitest';
import { ModuleRegistry } from '@core/application/services/ModuleRegistry';
import type { IBrandModule } from '@core/domain/services/IBrandModule';

const makeModule = (id: string, tools: string[]): IBrandModule => ({
  id,
  displayName: id,
  recommendedTools: tools,
  matches: (value) => value.toLowerCase().includes(id),
});

describe('ModuleRegistry', () => {
  let registry: ModuleRegistry;

  beforeEach(() => {
    registry = new ModuleRegistry();
  });

  it('registers and retrieves a module', () => {
    const samsung = makeModule('samsung', ['odin']);
    registry.register(samsung);
    expect(registry.get('samsung')).toBe(samsung);
    expect(registry.size).toBe(1);
  });

  it('rejects duplicate registration', () => {
    registry.register(makeModule('xiaomi', ['miflash']));
    expect(() => registry.register(makeModule('xiaomi', ['miflash']))).toThrow(
      /already registered/,
    );
  });

  it('finds the right module for a detected device string', () => {
    registry.register(makeModule('samsung', ['odin']));
    registry.register(makeModule('xiaomi', ['miflash']));
    const match = registry.findByDevice('SAMSUNG Galaxy S21');
    expect(match?.id).toBe('samsung');
    expect(match?.recommendedTools).toContain('odin');
  });

  it('returns undefined when no module matches', () => {
    registry.register(makeModule('samsung', ['odin']));
    expect(registry.findByDevice('Unknown Vendor')).toBeUndefined();
  });
});
