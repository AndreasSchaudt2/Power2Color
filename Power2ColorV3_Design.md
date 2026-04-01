# Power2Color V3 - Architecture and Design

## 1. Purpose

This document defines the V3 architecture for extending Power2Color with configurable lighting modes and two-button control, while keeping trainer integration and optional Intervals.icu zone download.

Goals:
- Reuse existing Power2Color core capabilities.
- Add multiple user-selectable modes (trainer, static, rainbow, etc.).
- Use two physical buttons with simple behavior:
  - Button 1: cycle modes.
  - Button 2: cycle colors (or mode variant when applicable).
- Configure modes/colors centrally in `config.yaml`.
- Remove Wi-Fi onboarding/federation from runtime logic.
- Keep the system responsive even if Bluetooth trainer is unavailable.

## 2. Hardware Mapping (Current Build)

- Mode button GPIO: `20`
- Color button GPIO: `22`
- LED data GPIO: `21`
- Platform: Raspberry Pi Zero 2 W

Note:
Some LED libraries/backends only support specific output pins. GPIO 21 must be validated with the selected LED driver. If unsupported, move LED data to a known supported pin (often GPIO 18) while keeping the architecture unchanged.

## 3. High-Level Architecture

The system is split into independent modules:

1. `Config Loader`
- Loads and validates `config.yaml`.
- Builds enabled mode list and color palette.

2. `Input Controller`
- Polls/interrupts GPIO buttons.
- Debounces and emits semantic events: `MODE_NEXT`, `COLOR_NEXT`.

3. `Mode Manager`
- Holds active mode index.
- Switches modes on `MODE_NEXT`.
- Forwards `COLOR_NEXT` to active mode behavior.

4. `Renderer`
- Updates LED strip at fixed FPS.
- Calls active mode `update()` with shared runtime state.

5. `Trainer Service` (background)
- Handles Bluetooth connection, power notifications, reconnect logic.
- Publishes latest power data and connection state.

6. `Zone Service` (optional background)
- Fetches zones from Intervals.icu when enabled.
- Falls back to local configured zones on failure.

7. `State Store`
- Persists minimal runtime selections (mode and per-mode color/variant index).

## 4. Runtime State Model

Shared state should be explicit and minimal:

- `active_mode_id`
- `mode_index`
- `selection_index_by_mode` (color or variant index)
- `trainer.connected` (bool)
- `trainer.status` (`disconnected` | `connecting` | `connected` | `stale`)
- `trainer.latest_power_watts`
- `trainer.last_power_timestamp`
- `zones.active`
- `zones.source` (`local` | `intervals`)

## 5. Mode Contract

Each mode implements a common interface:

- `start(context)`
- `stop(context)`
- `on_color_next(context)`
- `update(context, dt)`

Recommended first modes:
- `trainer_zone`
- `static`
- `rainbow`

Behavior:
- Mode switching triggers `stop(old)` then `start(new)`.
- `on_color_next` behavior is mode-defined but configured through `config.yaml`.

## 6. Button Behavior

Simple and fixed interaction model:

- Button 1 (GPIO 20): next enabled mode.
- Button 2 (GPIO 22): next color/variant for current mode.

Debounce guidance:
- Start with `40ms` software debounce.
- Keep event handler non-blocking.

## 7. Startup Sequence

Boot must be responsive and non-blocking:

1. Load + validate config.
2. Initialize LEDs and buttons.
3. Load persisted UI state (if enabled).
4. Start render loop immediately.
5. Start Trainer Service in background.
6. Start Zone Service in background (if enabled).
7. Continue normal operation regardless of service readiness.

Key principle:
- LED controller must not wait for Bluetooth or internet to become available.

## 8. Bluetooth and Intervals.icu Handling

### 8.1 Trainer Service

- Attempts connection on startup in background.
- Subscribes to power notifications.
- Updates shared trainer state.
- Reconnects with capped backoff when unavailable.

Suggested retry pattern:
- 2s, 5s, 10s, then every 20-30s (with small random jitter).

Stale data detection:
- If no power update for 3-5s while connected, transition to `stale`.

### 8.2 Zone Service (Intervals.icu)

- Enabled only by config.
- Optional one-shot fetch on boot.
- On success: atomically replace active zones.
- On failure: keep local zones, log warning, retry later.

## 9. Failure/Recovery Policy

