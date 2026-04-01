from __future__ import annotations

from app.modes.base_mode import BaseMode


class TrainerZoneMode(BaseMode):
    mode_id = "trainer_zone"

    def __init__(self, service, led_control, idle_color, connecting_color, running_color, debug: bool = False):
        self.service = service
        self.led_control = led_control
        self.idle_color = idle_color
        self.connecting_color = connecting_color
        self.running_color = running_color
        self.debug = debug
        self.state = "connecting"

    async def start(self, context):
        self.state = "connecting"
        self.led_control.set_lightmode("pulse", self.connecting_color)

    async def on_color_next(self, context):
        return None

    async def update(self, context, dt: float):
        power = self.service.get_power()

        if self.debug:
            print(f"Power: {power} hence zone state: {self.state}")

        if self.service.connected:
            if self.state == "connecting":
                self.state = "idle"
        elif self.state != "connecting":
            self.state = "connecting"

        if self.state == "connecting":
            self.led_control.set_lightmode("pulse", self.connecting_color)
            return

        if self.state == "idle":
            if power > 0:
                self.state = "in_zone"
            self.led_control.set_lightmode("running", self.running_color)
            return

        if power == 0:
            self.state = "idle"
            self.led_control.set_lightmode("running", self.running_color)
            return

        self.led_control.set_lightmode("pulse", self.service.determine_zone_color())
