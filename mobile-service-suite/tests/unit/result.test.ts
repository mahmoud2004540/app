import { describe, it, expect } from 'vitest';
import { ok, err, type Result } from '@shared/types/result';

describe('Result helpers', () => {
  it('constructs a success result', () => {
    const r: Result<number> = ok(42);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.value).toBe(42);
  });

  it('constructs an error result', () => {
    const r: Result<number> = err('boom');
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toBe('boom');
  });
});
