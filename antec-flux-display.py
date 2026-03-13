#!/usr/bin/env python3
"""
Antec Flux Pro Display Service
Sends CPU and GPU temperatures to the case front panel display.

Protocol reverse-engineered from Antec iUnity Windows software.
Reference: https://nishtahir.com/building-an-ubuntu-service-for-my-antec-flux-display/

Uses pyusb (libusb) to write directly to the interrupt OUT endpoint,
since the device doesn't enumerate as a standard HID device on Linux.

Hardware: AMD Ryzen 9900X (k10temp) + AMD 7900 XTX (amdgpu)
"""

import glob
import time
import sys
import signal

import usb.core
import usb.util

VENDOR_ID = 0x2022
PRODUCT_ID = 0x0522
ENDPOINT_OUT = 0x03
UPDATE_INTERVAL = 1.0  # seconds


def find_hwmon_path(device_name: str) -> str | None:
    """Find the hwmon sysfs path for a given device."""
    for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            with open(f"{hwmon}/name") as f:
                if f.read().strip() == device_name:
                    return hwmon
        except (IOError, OSError):
            continue
    return None


def read_temp(hwmon_path: str, input_file: str = "temp1_input") -> float:
    """Read temperature from hwmon sysfs (returns °C)."""
    try:
        with open(f"{hwmon_path}/{input_file}") as f:
            return int(f.read().strip()) / 1000.0
    except (IOError, OSError, ValueError):
        return 0.0


def encode_temperature(temp: float) -> list[int]:
    """Encode a temperature as 3 bytes: [tens, ones, tenths].

    If temp is 0 or unavailable, returns [0xEE, 0xEE, 0xEE] (display shows --.-).
    """
    if temp <= 0.0:
        return [0xEE, 0xEE, 0xEE]

    # Clamp to 99.9
    temp = min(temp, 99.9)
    formatted = f"{temp:04.1f}"  # e.g. "52.3" -> "52.3", "8.1" -> "08.1"

    tens = int(formatted[0])
    ones = int(formatted[1])
    tenths = int(formatted[3])

    return [tens, ones, tenths]


def build_packet(cpu_temp: float, gpu_temp: float) -> bytes:
    """Build the 12-byte USB packet for the display.

    Packet format:
      [0x55, 0xAA, 0x01, 0x01, 0x06,
       cpu_tens, cpu_ones, cpu_tenths,
       gpu_tens, gpu_ones, gpu_tenths,
       checksum]
    """
    payload = [0x55, 0xAA, 0x01, 0x01, 0x06]
    payload.extend(encode_temperature(cpu_temp))
    payload.extend(encode_temperature(gpu_temp))

    checksum = sum(payload) % 256
    payload.append(checksum)

    return bytes(payload)


def open_display():
    """Open the Antec Flux Pro USB device and return (device, endpoint)."""
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        return None

    # Detach kernel driver if attached
    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError):
        pass

    # Set configuration and claim interface
    try:
        dev.set_configuration()
    except usb.core.USBError:
        pass  # May already be configured

    usb.util.claim_interface(dev, 0)
    return dev


def main():
    # Find sensor paths
    cpu_hwmon = find_hwmon_path("k10temp")
    if not cpu_hwmon:
        print("ERROR: k10temp hwmon not found. Is the k10temp module loaded?", file=sys.stderr)
        sys.exit(1)

    gpu_hwmon = find_hwmon_path("amdgpu")
    if not gpu_hwmon:
        print("WARNING: amdgpu hwmon not found. GPU temp will show --.-", file=sys.stderr)

    print(f"CPU sensor: {cpu_hwmon}")
    print(f"GPU sensor: {gpu_hwmon or 'not found'}")

    # k10temp: temp1_input = Tctl
    cpu_temp_file = "temp1_input"
    # amdgpu: temp1_input = edge
    gpu_temp_file = "temp1_input"

    # Open display
    dev = open_display()
    if dev is None:
        print("ERROR: Could not find display device 2022:0522", file=sys.stderr)
        print("Is the display USB header connected?", file=sys.stderr)
        sys.exit(1)

    print(f"Display connected: {VENDOR_ID:04x}:{PRODUCT_ID:04x}")

    # Graceful shutdown
    running = True

    def shutdown(signum, frame):
        nonlocal running
        print(f"\nReceived signal {signum}, shutting down...")
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Main loop
    print(f"Sending temps every {UPDATE_INTERVAL}s. Press Ctrl+C to stop.")
    try:
        while running:
            cpu_temp = read_temp(cpu_hwmon, cpu_temp_file)
            gpu_temp = read_temp(gpu_hwmon, gpu_temp_file) if gpu_hwmon else 0.0

            packet = build_packet(cpu_temp, gpu_temp)

            try:
                dev.write(ENDPOINT_OUT, packet)
            except usb.core.USBError as e:
                print(f"USB write error: {e}", file=sys.stderr)
                # Try to reconnect
                try:
                    usb.util.release_interface(dev, 0)
                except Exception:
                    pass
                dev = open_display()
                if dev is None:
                    print("ERROR: Lost connection to display", file=sys.stderr)
                    break

            time.sleep(UPDATE_INTERVAL)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
    finally:
        try:
            usb.util.release_interface(dev, 0)
            usb.util.dispose_resources(dev)
        except Exception:
            pass
        print("Display service stopped.")


if __name__ == "__main__":
    main()
