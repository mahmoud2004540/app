import type { SqliteDatabase } from '../connection';
import type { LogRow, LogStatus } from '../types';

export interface NewLogEntry {
  level?: LogStatus;
  user?: string | null;
  device?: string | null;
  tool?: string | null;
  operation?: string | null;
  command?: string | null;
  result?: string | null;
  error?: string | null;
}

export interface LogQuery {
  level?: LogStatus;
  search?: string;
  limit?: number;
}

/** Append-and-query access to the audit log (`logs` table). */
export class LogRepository {
  constructor(private readonly db: SqliteDatabase) {}

  append(entry: NewLogEntry): LogRow {
    const info = this.db
      .prepare(
        `INSERT INTO logs (level, user, device, tool, operation, command, result, error)
         VALUES (@level, @user, @device, @tool, @operation, @command, @result, @error)`,
      )
      .run({
        level: entry.level ?? 'INFO',
        user: entry.user ?? null,
        device: entry.device ?? null,
        tool: entry.tool ?? null,
        operation: entry.operation ?? null,
        command: entry.command ?? null,
        result: entry.result ?? null,
        error: entry.error ?? null,
      });
    const row = this.db
      .prepare('SELECT * FROM logs WHERE id = ?')
      .get(Number(info.lastInsertRowid)) as LogRow | undefined;
    if (!row) throw new Error('Failed to load log after insert');
    return row;
  }

  query(filter: LogQuery = {}): LogRow[] {
    const clauses: string[] = [];
    const params: Record<string, string> = {};

    if (filter.level) {
      clauses.push('level = @level');
      params.level = filter.level;
    }
    if (filter.search) {
      clauses.push('(operation LIKE @search OR command LIKE @search OR result LIKE @search)');
      params.search = `%${filter.search}%`;
    }

    const where = clauses.length ? `WHERE ${clauses.join(' AND ')}` : '';
    const limit = filter.limit && filter.limit > 0 ? `LIMIT ${Math.floor(filter.limit)}` : '';
    return this.db
      .prepare(`SELECT * FROM logs ${where} ORDER BY id DESC ${limit}`)
      .all(params) as LogRow[];
  }

  count(): number {
    const row = this.db.prepare('SELECT COUNT(*) AS n FROM logs').get() as { n: number };
    return row.n;
  }

  clear(): number {
    return this.db.prepare('DELETE FROM logs').run().changes;
  }
}
