import type { Migration } from './types';

/** Initial schema: every core table for the suite. */
export const migration001Init: Migration = {
  version: 1,
  name: 'init',
  up: (db) => {
    db.exec(`
      CREATE TABLE users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL CHECK (role IN ('admin', 'technician', 'viewer')),
        display_name  TEXT NOT NULL DEFAULT '',
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE devices (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        serial          TEXT NOT NULL UNIQUE,
        brand           TEXT,
        model           TEXT,
        imei            TEXT,
        android_version TEXT,
        build_number    TEXT,
        chipset         TEXT,
        first_seen_at   TEXT NOT NULL DEFAULT (datetime('now')),
        last_seen_at    TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE repair_sessions (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id      INTEGER REFERENCES devices(id) ON DELETE SET NULL,
        customer_name  TEXT NOT NULL,
        customer_phone TEXT,
        brand          TEXT,
        model          TEXT,
        imei           TEXT,
        serial         TEXT,
        problem        TEXT,
        technician     TEXT,
        status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
        created_at     TEXT NOT NULL DEFAULT (datetime('now')),
        closed_at      TEXT
      );

      CREATE TABLE tools (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        key              TEXT NOT NULL UNIQUE,
        name             TEXT NOT NULL,
        version          TEXT,
        path             TEXT,
        installed        INTEGER NOT NULL DEFAULT 0 CHECK (installed IN (0, 1)),
        supported_brands TEXT,
        updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE drivers (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        key        TEXT NOT NULL UNIQUE,
        name       TEXT NOT NULL,
        version    TEXT,
        installed  INTEGER NOT NULL DEFAULT 0 CHECK (installed IN (0, 1)),
        status     TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE firmwares (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        brand            TEXT,
        model            TEXT,
        region           TEXT,
        android_version  TEXT,
        build_number     TEXT,
        firmware_version TEXT,
        file_path        TEXT,
        sha256           TEXT,
        size_bytes       INTEGER,
        imported_at      TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE operations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER REFERENCES repair_sessions(id) ON DELETE SET NULL,
        device_id  INTEGER REFERENCES devices(id) ON DELETE SET NULL,
        category   TEXT NOT NULL,
        command    TEXT,
        result     TEXT,
        status     TEXT NOT NULL DEFAULT 'INFO' CHECK (status IN ('SUCCESS', 'FAILED', 'WARNING', 'INFO')),
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE logs (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL DEFAULT (datetime('now')),
        level     TEXT NOT NULL DEFAULT 'INFO' CHECK (level IN ('SUCCESS', 'FAILED', 'WARNING', 'INFO')),
        user      TEXT,
        device    TEXT,
        tool      TEXT,
        operation TEXT,
        command   TEXT,
        result    TEXT,
        error     TEXT
      );

      CREATE TABLE backups (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id  INTEGER REFERENCES devices(id) ON DELETE SET NULL,
        type       TEXT NOT NULL,
        location   TEXT,
        encrypted  INTEGER NOT NULL DEFAULT 0 CHECK (encrypted IN (0, 1)),
        size_bytes INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE reports (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER REFERENCES repair_sessions(id) ON DELETE SET NULL,
        file_path  TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE settings (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE INDEX idx_logs_timestamp ON logs(timestamp);
      CREATE INDEX idx_logs_level ON logs(level);
      CREATE INDEX idx_operations_session ON operations(session_id);
      CREATE INDEX idx_repair_sessions_status ON repair_sessions(status);
    `);
  },
};
