import asyncio
import time
import yaml
import struct
import threading
import math
import requests
import json
from bleak import BleakClient, BleakScanner
from rpi_ws281x import PixelStrip, Color
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv, find_dotenv
import os
from ruamel.yaml import YAML

# Define global variables and constants
debug = False
fakeinput = False

# Load environment variables from .env file if it exists
load_dotenv(find_dotenv())

class Power2Color:
    def __init__(self, config_path, LEDControler):
        self.state = "connecting"
        self.states = {
            "connecting",
            "idle",
            "new_zone",
            "in_zone"
        }
        # Read Configuration via config.yaml.
        self.config_path = config_path
        self.config = self.read_config()

        # Set Lighting mode parameters:
        self.use_zones_from_intervals_icu = self.config['use_zones_from_intervals_icu']
        mode_params = self.config['mode_params']
        self.idle_color = Color(*mode_params['idle_color'])
        self.initial_brightness_value = mode_params['initial_brightness_value']
        self.initial_brightness_duration = mode_params['initial_brightness_duration']
        
        # Initialize Power Management
        self.instantaneous_power = 0
        self.fake_power = 0
        self.current_zone = "Unknown Zone"
        
         # Bluetooth related 
        self.client = None
        
        self.prev_zone = "Unknown Zone"
        self.zones = []
        self.init_zones()
        
        # LED Controller
        self.led_control = LEDControler

    def init_zones(self):
        # Initialize the zones based on the configuration
        
        #try to load zone values from intervals.icu
        if not self.use_zones_from_intervals_icu:
            print("Loading intervals defined in config.yaml")
            colors = self.config['power_zones_colors']
            for i,zone in enumerate(self.config['power_zones']):
                color = Color(*colors[i % len(colors)])
                self.zones.append((zone['name'],zone['min_watt'], zone['max_watt'], color))
                
        else:
            print("Loading intervals from intervals.icu")
            self.load_intervals_from_intervals_icu()    
        
        # Output used Intervals
        print("-- success! intervals:")
        for i,zone in enumerate(self.zones):
            color = zone[3]
            print(f"Zone {i+1} '{zone[0]}': {zone[1]}W - {zone[2]}W color : {color.r} {color.g} {color.b}" )

    def load_intervals_from_intervals_icu(self):
        if os.getenv('ATHLETE_ID') is None:
            athlet_id=self.self.config['athlete']['athlete_id'] 
        else:
            athlete_id = os.getenv('ATHLETE_ID')

        if os.getenv('API_KEY') is None:
            api_key = self.config['athlete']['api_key']
        else:
            api_key = os.getenv('API_KEY')
        
        #print(f"Loading intervals from intervals.icu for athlete ID {athlete_id}...")

        ftp_type = self.config['athlete'].get('ftp_type', 'ftp')  # Default to 'ftp' if not specified

        # Intervals.icu API URL
        url = f"https://intervals.icu/api/v1/athlete/{athlete_id}"

        # Make the API request with basic authentication
        response = requests.get(url, auth=HTTPBasicAuth('API_KEY', api_key), headers={'accept': '*/*'})

        # Check if the request was successful
        if response.status_code == 200:
            # Get the response data
            data = response.json()
            
            # Find the relevant section in sportSettings where type contains "Ride"
            sport_settings = data.get('sportSettings', [])
            #print('found sport settings') 
            #print(sport_settings)
            ride_settings = next((setting for setting in sport_settings if 'Ride' in setting.get('types', '')), None)
            
            if ride_settings:
                # Extract FTP or indoor FTP based on configuration
                ftp = ride_settings.get(ftp_type)
                power_zones_percentages = ride_settings.get('power_zones', [])
                power_zone_names = ride_settings.get('power_zone_names', [])
                
                if ftp and power_zones_percentages and power_zone_names:
                    # Calculate the power zones based on FTP and percentages
                    power_zones = []

                    # Add the first zone starting from 0
                    min_watt = 0
                    max_watt = ftp * power_zones_percentages[0] / 100
                    zone_name = power_zone_names[0]
                    power_zones.append({
                        'zone_number': 1,
                        'min_watt': min_watt,
                        'max_watt': max_watt,
                        'name': zone_name
                    })

                    # Add the remaining zones
                    for i in range(1, len(power_zones_percentages)):
                        min_watt = ftp * power_zones_percentages[i - 1] / 100
                        max_watt = ftp * power_zones_percentages[i] / 100
                        zone_name = power_zone_names[i]
                        power_zones.append({
                            'zone_number': i + 1,
                            'min_watt': min_watt,
                            'max_watt': max_watt,
                            'name': zone_name
                        })

                    # Print the calculated power zone
                    colors = self.config['power_zones_colors']
                    for i,zone in enumerate(power_zones):
                        #print(f"Zone {zone['zone_number']} '{zone['name']}': {zone['min_watt']}W - {zone['max_watt']}W")
                        self.zones.append((zone['name'],zone['min_watt'], zone['max_watt'], Color(*colors[i % len(colors)])))
                    
                else:
                    print("Failed to retrieve FTP, power zones percentages, or power zone names from the Ride settings.")
                    return False
            else:
                print("No Ride settings found in sportSettings.")
                return False
        else:
            print(f"Failed to retrieve data: {response.status_code} - {response.text}")   
            return False


    
    def read_config(self):
        yaml = YAML()
        with open(self.config_path, 'r') as file:
            return yaml.load(file)

    def update_config(self, address):
        yaml = YAML()
        with open(self.config_path, 'r') as file:
            config = yaml.load(file)
        config['bluetooth']['address'] = address
        with open(self.config_path, 'w') as file:
            yaml.dump(config, file)

    async def fakeinput(self):
        ramp_time = 2  # seconds for ramp up and down
        max_power = 350
        while True:
            # Ramp up from 0 to max_power
            for t in range(ramp_time * 10):  # 10 samples per second
                self.fake_power = int((max_power / (ramp_time * 10)) * t)
                await asyncio.sleep(0.1)  # 10 samples per second

            # Ramp down from max_power to 0
            for t in range(ramp_time * 10):  # 10 samples per second
                self.fake_power = int(max_power - (max_power / (ramp_time * 10)) * t)
                await asyncio.sleep(0.1)  # 10 samples per second

            # Stay at 0 for ramp_time seconds
            for _ in range(ramp_time * 10):  # 10 samples per second
                self.fake_power = 0
                await asyncio.sleep(0.1)  # 10 samples per second

    async def scan_devices(self):
        print("Scanning for Bluetooth devices...")
        devices = await BleakScanner.discover()
        for i, device in enumerate(devices):
            print(f"{i}: {device.name} ({device.address})")
        return devices

    async def connect(self):
        address = self.config['bluetooth']['address']
        characteristic_uuid = self.config['bluetooth']['uuid']

        if not address:
            print("Bluetooth address is missing.")
            devices = await self.scan_devices()
            if devices:
                device_index = int(input("Please select a device by index: "))
                address = devices[device_index].address
                self.update_config(address)
            else:
                print("No Bluetooth devices found. Please try again.")
                return

        self.client = BleakClient(address)
        print(f"Connecting to {address}")
        await self.client.connect()
        print(f"Connected to {address}")
        await self.client.start_notify(characteristic_uuid, self.notification_handler)
        #self.set_state("idle")

    async def notification_handler(self, sender, data):
      
        # Unpack the first 4 bytes: Flags (2 bytes) and Instantaneous Power (2 bytes)
        flags, instantaneous_power = struct.unpack('<HH', data[:4])
        self.instantaneous_power = instantaneous_power


    def set_state(self, new_state):
        self.state = new_state
        print(f"State changed to: {self.state}")
    
    def determine_zone_color(self):
        """Determine the color based on the instantaneous power and zones."""
        power = self.get_power()
        for zone_name, min_watt, max_watt, color in self.zones:
            if min_watt <= power <= (float('inf') if max_watt == '.inf' else max_watt):
                self.zone = zone_name
                #print(f"Determined Current Zone: {self.zone} for power: {power}, so clolor is:  {color.r} {color.g} {color.b}")
                return color
        self.zone = "Unknown Zone"
        return self.idle_color
    
    def get_power(self):
        if fakeinput:
            return self.fake_power
        else:
            return self.instantaneous_power

    async def run(self):
        try:
            #Default entry State "CONNECTING"
            self.led_control.set_lightmode("pulse", Color(0,0,255))

            if not fakeinput: await self.connect()
            self.set_state("idle")
        
            while True:
                if debug: print(f"Power: {self.get_power()} hence zone: {self.state}")
                
                if self.state == "idle": 
                    if self.get_power() > 0:
                        self.set_state("in_zone")
                    self.led_control.set_lightmode("running", Color(255,255,255))
                
                elif self.state == "in_zone":
                    
                    if self.get_power() == 0:
                         self.set_state("idle")
                    
                    self.led_control.set_lightmode("pulse", self.determine_zone_color())
                   
                #only update the state machine every second.
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            print("Run loop cancelled.")
        finally:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
            print("Disconnected from Bluetooth device.")

