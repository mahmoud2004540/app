import type { SqliteDatabase } from '../connection';
import type { UserRow } from '../types';
import type { UserRole } from '@shared/constants/app';

export interface NewUser {
  username: string;
  passwordHash: string;
  role: UserRole;
  displayName?: string;
}

/** CRUD for application users (Repository Pattern). Password hashing is done by
 *  the service layer; this repository only stores the hash. */
export class UserRepository {
  constructor(private readonly db: SqliteDatabase) {}

  create(user: NewUser): UserRow {
    const info = this.db
      .prepare(
        `INSERT INTO users (username, password_hash, role, display_name)
         VALUES (?, ?, ?, ?)`,
      )
      .run(user.username, user.passwordHash, user.role, user.displayName ?? '');
    const created = this.findById(Number(info.lastInsertRowid));
    if (!created) throw new Error('Failed to load user after insert');
    return created;
  }

  findById(id: number): UserRow | null {
    return (this.db.prepare('SELECT * FROM users WHERE id = ?').get(id) as UserRow | undefined) ?? null;
  }

  findByUsername(username: string): UserRow | null {
    return (
      (this.db.prepare('SELECT * FROM users WHERE username = ?').get(username) as
        | UserRow
        | undefined) ?? null
    );
  }

  findAll(): UserRow[] {
    return this.db.prepare('SELECT * FROM users ORDER BY id').all() as UserRow[];
  }

  delete(id: number): boolean {
    return this.db.prepare('DELETE FROM users WHERE id = ?').run(id).changes > 0;
  }
}
