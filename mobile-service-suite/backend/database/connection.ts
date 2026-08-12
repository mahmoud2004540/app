import Database from 'better-sqlite3';

/** Concrete SQLite handle type, independent of how the default export is named. */
export type SqliteDatabase = InstanceType<typeof Database>;

export interface OpenDatabaseOptions {
  /** File path, or ':memory:' for an ephemeral database (used in tests). */
  filename: string;
  readonly?: boolean;
}

/**
 * Open (creating if needed) a SQLite database with the pragmas the suite relies
 * on: foreign-key enforcement and WAL journaling for concurrent reads.
 */
export function openDatabase({ filename, readonly = false }: OpenDatabaseOptions): SqliteDatabase {
  const db = new Database(filename, { readonly });
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  return db;
}