class LEDControl:
    def __init__(self, config_path):
        # Configuration via config.yaml.
        self.config_path = config_path
        self.config = self.read_config()
        led_config = self.config['led_strip']
        self.strip = PixelStrip(
            led_config['count'],
            led_config['pin'],
            led_config['freq_hz'],
            led_config['dma'],
            led_config['invert'],
            led_config['brightness'],
            led_config['channel']
        )
        self.mode = "running"
        self.color = Color(255, 255, 255)
        self.brightness = 0.5
        self.pulesup = True
        self.strip.begin()

    def read_config(self):
        with open(self.config_path, 'r') as file:
            return yaml.safe_load(file)

    def show_running_Light(self, length=40):
        if debug: print("running light")
        """Create a running light effect with a pulse of specified length and linear brightness fade."""
        strip = self.strip
        num_pixels = strip.numPixels()
        color = self.color

        for i in range(num_pixels):
            # Turn off the trailing LED
            strip.setPixelColor((i - length) % num_pixels, Color(0, 0, 0))
            for j in range(length):
                index = (i - j) % num_pixels
                if j < length // 4:
                    # Full brightness for the first 25% of the pulse
                    fade_factor=  1.0
                else:
                    # Linear fade for the remaining 75% of the pulse
                    fade_factor = 1.0 - ((j - length // 4) / (length * 0.75))         
                #apply fade factor to all rgb values:
                r = int(((color >> 16) & 0xFF) * fade_factor)
                g = int(((color >> 8) & 0xFF) * fade_factor)
                b = int((color & 0xFF) * fade_factor)
                strip.setPixelColor(index, Color(r, g, b))
            strip.show()

    
    def show_pulseing_Light(self, wait_ms,  min_brightness=0.4, max_brightness=1.0, step=0.005):
        #if debug: print("pulse light")
        """Pulse the entire LED strip between min_brightness and max_brightness."""
        #if debug: print("bightness:", self.brightness)

        # Pulse up
        if self.pulesup:
            self.brightness += step
            if self.brightness >= max_brightness:
                self.pulesup = False
        else:
            self.brightness -= step
            if self.brightness <= min_brightness:
                self.pulesup = True
       
        #update all leds with the new value
        for i in range(self.strip.numPixels()):
            r = int(((self.color >> 16) & 0xFF) * self.brightness)
            g = int(((self.color >> 8) & 0xFF) * self.brightness)
            b = int((self.color & 0xFF) * self.brightness)
            self.strip.setPixelColor(i, Color(r, g, b))
        self.strip.show()

    
    def set_lightmode(self, target_mode, color):
        self.mode = target_mode
        self.color = color

    def set_color(self, color=Color(255, 255, 0)):
        self.color = color

    async def run(self, wait_ms=10):
        while True:
            if self.mode == "running":
                self.show_running_Light()
            elif self.mode == "pulse":
                self.show_pulseing_Light(wait_ms)
            await asyncio.sleep(wait_ms / 1000.0)


async def main():
    config_path = 'config.yaml'
    led_control = LEDControl(config_path)
    power2color = Power2Color(config_path, led_control)
    
    await asyncio.gather(
        power2color.run(),
        led_control.run(),
        power2color.fakeinput()
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user.")