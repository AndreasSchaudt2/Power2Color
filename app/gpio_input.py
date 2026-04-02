from __future__ import annotations

import asyncio

try:
    from gpiozero import Button
except ImportError:  # pragma: no cover - only occurs off-device
    Button = None


class GPIOInputController:
    def __init__(self, mode_button_gpio: int | None, color_button_gpio: int | None, debounce_ms: int = 40):
        self.mode_button_gpio = mode_button_gpio
        self.color_button_gpio = color_button_gpio
        self.debounce_seconds = debounce_ms / 1000
        self._queue = asyncio.Queue()
        self._buttons = []

    async def run(self, on_mode_next, on_color_next):
        if Button is None:
            print("gpiozero is not installed. GPIO button input disabled.")
            return

        if self.mode_button_gpio is None or self.color_button_gpio is None:
            print("Button GPIOs are not configured. GPIO button input disabled.")
            return

        loop = asyncio.get_running_loop()
        try:
            mode_button = Button(self.mode_button_gpio, pull_up=True, bounce_time=self.debounce_seconds)
            color_button = Button(self.color_button_gpio, pull_up=True, bounce_time=self.debounce_seconds)
        except Exception as error:
            print(
                "GPIO button input disabled due to initialization error. "
                "Install a supported gpiozero backend (recommended: lgpio). "
                f"Details: {error}"
            )
            return

        self._buttons = [mode_button, color_button]

        mode_button.when_pressed = lambda: loop.call_soon_threadsafe(self._queue.put_nowait, "mode_next")
        color_button.when_pressed = lambda: loop.call_soon_threadsafe(self._queue.put_nowait, "color_next")

        try:
            while True:
                event = await self._queue.get()
                if event == "mode_next":
                    await on_mode_next()
                elif event == "color_next":
                    await on_color_next()
        finally:
            self.close()

    def close(self):
        for button in self._buttons:
            button.close()
        self._buttons = []
