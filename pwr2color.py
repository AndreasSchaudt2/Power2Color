import asyncio
import yaml
from bleak import BleakScanner, BleakClient
import struct
from rpi_ws281x import PixelStrip, Color
import time
import signal
import sys
import threading
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Access the Intervals.icu API key
intervals_icu_api_key = os.getenv('INTERVALS_ICU_API_KEY')

# Ensure the API key is loaded
if not intervals_icu_api_key:
   raise ValueError("Athlete ID or Intervals.icu API key not found. Please set them in the .env file.")

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
MAX_BRIGHTNESS = min(led_config['max_brightness'], 255)  # Cap to absolute max
INITIAL_BRIGHTNESS_DURATION = led_config['initial_brightness_duration']
INITIAL_BRIGHTNESS_VALUE = min(led_config['initial_brightness_value'], MAX_BRIGHTNESS)  # Cap to max_brightness

# Debug flag
debug = False  # Set to True to enable debug mode
output_sequential = False

# Initialize LED strip
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# Track the current power zone
current_zone = None

# Global variable to control the pulsing thread
pulsing_thread = None
stop_pulsing = threading.Event()

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
    global current_zone, pulsing_thread, stop_pulsing
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
    
    # Check if the zone has changed
    if zone != current_zone:
        current_zone = zone
        # Stop the current pulsing thread if it exists
        if pulsing_thread and pulsing_thread.is_alive():
            stop_pulsing.set()
            pulsing_thread.join()
        
        # Set LEDs to initial brightness for the configured duration
        update_led_strip_brightness(color, INITIAL_BRIGHTNESS_VALUE)
        time.sleep(INITIAL_BRIGHTNESS_DURATION)
        
        # Start a new pulsing thread
        stop_pulsing.clear()
        pulsing_thread = threading.Thread(target=pulse_continuously, args=(color, INITIAL_BRIGHTNESS_VALUE))
        pulsing_thread.start()

def pulse_continuously(color, initial_brightness):
    while not stop_pulsing.is_set():
        update_led_strip_pulse(color, initial_brightness=initial_brightness)

# Function to update the LED strip with a specific brightness
def update_led_strip_brightness(color, brightness):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(
            (color >> 16 & 0xFF) * brightness // 255,
            (color >> 8 & 0xFF) * brightness // 255,
            (color & 0xFF) * brightness // 255
        ))
    strip.show()

# Function to update the LED strip with a pulsing effect
def update_led_strip_pulse(color, pulse_duration=2, steps=100, min_brightness=0.3, initial_brightness=None):
    if initial_brightness is None:
        initial_brightness = LED_BRIGHTNESS

    for step in range(steps):
        brightness = int(initial_brightness * (min_brightness + (1 - min_brightness) * step / steps))
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(
                (color >> 16 & 0xFF) * brightness // 255,
                (color >> 8 & 0xFF) * brightness // 255,
                (color & 0xFF) * brightness // 255
            ))
        strip.show()
        time.sleep(pulse_duration / (2 * steps))
    
    for step in range(steps, 0, -1):
        brightness = int(initial_brightness * (min_brightness + (1 - min_brightness) * step / steps))
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(
                (color >> 16 & 0xFF) * brightness // 255,
                (color >> 8 & 0xFF) * brightness // 255,
                (color & 0xFF) * brightness // 255
            ))
        strip.show()
        time.sleep(pulse_duration / (2 * steps))

# Mock function to simulate power data
def mock_power_data():
    test_data = [
        (0, 100),  # Zone 1
        (0, 150),  # Zone 2
        (0, 200),  # Zone 3
        (0, 230),  # Zone 4
        (0, 300)   # Zone 5
    ]
    for flags, power in test_data:
        data = struct.pack('<HH', flags, power)
        interpret_power_data(data)
        time.sleep(5)  # Wait 5 seconds before sending the next power data

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
        await asyncio.sleep(300000)
        
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

# Cleanup function to be called on termination
def cleanup():
    print("Cleaning up...")
    stop_pulsing.set()
    if pulsing_thread and pulsing_thread.is_alive():
        pulsing_thread.join()
    strip.setBrightness(0)
    strip.show()
    sys.exit(0)

# Signal handler for graceful termination
def signal_handler(sig, frame):
    cleanup()

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Main function
async def main():
    if debug:
        print("Debug mode enabled. Using mock power data.")
        mock_power_data()
    else:
        print("Scanning for BLE devices...")
        await scan_for_devices()
        
        print(f"Connecting to power meter at {bluetooth_address}...")
        await read_power_meter(bluetooth_address)

# Run the main function
asyncio.run(main())