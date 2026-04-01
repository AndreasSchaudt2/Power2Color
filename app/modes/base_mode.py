from __future__ import annotations


class BaseMode:
    mode_id = "base"

    async def start(self, context):
        return None

    async def stop(self, context):
        return None

    async def on_color_next(self, context):
        return None

    async def update(self, context, dt: float):
        raise NotImplementedError
