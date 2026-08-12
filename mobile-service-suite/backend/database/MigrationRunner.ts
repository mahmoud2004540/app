import type { SqliteDatabase } from './connection';
import { MIGRATIONS, type Migration } from './migrations';

interface VersionRow {
  version: number;
}

/**
 * Applies pending migrations in order, each inside a transaction, and records
 * the applied version in `schema_migrations`. Idempotent: running twice is a
 * no-op once every migration has been applied.
 */
export class MigrationRunner {
  constructor(
    private readonly db: SqliteDatabase,
    private readonly migrations: readonly Migration[] = MIGRATIONS,
  ) {}

  private ensureMigrationsTable(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version    INTEGER PRIMARY KEY,
        name       TEXT NOT NULL,
        applied_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
    `);
  }

  currentVersion(): number {
    this.ensureMigrationsTable();
    const row = this.db
      .prepare('SELECT MAX(version) AS version FROM schema_migrations')
      .get() as VersionRow | undefined;
    return row?.version ?? 0;
  }

  /** Apply all migrations whose version is greater than the current version. */
  migrate(): number {
    this.ensureMigrationsTable();
    const from = this.currentVersion();
    const pending = [...this.migrations]
      .sort((a, b) => a.version - b.version)
      .filter((m) => m.version > from);

    const record = this.db.prepare(
      'INSERT INTO schema_migrations (version, name) VALUES (?, ?)',
    );

    for (const migration of pending) {
      const apply = this.db.transaction(() => {
        migration.up(this.db);
        record.run(migration.version, migration.name);
      });
      apply();
    }

    return pending.length;
  }
}
