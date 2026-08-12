import type { SqliteDatabase } from '../connection';
import type { ToolRow } from '../types';

/** Persists user-configured tool paths in the `tools` table. */
export class ToolRepository {
  constructor(private readonly db: SqliteDatabase) {}

  getPath(key: string): string | null {
    const row = this.db.prepare('SELECT path FROM tools WHERE key = ?').get(key) as
      | Pick<ToolRow, 'path'>
      | undefined;
    return row?.path ?? null;
  }

  setPath(key: string, name: string, path: string): void {
    this.db
      .prepare(
        `INSERT INTO tools (key, name, path, installed, updated_at)
         VALUES (?, ?, ?, 1, datetime('now'))
         ON CONFLICT(key) DO UPDATE SET
           path = excluded.path,
           name = excluded.name,
           installed = 1,
           updated_at = datetime('now')`,
      )
      .run(key, name, path);
  }

  all(): ToolRow[] {
    return this.db.prepare('SELECT * FROM tools ORDER BY key').all() as ToolRow[];
  }
}
