from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML


DEFAULT_COLOR_NAMES = [
    "blue",
    "green",
    "yellow",
    "orange",
    "red",
    "magenta",
    "purple",
    "teal",
    "olive",
]


class AppConfig:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._yaml = YAML()
        self.data = self._load()

    def _load(self):
        with self.path.open("r", encoding="utf-8") as handle:
            return self._yaml.load(handle)

    def save(self) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            self._yaml.dump(self.data, handle)

    @property
    def bluetooth(self):
        return self.data["bluetooth"]

    @property
    def led_strip(self):
        led_strip = dict(self.data["led_strip"])
        hardware_settings = self.hardware_settings
        if "led_data_gpio" in hardware_settings:
            led_strip["pin"] = hardware_settings["led_data_gpio"]
        return led_strip

    @property
    def mode_params(self):
        return self.data["mode_params"]

    @property
    def use_zones_from_intervals_icu(self) -> bool:
        return bool(self.data.get("use_zones_from_intervals_icu", False))

    @property
    def power_zones(self):
        return self.data.get("power_zones", [])

    @property
    def power_zone_colors(self):
        return self.data.get("power_zones_colors", [])

    @property
    def athlete(self):
        return self.data.get("athlete", {})

    @property
    def hardware_settings(self):
        return self.data.get("hardware", {})

    @property
    def trainer_settings(self):
        return self.data.get("trainer", {})

    @property
    def global_settings(self):
        return self.data.get("global", {})

    @property
    def persist_last_state(self) -> bool:
        return bool(self.global_settings.get("persist_last_state", True))

    @property
    def state_file(self) -> str:
        return self.global_settings.get("state_file", "state.json")

    @property
    def mode_button_gpio(self) -> int | None:
        return self.hardware_settings.get("mode_button_gpio")

    @property
    def color_button_gpio(self) -> int | None:
        return self.hardware_settings.get("color_button_gpio")

    @property
    def button_debounce_ms(self) -> int:
        return int(self.hardware_settings.get("button_debounce_ms", 40))

    @property
    def color_palette(self):
        configured_colors = self.data.get("colors")
        if configured_colors:
            return configured_colors

        legacy_colors = {}
        for index, color in enumerate(self.power_zone_colors):
            name = DEFAULT_COLOR_NAMES[index] if index < len(DEFAULT_COLOR_NAMES) else f"color_{index + 1}"
            legacy_colors[name] = color
        return legacy_colors

    @property
    def modes(self):
        configured_modes = self.data.get("modes")
        if configured_modes:
            return [mode for mode in configured_modes if mode.get("enabled", True)]
        return self._build_legacy_modes()

    @property
    def initial_mode_id(self) -> str:
        configured_default = self.global_settings.get("default_mode")
        enabled_modes = self.modes
        if configured_default and any(mode["id"] == configured_default for mode in enabled_modes):
            return configured_default
        return enabled_modes[0]["id"]

    def resolve_color(self, color_name_or_value):
        if isinstance(color_name_or_value, str):
            palette = self.color_palette
            if color_name_or_value not in palette:
                raise KeyError(f"Unknown color '{color_name_or_value}'")
            return palette[color_name_or_value]
        return color_name_or_value

    def _build_legacy_modes(self):
        palette_names = list(self.color_palette.keys())
        default_color = palette_names[0] if palette_names else None
        return [
            {
                "id": "trainer_zone",
                "enabled": True,
                "type": "trainer",
                "supports_color_cycle": False,
            },
            {
                "id": "static",
                "enabled": True,
                "type": "static",
                "supports_color_cycle": True,
                "colors": palette_names,
                "default_color": default_color,
            },
            {
                "id": "rainbow",
                "enabled": True,
                "type": "rainbow",
                "supports_color_cycle": True,
                "variants": ["classic", "ocean", "fire"],
                "default_variant": "classic",
            },
        ]

    def update_bluetooth_address(self, address: str) -> None:
        self.data["bluetooth"]["address"] = address
        self.save()

    def trainer_color(self, key: str, fallback):
        return self.trainer_settings.get(key, fallback)
