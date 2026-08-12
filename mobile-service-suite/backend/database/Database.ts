import { openDatabase, type SqliteDatabase } from './connection';
import { MigrationRunner } from './MigrationRunner';
import { SettingsRepository } from './repositories/SettingsRepository';
import { UserRepository } from './repositories/UserRepository';
import { DeviceRepository } from './repositories/DeviceRepository';
import { LogRepository } from './repositories/LogRepository';

/**
 * Application data layer facade.
 *
 * Owns the SQLite handle, runs migrations on open, and exposes typed
 * repositories. The Electron main process creates one instance and passes
 * repository calls through IPC handlers (added with each feature phase).
 */
export class AppDatabase {
  readonly settings: SettingsRepository;
  readonly users: UserRepository;
  readonly devices: DeviceRepository;
  readonly logs: LogRepository;

  private constructor(private readonly db: SqliteDatabase) {
    this.settings = new SettingsRepository(db);
    this.users = new UserRepository(db);
    this.devices = new DeviceRepository(db);
    this.logs = new LogRepository(db);
  }

  /** Open a database file (or ':memory:'), applying any pending migrations. */
  static open(filename: string): AppDatabase {
    const db = openDatabase({ filename });
    new MigrationRunner(db).migrate();
    return new AppDatabase(db);
  }

  /** Raw handle escape hatch for repositories added in later phases. */
  get connection(): SqliteDatabase {
    return this.db;
  }

  close(): void {
    this.db.close();
  }
}
