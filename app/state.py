from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrainerState:
    connected: bool = False
    status: str = "disconnected"
    latest_power_watts: int = 0
    last_power_timestamp: float = 0.0


@dataclass
class RuntimeState:
    active_mode_id: str = "trainer_zone"
    mode_index: int = 0
    selection_index_by_mode: dict[str, int] = field(default_factory=dict)
    trainer: TrainerState = field(default_factory=TrainerState)
    zones: list[tuple[str, float, float, Any]] = field(default_factory=list)
    zone_source: str = "local"
