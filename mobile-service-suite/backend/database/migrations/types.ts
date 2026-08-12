import type { SqliteDatabase } from '../connection';

/** A single, ordered, forward-only schema change. */
export interface Migration {
  readonly version: number;
  readonly name: string;
  readonly up: (db: SqliteDatabase) => void;
}