### 9.1 Trainer unavailable at startup

- System still boots and accepts button input.
- Non-trainer modes work normally.
- Trainer mode shows fallback visual pattern.
- Reconnect loop continues in background.

### 9.2 Trainer disconnect during runtime

- Detect timeout/stale state.
- Trainer mode enters fallback pattern.
- Other modes unaffected.
- Auto-reconnect in background.

### 9.3 Intervals fetch failure

- Keep local zone config.
- Do not block rendering.
- Retry later with long interval.

## 10. `config.yaml` Blueprint

```yaml
global:
  fps: 30
  brightness: 0.6
  persist_last_state: true

hardware:
  led_data_gpio: 21
  led_count: 60
  mode_button_gpio: 20
  color_button_gpio: 22
  button_debounce_ms: 40

trainer:
  autoconnect: true
  reconnect_backoff_seconds: [2, 5, 10, 20, 30]
  stale_after_seconds: 4
  fallback_visual: trainer_disconnected_pulse

intervals_icu:
  enabled: true
  fetch_on_startup: true
  refresh_minutes: 60
  username_env: INTERVALS_USERNAME
  api_key_env: INTERVALS_API_KEY
  fallback_to_local_zones: true

colors:
  warm_white: [255, 180, 80]
  red: [255, 0, 0]
  green: [0, 255, 0]
  blue: [0, 80, 255]
  cyan: [0, 255, 180]
  magenta: [255, 0, 180]

modes:
  - id: trainer_zone
    enabled: true
    type: trainer
    supports_color_cycle: false
    zone_colors:
      z1: warm_white
      z2: green
      z3: blue
      z4: cyan
      z5: magenta
      z6: red

  - id: static
    enabled: true
    type: static
    supports_color_cycle: true
    colors: [warm_white, red, green, blue, cyan, magenta]
    default_color: warm_white

  - id: rainbow
    enabled: true
    type: rainbow
    supports_color_cycle: true
    variants: [classic, ocean, fire]
    default_variant: classic
```

## 11. No Wi-Fi Federation in Runtime

V3 assumption:
- Networking is preconfigured when preparing the SD card.

Therefore runtime code should:
- Remove Wi-Fi onboarding flows.
- Remove first-boot network setup logic.
- Keep only operational checks (for optional cloud fetch).

## 12. Recommended Project Layout

```text
power2color/
  main.py
  config.yaml
  state.json
  app/
    config.py
    state.py
    gpio_input.py
    mode_manager.py
    renderer.py
    services/
      trainer_service.py
      intervals_service.py
    modes/
      base_mode.py
      trainer_zone_mode.py
      static_mode.py
      rainbow_mode.py
```

## 13. Logging and Diagnostics

Log at info/warn/error levels with concise messages:
- startup stage complete
- mode changed
- color/variant changed
- trainer connected/disconnected/stale
- intervals fetch success/fail

Avoid per-frame logs.

## 14. Test Plan (Minimum)

1. Button test
- Press mode button repeatedly: modes rotate only through enabled list.
- Press color button in static mode: colors rotate as configured.

2. Trainer unavailable test
- Boot without trainer powered.
- Verify app remains responsive and trainer mode shows fallback.

3. Disconnect test
- Connect trainer, start trainer mode, then power trainer off.
- Verify stale/disconnect fallback and auto-reconnect attempts.

4. Intervals failure test
- Disable network or use invalid credentials.
- Verify local zones remain active and app continues.

5. Persistence test
- Select mode/color, reboot.
- Verify state restoration if enabled.

## 15. Implementation Order

1. Introduce mode manager and mode interface around existing trainer logic.
2. Add config-driven mode/color definitions.
3. Add GPIO input controller for two-button events (GPIO 20/22).
4. Add static and rainbow modes.
5. Move trainer and intervals logic into background services.
6. Add reconnect/stale handling and fallback visuals.
7. Remove Wi-Fi onboarding runtime logic.
8. Add state persistence and final hardening.

## 16. Acceptance Criteria

V3 is complete when:
- System boots and renders without blocking on BLE/network.
- Button 1 cycles modes; Button 2 cycles color/variant.
- Modes and colors are fully controlled by `config.yaml`.
- Trainer failures do not crash app and recover automatically.
- Optional Intervals.icu fetch updates zones without breaking operation.
- Wi-Fi federation/onboarding logic is removed from runtime.
