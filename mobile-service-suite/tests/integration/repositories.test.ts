// @vitest-environment node
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { AppDatabase } from '@backend/database/Database';

describe('repositories', () => {
  let db: AppDatabase;

  beforeEach(() => {
    db = AppDatabase.open(':memory:');
  });

  afterEach(() => {
    db.close();
  });

  describe('SettingsRepository', () => {
    it('sets, updates, reads and deletes settings', () => {
      expect(db.settings.get('theme')).toBeNull();
      db.settings.set('theme', 'dark');
      expect(db.settings.get('theme')).toBe('dark');
      db.settings.set('theme', 'light'); // upsert
      expect(db.settings.get('theme')).toBe('light');
      db.settings.set('locale', 'ar');
      expect(db.settings.getAll()).toEqual({ theme: 'light', locale: 'ar' });
      expect(db.settings.delete('theme')).toBe(true);
      expect(db.settings.get('theme')).toBeNull();
    });
  });

  describe('UserRepository', () => {
    it('creates and finds users and enforces unique usernames', () => {
      const user = db.users.create({
        username: 'tech1',
        passwordHash: 'hash',
        role: 'technician',
        displayName: 'Tech One',
      });
      expect(user.id).toBeGreaterThan(0);
      expect(db.users.findByUsername('tech1')?.display_name ?? null).toBe('Tech One');
      expect(db.users.findAll()).toHaveLength(1);
      expect(() =>
        db.users.create({ username: 'tech1', passwordHash: 'x', role: 'viewer' }),
      ).toThrow();
    });
  });

  describe('DeviceRepository', () => {
    it('upserts by serial, preserving existing fields on null', () => {
      const created = db.devices.upsert({ serial: 'ABC123', brand: 'Samsung', model: 'S21' });
      expect(created.brand).toBe('Samsung');

      // Second upsert with model omitted keeps the old model (COALESCE).
      const updated = db.devices.upsert({ serial: 'ABC123', imei: '35900011' });
      expect(updated.id).toBe(created.id);
      expect(updated.model).toBe('S21');
      expect(updated.imei).toBe('35900011');
      expect(db.devices.findAll()).toHaveLength(1);
    });
  });

  describe('LogRepository', () => {
    it('appends and queries the audit log', () => {
      db.logs.append({ level: 'INFO', operation: 'detect', result: 'ok' });
      db.logs.append({ level: 'FAILED', operation: 'flash', error: 'timeout' });
      db.logs.append({ level: 'SUCCESS', operation: 'backup contacts' });

      expect(db.logs.count()).toBe(3);
      expect(db.logs.query({ level: 'FAILED' })).toHaveLength(1);
      expect(db.logs.query({ search: 'backup' })).toHaveLength(1);
      // Most recent first.
      expect(db.logs.query({ limit: 1 })[0]?.operation).toBe('backup contacts');
      expect(db.logs.clear()).toBe(3);
      expect(db.logs.count()).toBe(0);
    });
  });
});
