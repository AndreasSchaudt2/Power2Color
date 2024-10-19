import asyncio
from bleak import BleakScanner, BleakClient
import struct

# Define power zones based on watt values
POWER_ZONES = [
    (0, 100, "Zone 1"),   # 0-100 watts
    (101, 150, "Zone 2"), # 101-150 watts
    (151, 200, "Zone 3"), # 151-200 watts
    (201, 250, "Zone 4"), # 201-250 watts
    (251, 300, "Zone 5"), # 251-300 watts
    (301, float('inf'), "Zone 6") # 301+ watts
]

# Debug flag
debug = False
output_sequential = False

# Function to scan for BLE devices
async def scan_for_devices():
    devices = await BleakScanner.discover()
    if debug:
        for device in devices:
            print(device)

# Function to interpret the received bytearray
"""
Cycling Power Measurement Characteristic Format
The Cycling Power Measurement characteristic typically includes the following fields:

Flags (2 bytes)
Instantaneous Power (2 bytes, signed integer)
Optional Fields (depending on the flags)
"""
# Function to interpret the received bytearray
def interpret_power_data(data):
    """
    Unpack the first 4 bytes: Flags (2 bytes) and Instantaneous Power (2 bytes)
    """
    flags, instantaneous_power = struct.unpack('<HH', data[:4])
    
    # Map the instantaneous power to the corresponding zone
    zone = next((zone_name for min_watt, max_watt, zone_name in POWER_ZONES if min_watt <= instantaneous_power <= max_watt), "Unknown Zone")
    
    if output_sequential:
        if debug:
            print(f"Flags: {flags}, Instantaneous Power: {instantaneous_power} watts, Zone: {zone}")
        else:
            print(f"Zone: {zone}")
    else:
        if debug:
            output = f"Flags: {flags}, Instantaneous Power: {instantaneous_power} watts, Zone: {zone}"
        else:
            output = f"Zone: {zone}"
        # Print the output with carriage return to overwrite the previous line
        print(f"\r{output}", end='', flush=True)

# Callback function to handle notifications
def notification_handler(sender, data):
    if debug:
        print(f"Received data from {sender}: {data}")
    interpret_power_data(data)

# Function to connect to a BLE device and receive notifications
async def read_power_meter(address):
    async with BleakClient(address) as client:
        # Cycling Power Measurement Characteristic UUID
        POWER_METER_CHARACTERISTIC_UUID = "00002a63-0000-1000-8000-00805f9b34fb"
        
        # Start receiving notifications
        await client.start_notify(POWER_METER_CHARACTERISTIC_UUID, notification_handler)
        
        # Keep the connection open to receive notifications
        await asyncio.sleep(300)
        
        # Stop receiving notifications
        await client.stop_notify(POWER_METER_CHARACTERISTIC_UUID)

# Function to discover services and characteristics of a BLE device
async def discover_services(address):
    async with BleakClient(address) as client:
        services = await client.get_services()
        if debug:
            for service in services:
                print(f"Service: {service.uuid}")
                for characteristic in service.characteristics:
                    print(f"  Characteristic: {characteristic.uuid}, Properties: {characteristic.properties}")

# Main function
async def main():
    print("Scanning for BLE devices...")
    await scan_for_devices()
    
    # Replace with the address of your power meter
    power_meter_address = "DF:36:42:3D:BD:A4"

    # Uncomment to discover services and characteristics
    # print(f"Discovering services and characteristics for device at {power_meter_address}...")
    # await discover_services(power_meter_address)

    print(f"Connecting to power meter at {power_meter_address}...")
    await read_power_meter(power_meter_address)

# Run the main function
asyncio.run(main())