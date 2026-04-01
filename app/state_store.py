from __future__ import annotations

import json
from pathlib import Path


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save(self, state) -> None:
        payload = {
            "active_mode_id": state.active_mode_id,
            "selection_index_by_mode": state.selection_index_by_mode,
        }
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
