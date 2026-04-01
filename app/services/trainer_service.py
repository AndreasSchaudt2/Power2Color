from __future__ import annotations

import asyncio
import os
import struct
import time

import requests
from bleak import BleakClient, BleakScanner
from requests.auth import HTTPBasicAuth
from rpi_ws281x import Color


class TrainerService:
    def __init__(self, app_config, runtime_state, debug: bool = False, fake_input: bool = False):
        self.app_config = app_config
        self.runtime_state = runtime_state
        self.debug = debug
        self.fake_input = fake_input
        self.client = None
        self.fake_power = 0
        self.zones = []
        self.load_zones()

    @property
    def connected(self) -> bool:
        return self.runtime_state.trainer.connected or self.fake_input

    def load_zones(self):
        self.zones = []
        if self.app_config.use_zones_from_intervals_icu:
            print("Loading intervals from intervals.icu")
            loaded = self._load_intervals_from_intervals_icu()
            if not loaded:
                print("Falling back to local intervals defined in config.yaml")
                self._load_local_zones()
                self.runtime_state.zone_source = "local"
            else:
                self.runtime_state.zone_source = "intervals"
        else:
            print("Loading intervals defined in config.yaml")
            self._load_local_zones()
            self.runtime_state.zone_source = "local"

        self.runtime_state.zones = self.zones
        print("-- success! intervals:")
        for index, zone in enumerate(self.zones):
            color = zone[3]
            print(
                f"Zone {index + 1} '{zone[0]}': {zone[1]}W - {zone[2]}W color : "
                f"{color.r} {color.g} {color.b}"
            )

    def _load_local_zones(self):
        colors = self.app_config.power_zone_colors
        for index, zone in enumerate(self.app_config.power_zones):
            color = Color(*colors[index % len(colors)])
            self.zones.append((zone["name"], zone["min_watt"], zone["max_watt"], color))

    def _load_intervals_from_intervals_icu(self) -> bool:
        athlete_id = os.getenv("ATHLETE_ID") or self.app_config.athlete.get("athlete_id") or self.app_config.athlete.get("id")
        api_key = os.getenv("API_KEY") or self.app_config.athlete.get("api_key")

        if not athlete_id or not api_key:
            print("Intervals.icu credentials are incomplete.")
            return False

        ftp_type = self.app_config.athlete.get("ftp_type", "ftp")
        url = f"https://intervals.icu/api/v1/athlete/{athlete_id}"
        response = requests.get(
            url,
            auth=HTTPBasicAuth("API_KEY", api_key),
            headers={"accept": "*/*"},
            timeout=10,
        )

        if response.status_code != 200:
            print(f"Failed to retrieve data: {response.status_code} - {response.text}")
            return False

        data = response.json()
        ride_settings = next(
            (setting for setting in data.get("sportSettings", []) if "Ride" in setting.get("types", "")),
            None,
        )
        if not ride_settings:
            print("No Ride settings found in sportSettings.")
            return False

        ftp = ride_settings.get(ftp_type)
        power_zone_percentages = ride_settings.get("power_zones", [])
        power_zone_names = ride_settings.get("power_zone_names", [])
        if not ftp or not power_zone_percentages or not power_zone_names:
            print("Failed to retrieve FTP, power zones percentages, or power zone names from the Ride settings.")
            return False

        power_zones = []
        min_watt = 0
        max_watt = ftp * power_zone_percentages[0] / 100
        power_zones.append({
            "zone_number": 1,
            "min_watt": min_watt,
            "max_watt": max_watt,
            "name": power_zone_names[0],
        })

        for index in range(1, len(power_zone_percentages)):
            min_watt = ftp * power_zone_percentages[index - 1] / 100
            max_watt = ftp * power_zone_percentages[index] / 100
            power_zones.append({
                "zone_number": index + 1,
                "min_watt": min_watt,
                "max_watt": max_watt,
                "name": power_zone_names[index],
            })

        colors = self.app_config.power_zone_colors
        for index, zone in enumerate(power_zones):
            self.zones.append((zone["name"], zone["min_watt"], zone["max_watt"], Color(*colors[index % len(colors)])))
        return True

    async def create_fake_input(self):
        ramp_time = 10
        max_power = 300
        while True:
            for tick in range(ramp_time * 10):
                self.fake_power = int((max_power / (ramp_time * 10)) * tick)
                self._set_power(self.fake_power)
                await asyncio.sleep(0.1)

            for tick in range(ramp_time * 10):
                self.fake_power = int(max_power - (max_power / (ramp_time * 10)) * tick)
                self._set_power(self.fake_power)
                await asyncio.sleep(0.1)

            for _ in range(ramp_time * 10):
                self.fake_power = 0
                self._set_power(0)
                await asyncio.sleep(0.1)

    async def scan_devices(self):
        print("Scanning for Bluetooth devices...")
        devices = await BleakScanner.discover()
        for index, device in enumerate(devices):
            print(f"{index}: {device.name} ({device.address})")
        return devices

    async def connect(self):
        address = self.app_config.bluetooth["address"]
        characteristic_uuid = self.app_config.bluetooth["uuid"]

        if not address:
            print("Bluetooth address is missing.")
            devices = await self.scan_devices()
            if not devices:
                print("No Bluetooth devices found. Please try again.")
                return False
            device_index = int(input("Please select a device by index: "))
            address = devices[device_index].address
            self.app_config.update_bluetooth_address(address)

        self.runtime_state.trainer.status = "connecting"
        self.client = BleakClient(address)
        print(f"Connecting to {address}")
        await self.client.connect()
        print(f"Connected to {address}")
        await self.client.start_notify(characteristic_uuid, self.notification_handler)
        self.runtime_state.trainer.connected = True
        self.runtime_state.trainer.status = "connected"
        return True

    async def notification_handler(self, sender, data):
        _, instantaneous_power = struct.unpack("<HH", data[:4])
        self._set_power(instantaneous_power)

    def _set_power(self, value: int):
        self.runtime_state.trainer.latest_power_watts = value
        self.runtime_state.trainer.last_power_timestamp = time.monotonic()

    def get_power(self):
        return self.runtime_state.trainer.latest_power_watts

    def determine_zone_color(self):
        power = self.get_power()
        for zone_name, min_watt, max_watt, color in self.zones:
            upper_limit = float("inf") if max_watt == ".inf" else max_watt
            if min_watt <= power <= upper_limit:
                return color
        return Color(*self.app_config.mode_params["idle_color"])

    async def start(self):
        if self.fake_input:
            self.runtime_state.trainer.connected = True
            self.runtime_state.trainer.status = "connected"
            return
        await self.connect()

    async def run(self):
        if self.fake_input:
            self.runtime_state.trainer.connected = True
            self.runtime_state.trainer.status = "connected"
            return

        retry_delays = self.app_config.trainer_settings.get("reconnect_backoff_seconds", [2, 5, 10, 20, 30])
        stale_after = self.app_config.trainer_settings.get("stale_after_seconds", 4)
        attempt = 0

        while True:
            try:
                await self.connect()
                attempt = 0
                while self.client and self.client.is_connected:
                    last_power_timestamp = self.runtime_state.trainer.last_power_timestamp
                    if last_power_timestamp and (time.monotonic() - last_power_timestamp) > stale_after:
                        self.runtime_state.trainer.connected = False
                        self.runtime_state.trainer.status = "stale"
                        await self.client.disconnect()
                        break
                    await asyncio.sleep(1)

                self.runtime_state.trainer.connected = False
                if self.runtime_state.trainer.status != "stale":
                    self.runtime_state.trainer.status = "disconnected"
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.runtime_state.trainer.connected = False
                self.runtime_state.trainer.status = "disconnected"
                print(f"Trainer connection failed: {error}")

            delay = retry_delays[min(attempt, len(retry_delays) - 1)] if retry_delays else 5
            attempt += 1
            await asyncio.sleep(delay)

    async def stop(self):
        self.runtime_state.trainer.connected = False
        self.runtime_state.trainer.status = "disconnected"
        if self.client and self.client.is_connected:
            print("Disconnecting Blauzahn")
            await self.client.disconnect()
            print("Disconnected from Bluetooth device.")
