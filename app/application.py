from __future__ import annotations

import asyncio
from pathlib import Path

from rpi_ws281x import Color

from app.config import AppConfig
from app.gpio_input import GPIOInputController
from app.mode_manager import ModeManager
from app.modes.rainbow_mode import RainbowMode
from app.modes.static_mode import StaticMode
from app.modes.trainer_zone_mode import TrainerZoneMode
from app.services.trainer_service import TrainerService
from app.state import RuntimeState
from app.state_store import StateStore


class Power2ColorApp:
    def __init__(self, config_path: str, led_control, debug: bool = False, fake_input: bool = False):
        self.config = AppConfig(config_path)
        self.led_control = led_control
        self.runtime_state = RuntimeState()
        self.state_store = StateStore(Path(config_path).with_name(self.config.state_file))
        self._load_persisted_state()
        self.trainer_service = TrainerService(self.config, self.runtime_state, debug=debug, fake_input=fake_input)
        initial_mode_id = self.runtime_state.active_mode_id or self.config.initial_mode_id
        self.mode_manager = ModeManager(self._build_modes(debug), initial_mode_id=initial_mode_id)
        self.input_controller = GPIOInputController(
            mode_button_gpio=self.config.mode_button_gpio,
            color_button_gpio=self.config.color_button_gpio,
            debounce_ms=self.config.button_debounce_ms,
        )
        self.fake_input = fake_input

    async def run(self):
        await self.mode_manager.start(self.runtime_state)
        self._save_state()

        tasks = [
            asyncio.create_task(self.led_control.run()),
            asyncio.create_task(self._run_modes()),
            asyncio.create_task(self.input_controller.run(self._handle_mode_next, self._handle_color_next)),
        ]

        if self.fake_input:
            tasks.append(asyncio.create_task(self.trainer_service.create_fake_input()))
        else:
            tasks.append(asyncio.create_task(self.trainer_service.run()))

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            print("Program ended by user.")
            raise
        finally:
            self.input_controller.close()
            self.led_control.turn_off_leds()
            await self.trainer_service.stop()

    async def _run_modes(self):
        while True:
            await self.mode_manager.update(self.runtime_state, 0.1)
            await asyncio.sleep(0.1)

    def _build_modes(self, debug: bool):
        modes = []
        for mode_config in self.config.modes:
            mode_type = mode_config.get("type")
            mode_id = mode_config.get("id")
            if mode_type == "trainer":
                modes.append(
                    TrainerZoneMode(
                        service=self.trainer_service,
                        led_control=self.led_control,
                        idle_color=Color(*self.config.mode_params["idle_color"]),
                        connecting_color=Color(*self.config.trainer_color("connecting_color", [0, 0, 255])),
                        running_color=Color(*self.config.trainer_color("idle_running_color", [255, 255, 255])),
                        debug=debug,
                    )
                )
            elif mode_type == "static":
                color_names = mode_config.get("colors", list(self.config.color_palette.keys()))
                colors = [Color(*self.config.resolve_color(color_name)) for color_name in color_names]
                default_color = mode_config.get("default_color", color_names[0])
                default_index = color_names.index(default_color) if default_color in color_names else 0
                mode = StaticMode(self.led_control, colors=colors, default_index=default_index)
                mode.mode_id = mode_id
                modes.append(mode)
            elif mode_type == "rainbow":
                variants = mode_config.get("variants", ["classic", "ocean", "fire"])
                default_variant = mode_config.get("default_variant", variants[0])
                default_index = variants.index(default_variant) if default_variant in variants else 0
                mode = RainbowMode(self.led_control, variants=variants, default_index=default_index)
                mode.mode_id = mode_id
                modes.append(mode)

        if not modes:
            raise ValueError("No enabled modes were created from the configuration")
        return modes

    async def _handle_mode_next(self):
        await self.mode_manager.next_mode(self.runtime_state)
        self._save_state()

    async def _handle_color_next(self):
        await self.mode_manager.color_next(self.runtime_state)
        self._save_state()

    def _load_persisted_state(self):
        if not self.config.persist_last_state:
            self.runtime_state.active_mode_id = self.config.initial_mode_id
            return

        data = self.state_store.load()
        self.runtime_state.active_mode_id = data.get("active_mode_id", self.config.initial_mode_id)
        self.runtime_state.selection_index_by_mode = data.get("selection_index_by_mode", {})

    def _save_state(self):
        if self.config.persist_last_state:
            self.state_store.save(self.runtime_state)
