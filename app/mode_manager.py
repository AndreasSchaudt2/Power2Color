from __future__ import annotations


class ModeManager:
    def __init__(self, modes, initial_mode_id: str | None = None):
        if not modes:
            raise ValueError("At least one mode must be configured")
        self._modes = modes
        self._active_index = self._resolve_initial_index(initial_mode_id)

    @property
    def active_mode(self):
        return self._modes[self._active_index]

    @property
    def modes(self):
        return self._modes

    async def start(self, context):
        context.mode_index = self._active_index
        context.active_mode_id = self.active_mode.mode_id
        await self.active_mode.start(context)

    async def stop(self, context):
        await self.active_mode.stop(context)

    async def update(self, context, dt: float):
        await self.active_mode.update(context, dt)

    async def next_mode(self, context):
        await self.active_mode.stop(context)
        self._active_index = (self._active_index + 1) % len(self._modes)
        context.mode_index = self._active_index
        context.active_mode_id = self.active_mode.mode_id
        await self.active_mode.start(context)

    async def color_next(self, context):
        await self.active_mode.on_color_next(context)

    def _resolve_initial_index(self, initial_mode_id: str | None) -> int:
        if initial_mode_id is None:
            return 0
        for index, mode in enumerate(self._modes):
            if mode.mode_id == initial_mode_id:
                return index
        return 0
