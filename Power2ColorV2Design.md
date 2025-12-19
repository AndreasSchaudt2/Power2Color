# PiTrainerLED - Power Zone Visualizer Design Document

## Goal

To visualize a cyclist's power training zones on an LED strip, based on real-time data from a smart indoor trainer, controlled by a Raspberry Pi.

## Key Principles

*   **Modularity:** Decomposed into independent services for robustness and maintainability.
*   **Asynchronous Processing:** Utilizes `asyncio` within services for concurrent I/O-bound tasks.
*   **Inter-Process Communication (IPC):** MQTT for reliable, decoupled communication between services.
*   **State Management:** Explicit handling of system and LED display states.
*   **User Configuration:** Web interface for easy setup and adjustment.

---

## I. System Architecture

The system consists of a Raspberry Pi running a local MQTT broker (Mosquitto) and four primary Python services managed by `systemd`.

### A. Core Components

1.  **Mosquitto MQTT Broker**
    *   **Role:** The central communication hub for all Python services.
    *   **Platform:** Standard Linux service.
    *   **Functionality:** Receives and distributes messages between services based on a defined topic hierarchy. Supports Retained Messages and Last Will and Testament (LWT).
    *   **Installation:** `sudo apt install mosquitto mosquitto-clients`

2.  **`TrainerMonitorService`**
    *   **Role:** Connects to the smart trainer via Bluetooth LE, extracts power data, and publishes it to MQTT.
    *   **Technology:** Python, `asyncio`, `bleak`, `paho-mqtt`.
    *   **Key Responsibilities:**
        *   Discover and connect to the specified BLE smart trainer (MAC address retrieved from `config/trainer_mac` via MQTT).
        *   Subscribe to GATT notifications for the Cycling Power Service's Power Measurement Characteristic (UUID: `00002a63-0000-1000-8000-00805f9b34fb`).
        *   Parse raw power data from BLE packets.
        *   Publish `trainer/power` (raw instantaneous power) to MQTT.
        *   Publish `trainer/connection_status` ("connecting", "connected", "disconnected") to MQTT.
        *   Manage BLE reconnections upon disconnect (with backoff).
        *   Publish LWT to `status/service/TrainerMonitorService`.

3.  **`ConfigWebServerService`**
    *   **Role:** Provides a web interface for system configuration and control.
    *   **Technology:** Python, `FastAPI`, `uvicorn`, `paho-mqtt`.
    *   **Key Responsibilities:**
        *   Serve an HTML page for user interaction (using Jinja2 templates).
        *   Display current system parameters (trainer MAC, FTP, LED pin, pixel count, brightness) by subscribing to retained `config/#` topics.
        *   Allow user to edit and save configuration parameters (`config/trainer_mac`, `config/ftp`, `config/led_strip/pin`, `config/led_strip/num_pixels`, `config/led_strip/brightness`).
        *   Publish updated configuration values to MQTT with the `retain=True` flag.
        *   Provide a button to trigger the `IntervalsSyncService` to fetch updated power zones (`command/update_zones` message).
        *   (Optional) Display current `trainer/power`, `trainer/connection_status`, and `led/display_mode`.
        *   Publish LWT to `status/service/ConfigWebServerService`.

4.  **`IntervalsSyncService`**
    *   **Role:** Fetches power zone definitions and FTP from Intervals.icu.
    *   **Technology:** Python, `asyncio`, `requests`, `paho-mqtt`.
    *   **Key Responsibilities:**
        *   Listen for `command/update_zones` messages (trigger for fetching zones).
        *   Make authenticated HTTP requests to the Intervals.icu API using API key (`INTERVALS_API_KEY`) and athlete ID (`INTERVALS_ATHLETE_ID`) loaded from environment variables.
        *   Parse the API response to extract the current FTP and a list of power zone definitions (each containing name, lower bound, upper bound in watts, and color in hex format).
        *   Publish the fetched FTP to `config/ftp` (retained).
        *   Publish the fetched power zones as a JSON array to `config/power_zones` (retained).
        *   Publish LWT to `status/service/IntervalsSyncService`.

