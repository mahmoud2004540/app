import type { SqliteDatabase } from '../connection';
import type { SettingRow } from '../types';

/** Key/value application settings persisted in the `settings` table. */
export class SettingsRepository {
  constructor(private readonly db: SqliteDatabase) {}

  get(key: string): string | null {
    const row = this.db.prepare('SELECT value FROM settings WHERE key = ?').get(key) as
      | Pick<SettingRow, 'value'>
      | undefined;
    return row?.value ?? null;
  }

  set(key: string, value: string): void {
    this.db
      .prepare(
        `INSERT INTO settings (key, value, updated_at)
         VALUES (?, ?, datetime('now'))
         ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')`,
      )
      .run(key, value);
  }

  getAll(): Record<string, string> {
    const rows = this.db.prepare('SELECT key, value FROM settings').all() as Array<
      Pick<SettingRow, 'key' | 'value'>
    >;
    return Object.fromEntries(rows.map((r) => [r.key, r.value]));
  }

  delete(key: string): boolean {
    return this.db.prepare('DELETE FROM settings WHERE key = ?').run(key).changes > 0;
  }
}
