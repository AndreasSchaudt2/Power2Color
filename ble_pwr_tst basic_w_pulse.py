import asyncio
import yaml
from bleak import BleakScanner, BleakClient
import struct
from rpi_ws281x import PixelStrip, Color
import time

# Load configuration from YAML file
with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

# Extract Bluetooth configuration
bluetooth_address = config['bluetooth']['address']
power_meter_characteristic_uuid = config['bluetooth']['uuid']

# Extract power zones configuration
POWER_ZONES = [
    (zone['min_watt'], zone['max_watt'], zone['name'], Color(*zone['color']))
    for zone in config['power_zones']
]

# Extract LED strip configuration
led_config = config['led_strip']
LED_COUNT = led_config['count']
LED_PIN = led_config['pin']
LED_FREQ_HZ = led_config['freq_hz']
LED_DMA = led_config['dma']
LED_BRIGHTNESS = led_config['brightness']
LED_INVERT = led_config['invert']
LED_CHANNEL = led_config['channel']

# Debug flag
debug = False
output_sequential = False

# Initialize LED strip
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

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
def interpret_power_data(data):
    """
    Unpack the first 4 bytes: Flags (2 bytes) and Instantaneous Power (2 bytes)
    """
    flags, instantaneous_power = struct.unpack('<HH', data[:4])
    
    # Map the instantaneous power to the corresponding zone
    zone, color = next(((zone_name, color) for min_watt, max_watt, zone_name, color in POWER_ZONES if min_watt <= instantaneous_power <= max_watt), ("Unknown Zone", Color(0, 0, 0)))
    
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
    
    # Update the LED strip based on the power zone
    update_led_strip_pulse(color)

# Function to update the LED strip with a pulsing effect
def update_led_strip_pulse(color, pulse_duration=2, steps=20, min_brightness=0.3):
    for step in range(steps):
        brightness = int(LED_BRIGHTNESS * (min_brightness + (1 - min_brightness) * step / steps))
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(
                (color >> 16 & 0xFF) * brightness // 255,
                (color >> 8 & 0xFF) * brightness // 255,
                (color & 0xFF) * brightness // 255
            ))
        strip.show()
        time.sleep(pulse_duration / (2 * steps))
    
    for step in range(steps, 0, -1):
        brightness = int(LED_BRIGHTNESS * (min_brightness + (1 - min_brightness) * step / steps))
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(
                (color >> 16 & 0xFF) * brightness // 255,
                (color >> 8 & 0xFF) * brightness // 255,
                (color & 0xFF) * brightness // 255
            ))
        strip.show()
        time.sleep(pulse_duration / (2 * steps))

# Callback function to handle notifications
def notification_handler(sender, data):
    if debug:
        print(f"Received data from {sender}: {data}")
    interpret_power_data(data)

# Function to connect to a BLE device and receive notifications
async def read_power_meter(address):
    async with BleakClient(address) as client:
        # Start receiving notifications
        await client.start_notify(power_meter_characteristic_uuid, notification_handler)
        
        # Keep the connection open to receive notifications
        await asyncio.sleep(300)
        
        # Stop receiving notifications
        await client.stop_notify(power_meter_characteristic_uuid)

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
    
    print(f"Connecting to power meter at {bluetooth_address}...")
    await read_power_meter(bluetooth_address)

# Run the main function
asyncio.run(main())