5.  **`LedControlService`**
    *   **Role:** The core logic orchestrator, controlling the physical LED strip based on all incoming data.
    *   **Technology:** Python, `asyncio`, `paho-mqtt`, `neopixel`/`rpi_ws281x`.
    *   **Key Responsibilities:**
        *   **Initialization:** On startup, attempt to initialize the `neopixel` strip with configured pin, pixel count, and brightness. Re-initialize if LED strip parameters change via MQTT.
        *   **Configuration Loading:** Subscribe to and load all `config/#` topics (FTP, power zones, LED strip parameters) using retained MQTT messages upon startup.
        *   **Data Reception:** Subscribe to `trainer/power` and `trainer/connection_status`.
        *   **Power Smoothing:** Apply an Exponential Moving Average (EMA) to the raw `trainer/power` readings (`SMOOTHING_ALPHA` configurable) to reduce flicker.
        *   **State Machine:** Maintain `current_display_mode` ("connecting", "idle", "zone") based on `trainer_connection_status` and smoothed power values. Publish `led/display_mode` changes to MQTT.
        *   **LED Control Loop (`run_led_animations`):** An `asyncio` loop that continuously updates the LED strip.
        *   **Display Modes:**
            *   **`connecting`:** Pulsating blue animation (trainer connection attempt).
            *   **`idle`:** Faint green solid color (trainer connected, but low/no significant power).
            *   **`zone`:** LED color matches the defined color of the current power zone based on `smoothed_power` and configured `FTP`.
        *   **Hardware Interface:** Uses the `neopixel` library to control the WS2812B LED strip via GPIO.
        *   Publish LWT to `status/service/LedControlService`.

---

### B. MQTT Topic Hierarchy

*   `config/trainer_mac`: RETAINED. Trainer's Bluetooth MAC address.
*   `config/ftp`: RETAINED. User's FTP value (can be set manually or by IntervalsSyncService).
*   `config/power_zones`: RETAINED. JSON array of power zone definitions (e.g., `[{"name": "Z1", "lower": 0, "upper": 100, "color": "#00FF00"}, ...]`).
*   `config/led_strip/pin`: RETAINED. GPIO pin for LED data (e.g., "18" for D18).
*   `config/led_strip/num_pixels`: RETAINED. Number of LEDs in the strip.
*   `config/led_strip/brightness`: RETAINED. Overall LED brightness (float, 0.0-1.0).
*   `trainer/power`: Current instantaneous power reading from trainer (int).
*   `trainer/connection_status`: "connected", "disconnected", "connecting".
*   `led/display_mode`: Current mode the LED strip is in ("connecting", "idle", "zone").
*   `command/update_zones`: Trigger for `IntervalsSyncService` to fetch zones (payload "true").
*   `status/service/<service_name>`: LWT for each service (e.g., `status/service/TrainerMonitorService`).

---

### II. Implementation Details & Best Practices

**A. MQTT Client Configuration (`paho-mqtt`)**

*   **Broker:** `localhost:1883` (default Mosquitto).
*   **Callbacks:** Each service will implement `on_connect` (to subscribe to topics) and `on_message` (to process incoming messages).
*   **QoS:**
    *   `config/#`, `command/#`: QoS 1 (at least once) for reliability.
    *   `trainer/power`, `trainer/connection_status`, `led/display_mode`: QoS 0 (at most once) for real-time responsiveness (loss of an occasional message is acceptable).
*   **Retained Messages:** `config/#` and `status/service/#` topics will use `retain=True` to ensure services receive initial/last known state upon connection.
*   **LWT:** Configured for each service to publish "offline" to its respective `status/service/<service_name>` topic.
*   **Looping:** `mqtt_client.loop_start()` will be used to run the MQTT client's network loop in a separate thread, preventing blocking of the main `asyncio` event loop.

**B. Asynchronous Programming (`asyncio`)**

*   All Python services that perform I/O (network requests, BLE communication, GPIO control with non-blocking sleeps) will be `asyncio`-based.
*   `asyncio.run(main_coroutine())` will be the entry point for each service's primary execution.
*   `await asyncio.sleep(duration)` will be used to yield control to the `asyncio` event loop, allowing other concurrent tasks (like `on_message` callbacks) to execute.
*   `asyncio.create_task()` will be used for fire-and-forget background tasks (e.g., initiating zone fetch without blocking the web server).

**C. Power Smoothing (within `LedControlService`)**

*   **Algorithm:** Exponential Moving Average (EMA).
*   **Equation:** `smoothed_power = (SMOOTHING_ALPHA * new_raw_power) + ((1.0 - SMOOTHING_ALPHA) * previous_smoothed_power)`
*   **`SMOOTHING_ALPHA`:** Configurable (float, typically `0.1` to `0.5`). A value around `0.3` is a good starting point for balancing smoothness and responsiveness.
*   **Implementation:**
    *   The `on_message` handler for `trainer/power` will update the `smoothed_power` global variable.
    *   The `smoothed_power` variable will be initialized to 0.0 and will pick up the first non-zero `new_raw_power` directly, then start applying the EMA.
    *   When in "connecting" mode, `smoothed_power` should be reset to 0.0 to ensure a clean start for EMA when power data resumes.

