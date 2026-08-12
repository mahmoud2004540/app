import type {
  DetectedDevice,
  DetectionResult,
  TriBool,
} from '@shared/types/device';
import type { IDeviceDetectionService } from '@core/domain/services/IDeviceDetectionService';
import { AdbClient } from '../adb/AdbClient';
import { FastbootClient } from '../fastboot/FastbootClient';
import type { CommandRunner } from '../process/CommandRunner';
import { NodeCommandRunner } from '../process/CommandRunner';

function boolProp(value: string | undefined, whenTrue: string): TriBool {
  if (value === undefined) return 'unknown';
  return value === whenTrue ? 'yes' : 'no';
}

/**
 * Detects connected devices via ADB and Fastboot and enriches ADB devices with
 * properties, battery and RAM. Protection-related fields are DIAGNOSED only.
 */
export class DeviceDetectionService implements IDeviceDetectionService {
  private readonly adb: AdbClient;
  private readonly fastboot: FastbootClient;

  constructor(runner: CommandRunner = new NodeCommandRunner()) {
    this.adb = new AdbClient(runner);
    this.fastboot = new FastbootClient(runner);
  }

  async detect(): Promise<DetectionResult> {
    const [adbAvailable, fastbootAvailable] = await Promise.all([
      this.adb.isAvailable(),
      this.fastboot.isAvailable(),
    ]);

    const devices: DetectedDevice[] = [];
    if (adbAvailable) devices.push(...(await this.detectAdbDevices()));
    if (fastbootAvailable) devices.push(...(await this.detectFastbootDevices()));

    return { adbAvailable, fastbootAvailable, devices };
  }

  private async detectAdbDevices(): Promise<DetectedDevice[]> {
    const lines = await this.adb.listDevices();
    return Promise.all(
      lines.map(async ({ id, state }) => {
        if (state !== 'device') {
          // Unauthorized / offline: report presence without probing.
          return { id, transport: 'adb', state } satisfies DetectedDevice;
        }
        const [props, battery, ramKb] = await Promise.all([
          this.adb.getProps(id),
          this.adb.getBatteryLevel(id),
          this.adb.getTotalRamKb(id),
        ]);
        return this.buildAdbDevice(id, state, props, battery, ramKb);
      }),
    );
  }

  private buildAdbDevice(
    id: string,
    state: string,
    props: Record<string, string>,
    battery: number | undefined,
    ramKb: number | undefined,
  ): DetectedDevice {
    const device: DetectedDevice = {
      id,
      transport: 'adb',
      state,
      bootloaderUnlocked: boolProp(props['ro.boot.flash.locked'], '0'),
      oemUnlockAllowed: boolProp(props['sys.oem_unlock_allowed'], '1'),
      frpState: 'unknown',
    };

    const bag = device as unknown as Record<string, unknown>;
    const assign = (key: keyof DetectedDevice, value: string | undefined): void => {
      if (value !== undefined && value !== '') {
        bag[key] = value;
      }
    };
    assign('brand', props['ro.product.brand']);
    assign('manufacturer', props['ro.product.manufacturer']);
    assign('model', props['ro.product.model']);
    assign('androidVersion', props['ro.build.version.release']);
    assign('sdk', props['ro.build.version.sdk']);
    assign('buildNumber', props['ro.build.display.id']);
    assign('serialNumber', props['ro.serialno']);
    assign('chipset', props['ro.board.platform'] ?? props['ro.hardware']);
    assign('cpuAbi', props['ro.product.cpu.abi']);
    if (battery !== undefined) device.batteryPercent = battery;
    if (ramKb !== undefined) device.totalRamKb = ramKb;
    return device;
  }

  private async detectFastbootDevices(): Promise<DetectedDevice[]> {
    const ids = await this.fastboot.listDevices();
    return Promise.all(
      ids.map(async (id) => {
        const [unlocked, product] = await Promise.all([
          this.fastboot.getVar(id, 'unlocked'),
          this.fastboot.getVar(id, 'product'),
        ]);
        const device: DetectedDevice = {
          id,
          transport: 'fastboot',
          state: 'fastboot',
          bootloaderUnlocked: unlocked === undefined ? 'unknown' : unlocked === 'yes' ? 'yes' : 'no',
          frpState: 'unknown',
        };
        if (product) device.model = product;
        return device;
      }),
    );
  }
}
