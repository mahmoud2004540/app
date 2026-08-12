/**
 * Persisted row shapes for the SQLite tables. These are the storage models; the
 * domain/UI may use richer view-models and map to/from these.
 */
import type { UserRole } from '@shared/constants/app';

export interface UserRow {
  id: number;
  username: string;
  password_hash: string;
  role: UserRole;
  display_name: string;
  created_at: string;
}

export interface DeviceRow {
  id: number;
  serial: string;
  brand: string | null;
  model: string | null;
  imei: string | null;
  android_version: string | null;
  build_number: string | null;
  chipset: string | null;
  first_seen_at: string;
  last_seen_at: string;
}

export interface RepairSessionRow {
  id: number;
  device_id: number | null;
  customer_name: string;
  customer_phone: string | null;
  brand: string | null;
  model: string | null;
  imei: string | null;
  serial: string | null;
  problem: string | null;
  technician: string | null;
  status: 'open' | 'closed';
  created_at: string;
  closed_at: string | null;
}

export interface ToolRow {
  id: number;
  key: string;
  name: string;
  version: string | null;
  path: string | null;
  installed: 0 | 1;
  supported_brands: string | null;
  updated_at: string;
}

export interface DriverRow {
  id: number;
  key: string;
  name: string;
  version: string | null;
  installed: 0 | 1;
  status: string | null;
  updated_at: string;
}

export interface FirmwareRow {
  id: number;
  brand: string | null;
  model: string | null;
  region: string | null;
  android_version: string | null;
  build_number: string | null;
  firmware_version: string | null;
  file_path: string | null;
  sha256: string | null;
  size_bytes: number | null;
  imported_at: string;
}

export interface OperationRow {
  id: number;
  session_id: number | null;
  device_id: number | null;
  category: string;
  command: string | null;
  result: string | null;
  status: LogStatus;
  created_at: string;
}

export type LogStatus = 'SUCCESS' | 'FAILED' | 'WARNING' | 'INFO';

export interface LogRow {
  id: number;
  timestamp: string;
  level: LogStatus;
  user: string | null;
  device: string | null;
  tool: string | null;
  operation: string | null;
  command: string | null;
  result: string | null;
  error: string | null;
}

export interface BackupRow {
  id: number;
  device_id: number | null;
  type: string;
  location: string | null;
  encrypted: 0 | 1;
  size_bytes: number | null;
  created_at: string;
}

export interface ReportRow {
  id: number;
  session_id: number | null;
  file_path: string | null;
  created_at: string;
}

export interface SettingRow {
  key: string;
  value: string;
  updated_at: string;
}
