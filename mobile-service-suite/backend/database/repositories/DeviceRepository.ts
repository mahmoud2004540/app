import type { SqliteDatabase } from '../connection';
import type { DeviceRow } from '../types';

export interface DeviceUpsert {
  serial: string;
  brand?: string | null;
  model?: string | null;
  imei?: string | null;
  androidVersion?: string | null;
  buildNumber?: string | null;
  chipset?: string | null;
}

/** Persists devices seen by the suite, keyed by serial number. */
export class DeviceRepository {
  constructor(private readonly db: SqliteDatabase) {}

  /** Insert a new device or refresh an existing one (matched by serial). */
  upsert(device: DeviceUpsert): DeviceRow {
    this.db
      .prepare(
        `INSERT INTO devices (serial, brand, model, imei, android_version, build_number, chipset)
         VALUES (@serial, @brand, @model, @imei, @android_version, @build_number, @chipset)
         ON CONFLICT(serial) DO UPDATE SET
           brand = COALESCE(excluded.brand, brand),
           model = COALESCE(excluded.model, model),
           imei = COALESCE(excluded.imei, imei),
           android_version = COALESCE(excluded.android_version, android_version),
           build_number = COALESCE(excluded.build_number, build_number),
           chipset = COALESCE(excluded.chipset, chipset),
           last_seen_at = datetime('now')`,
      )
      .run({
        serial: device.serial,
        brand: device.brand ?? null,
        model: device.model ?? null,
        imei: device.imei ?? null,
        android_version: device.androidVersion ?? null,
        build_number: device.buildNumber ?? null,
        chipset: device.chipset ?? null,
      });
    const saved = this.findBySerial(device.serial);
    if (!saved) throw new Error('Failed to load device after upsert');
    return saved;
  }

  findById(id: number): DeviceRow | null {
    return (
      (this.db.prepare('SELECT * FROM devices WHERE id = ?').get(id) as DeviceRow | undefined) ?? null
    );
  }

  findBySerial(serial: string): DeviceRow | null {
    return (
      (this.db.prepare('SELECT * FROM devices WHERE serial = ?').get(serial) as
        | DeviceRow
        | undefined) ?? null
    );
  }

  findAll(): DeviceRow[] {
    return this.db.prepare('SELECT * FROM devices ORDER BY last_seen_at DESC').all() as DeviceRow[];
  }

  delete(id: number): boolean {
    return this.db.prepare('DELETE FROM devices WHERE id = ?').run(id).changes > 0;
  }
}
