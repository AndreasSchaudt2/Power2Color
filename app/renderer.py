from __future__ import annotations

import asyncio
import yaml

from rpi_ws281x import Color, PixelStrip


class LEDControl:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.read_config()
        led_config = dict(self.config["led_strip"])
        hardware_settings = self.config.get("hardware", {})
        if "led_data_gpio" in hardware_settings:
            led_config["pin"] = hardware_settings["led_data_gpio"]
        self.strip = PixelStrip(
            led_config["count"],
            led_config["pin"],
            led_config["freq_hz"],
            led_config["dma"],
            led_config["invert"],
            led_config["brightness"],
            led_config["channel"],
        )
        self.mode = "running"
        self.color = Color(255, 255, 255)
        self.variant = "classic"
        self.brightness = 0.5
        self.pulse_up = True
        self.index = 0
        self.counter = 0
        self.rainbow_offset = 0
        # Load brightness cap from hardware settings
        self.brightness_cap = float(hardware_settings.get("brightness_cap", 1.0))
        self.brightness_cap = max(0.0, min(1.0, self.brightness_cap))
        self.strip.begin()

    def read_config(self):
        with open(self.config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    def _apply_brightness_cap(self, color):
        """Apply brightness cap to a Color object."""
        if self.brightness_cap >= 1.0:
            return color
        red = int(((color >> 16) & 0xFF) * self.brightness_cap)
        green = int(((color >> 8) & 0xFF) * self.brightness_cap)
        blue = int((color & 0xFF) * self.brightness_cap)
        return Color(red, green, blue)

    def show_running_light(self, length=5, fade_length=5):
        if self.counter >= (1 * self.config["mode_params"]["slowdown_speed_factor"]):
            self.counter = 0
            for pixel_index in range(self.strip.numPixels()):
                self.strip.setPixelColor(pixel_index, Color(0, 0, 0))

            capped_color = self._apply_brightness_cap(self.color)
            for fade_index in range(0, fade_length):
                color = capped_color
                fade_factor = fade_index / fade_length
                fade_factor *= fade_factor
                red = int(((color >> 16) & 0xFF) * fade_factor)
                green = int(((color >> 8) & 0xFF) * fade_factor)
                blue = int((color & 0xFF) * fade_factor)
                self.strip.setPixelColor(
                    (self.index + fade_index) % self.strip.numPixels(),
                    Color(red, green, blue),
                )

            for pixel_index in range(0, length):
                self.strip.setPixelColor(
                    (self.index + fade_length + pixel_index) % self.strip.numPixels(),
                    capped_color,
                )

            self.strip.show()
            self.index = (self.index + 1) % self.strip.numPixels()
        else:
            self.counter += 1

    def show_pulsing_light(self, min_brightness=0.2, max_brightness=1.0, step=0.005):
        if self.pulse_up:
            self.brightness += step
            if self.brightness >= max_brightness:
                self.pulse_up = False
        else:
            self.brightness -= step
            if self.brightness <= min_brightness:
                self.pulse_up = True

        capped_color = self._apply_brightness_cap(self.color)
        for pixel_index in range(self.strip.numPixels()):
            red = int(((capped_color >> 16) & 0xFF) * self.brightness)
            green = int(((capped_color >> 8) & 0xFF) * self.brightness)
            blue = int((capped_color & 0xFF) * self.brightness)
            self.strip.setPixelColor(pixel_index, Color(red, green, blue))
        self.strip.show()

    def show_solid_light(self):
        capped_color = self._apply_brightness_cap(self.color)
        for pixel_index in range(self.strip.numPixels()):
            self.strip.setPixelColor(pixel_index, capped_color)
        self.strip.show()

    def show_rainbow_light(self):
        profiles = {
            "classic": {"speed": 3, "spread": 256},
            "ocean": {"speed": 2, "spread": 128},
            "fire": {"speed": 4, "spread": 96},
        }
        profile = profiles.get(self.variant, profiles["classic"])

        for pixel_index in range(self.strip.numPixels()):
            wheel_index = (pixel_index * profile["spread"] // max(self.strip.numPixels(), 1)) + self.rainbow_offset
            wheel_color = self._wheel(wheel_index & 255, self.variant)
            capped_color = self._apply_brightness_cap(wheel_color)
            self.strip.setPixelColor(pixel_index, capped_color)

        self.strip.show()
        self.rainbow_offset = (self.rainbow_offset + profile["speed"]) & 255

    def set_lightmode(self, target_mode, color=None, variant=None):
        if target_mode == "running" and self.mode == "pulse":
            self.index = 0
            self.counter = 0
        self.mode = target_mode
        if color is not None:
            self.color = color
        if variant is not None:
            self.variant = variant

    def turn_off_leds(self):
        for pixel_index in range(self.strip.numPixels()):
            self.strip.setPixelColor(pixel_index, Color(0, 0, 0))
        self.strip.show()

    async def run(self):
        while True:
            if self.mode == "running":
                self.show_running_light(
                    self.config["mode_params"]["running_length"],
                    self.config["mode_params"]["running_fade_length"],
                )
            elif self.mode == "pulse":
                self.show_pulsing_light()
            elif self.mode == "solid":
                self.show_solid_light()
            elif self.mode == "rainbow":
                self.show_rainbow_light()
            await asyncio.sleep(0.001)

    def _wheel(self, position: int, variant: str):
        if variant == "ocean":
            return self._ocean_wheel(position)
        if variant == "fire":
            return self._fire_wheel(position)
        return self._classic_wheel(position)

    def _classic_wheel(self, position: int):
        if position < 85:
            return Color(position * 3, 255 - position * 3, 0)
        if position < 170:
            position -= 85
            return Color(255 - position * 3, 0, position * 3)
        position -= 170
        return Color(0, position * 3, 255 - position * 3)

    def _ocean_wheel(self, position: int):
        if position < 128:
            return Color(0, 40 + position, 120 + position)
        position -= 128
        return Color(0, 168 - position, 248 - position)

    def _fire_wheel(self, position: int):
        if position < 85:
            return Color(255, position * 2, 0)
        if position < 170:
            position -= 85
            return Color(255, 170 + position, position)
        position -= 170
        return Color(255 - position * 3, 255 - position * 2, 60 - min(position, 60))