**D. State Machine Logic (within `LedControlService`)**

*   **`set_display_mode(new_mode)` helper function:** This central function will be responsible for:
    1.  Updating the global `current_display_mode` variable.
    2.  Publishing the `new_mode` to `led/display_mode` topic via MQTT (only if the mode actually changes).
    3.  Printing the mode change for logging/debugging.
*   **Mode Evaluation:** The `run_led_animations` loop will continuously re-evaluate the display mode based on:
    1.  **`trainer_connection_status`:** If not "connected", always default to "connecting".
    2.  **`smoothed_power`:** If connected:
        *   If `smoothed_power < (FTP * 0.1)` (or a configurable low-power threshold), set to "idle".
        *   If `smoothed_power >= (FTP * 0.1)`, set to "zone".
*   This hierarchical evaluation ensures reliable and responsive mode transitions.

**E. Hardware Interface (`LedControlService`)**

*   **Library:** `neopixel` (CircuitPython NeoPixel library).
*   **GPIO Pin:** Configured via MQTT `config/led_strip/pin`.
*   **Initialization:** The `init_pixels()` function should be robust to parameter changes, potentially de-initializing and re-initializing the `neopixel` object.
*   **Permissions:** The `systemd` service for `LedControlService` must have appropriate permissions to access GPIO, possibly by running as a user in the `gpio` group or via specific `sudoers` configurations for non-root execution.

**F. Configuration Management**

*   **API Keys/IDs:** Intervals.icu `INTERVALS_API_KEY` and `INTERVALS_ATHLETE_ID` should be stored as environment variables on the Raspberry Pi for security (e.g., in `.bashrc` or directly in the `systemd` unit file for `IntervalsSyncService`).
*   **Initial Configuration:** All services are designed to receive their critical initial configuration parameters via retained MQTT messages immediately upon connecting to the broker.

**G. Service Management (`systemd`)**

*   Each Python service will have a dedicated `systemd` unit file (`.service`) located in `/etc/systemd/system/`.
*   These files will configure:
    *   `Description`: Service name.
    *   `After=network.target mosquitto.service`: Ensures network and MQTT broker are up before starting.
    *   `User`: The user to run the service as (e.g., `pi`).
    *   `WorkingDirectory`: The directory containing the service's Python script.
    *   `ExecStart`: The command to execute the Python script (e.g., `/usr/bin/python3 service_name.py`).
    *   `Restart=always`: Ensures the service restarts automatically if it crashes.
    *   `Environment`: For setting API keys/IDs in `systemd` environment.

---

### III. Setup and Deployment

1.  **Raspberry Pi OS Setup:** Install a fresh Raspberry Pi OS (Lite recommended).
2.  **Git Clone:** Clone your project repository to a suitable location (e.g., `/home/pi/pi-trainer-led`).
3.  **Mosquitto Installation:**
    ```bash
 sudo apt update
 sudo apt install mosquitto mosquitto-clients
 sudo systemctl enable mosquitto
 sudo systemctl start mosquitto
    ```
4.  **Python Environment:**
    *   Install `pip` and create a virtual environment:
        ```bash
     sudo apt install python3-pip python3-venv
     python3 -m venv ~/pi-trainer-led/venv
     source ~/pi-trainer-led/venv/bin/activate
        ```
    *   Install Python dependencies: `pip install paho-mqtt fastapi uvicorn bleak requests adafruit-circuitpython-neopixel python-dotenv` (add others as needed).
    *   Deactivate virtual environment if not needed for direct testing: `deactivate`
5.  **GPIO Permissions:** Add the user running the LED service to the `gpio` group: `sudo adduser pi gpio`.
6.  **Environment Variables:** Set Intervals.icu API key and athlete ID.
7.  **`systemd` Service Files:** Create and place `.service` files for each service in `/etc/systemd/system/`, adapting paths and `ExecStart` commands to use the virtual environment's Python interpreter (e.g., `/home/pi/pi-trainer-led/venv/bin/python3`).
8.  **Enable and Start Services:**
    ```bash
 sudo systemctl daemon-reload
 sudo systemctl enable <service_name>.service
 sudo systemctl start <service_name>.service
    ```
9.  **Initial Configuration:** Access the `ConfigWebServerService` via `http://<raspberry_pi_ip_address>/` to set initial configuration values.

---

This design document covers all the major components and interactions, providing a clear roadmap for implementation.
