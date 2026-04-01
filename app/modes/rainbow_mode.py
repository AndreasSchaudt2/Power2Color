from __future__ import annotations

from app.modes.base_mode import BaseMode


class RainbowMode(BaseMode):
    mode_id = "rainbow"

    def __init__(self, led_control, variants, default_index: int = 0):
        self.led_control = led_control
        self.variants = variants
        self.default_index = default_index
        self.current_index = default_index

    async def start(self, context):
        self.current_index = context.selection_index_by_mode.get(self.mode_id, self.default_index)
        self.current_index %= len(self.variants)
        context.selection_index_by_mode[self.mode_id] = self.current_index
        self.led_control.set_lightmode("rainbow", variant=self.variants[self.current_index])

    async def on_color_next(self, context):
        self.current_index = (self.current_index + 1) % len(self.variants)
        context.selection_index_by_mode[self.mode_id] = self.current_index
        self.led_control.set_lightmode("rainbow", variant=self.variants[self.current_index])

    async def update(self, context, dt: float):
        self.led_control.set_lightmode("rainbow", variant=self.variants[self.current_index])
