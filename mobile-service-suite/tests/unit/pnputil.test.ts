import { describe, it, expect } from 'vitest';
import { parsePnpUtilDrivers, matchDriver } from '@backend/services/drivers/pnputil';

const SAMPLE = `Microsoft PnP Utility

Published Name:     oem12.inf
Original Name:      android_winusb.inf
Provider Name:      Google, Inc.
Class Name:         Android Device
Driver Version:     08/28/2014 11.0.0.0

Published Name:     oem34.inf
Original Name:      ssudbus.inf
Provider Name:      SAMSUNG Electronics Co., Ltd.
Class Name:         Ports
Driver Version:     05/10/2021 2.14.7.0
`;

describe('pnputil parser', () => {
  it('parses driver entries', () => {
    const entries = parsePnpUtilDrivers(SAMPLE);
    expect(entries).toHaveLength(2);
    expect(entries[0]?.provider).toBe('Google, Inc.');
    expect(entries[1]?.originalName).toBe('ssudbus.inf');
    expect(entries[1]?.version).toBe('05/10/2021 2.14.7.0');
  });

  it('matches a driver by needle and returns its version', () => {
    const entries = parsePnpUtilDrivers(SAMPLE);
    expect(matchDriver(entries, ['SAMSUNG', 'ssudbus'])).toBe('05/10/2021 2.14.7.0');
    expect(matchDriver(entries, ['Google, Inc.'])).toBe('08/28/2014 11.0.0.0');
    expect(matchDriver(entries, ['Qualcomm'])).toBeNull();
  });
});
