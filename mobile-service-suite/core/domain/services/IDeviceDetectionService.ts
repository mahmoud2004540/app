import type { Device } from '../entities/Device';
import type { Result } from '@shared/types/result';

/**
 * Service-layer contract for device detection (Service Layer pattern).
 *
 * Implemented in PHASE 5 against ADB/Fastboot. Declared here so the UI and other
 * services can be built and tested against the abstraction.
 */
export interface IDeviceDetectionService {
  /** Enumerate all currently connected devices across USB / ADB / Fastboot. */
  listConnectedDevices(): Promise<Result<Device[]>>;

  /** Read detailed information for a single device by id. */
  getDeviceInfo(deviceId: string): Promise<Result<Device>>;
}
