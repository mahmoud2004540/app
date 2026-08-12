// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { openDatabase } from '@backend/database/connection';
import { MigrationRunner } from '@backend/database/MigrationRunner';

const EXPECTED_TABLES = [
  'users',
  'devices',
  'repair_sessions',
  'tools',
  'drivers',
  'firmwares',
  'operations',
  'logs',
  'backups',
  'reports',
  'settings',
];

describe('database migrations', () => {
  it('creates every table and records the schema version', () => {
    const db = openDatabase({ filename: ':memory:' });
    const runner = new MigrationRunner(db);

    expect(runner.currentVersion()).toBe(0);
    const applied = runner.migrate();
    expect(applied).toBe(1);
    expect(runner.currentVersion()).toBe(1);

    const tables = (
      db.prepare("SELECT name FROM sqlite_master WHERE type = 'table'").all() as Array<{
        name: string;
      }>
    ).map((r) => r.name);

    for (const table of EXPECTED_TABLES) {
      expect(tables, `missing table: ${table}`).toContain(table);
    }
    db.close();
  });

  it('is idempotent — a second migrate applies nothing', () => {
    const db = openDatabase({ filename: ':memory:' });
    const runner = new MigrationRunner(db);
    runner.migrate();
    expect(runner.migrate()).toBe(0);
    expect(runner.currentVersion()).toBe(1);
    db.close();
  });

  it('enforces foreign keys', () => {
    const db = openDatabase({ filename: ':memory:' });
    expect(db.pragma('foreign_keys', { simple: true })).toBe(1);
    db.close();
  });
});
