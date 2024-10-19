# Power2Color

Power2Color is a Raspberry Pi 4 based project that visualizes your current power zone on an indoor trainer using a LED strip with directly addressable LEDs. This project enhances your indoor training experience by providing real-time visual feedback on your power output.

## Features

- **Real-time Power Zone Visualization**: The LED strip lights up in different colors according to your current power zone.
- **Configurable Power Zones**: Power zones can be configured via a local config file or fetched from a configurable Intervals.icu account.
- **Bluetooth Connectivity**: The Raspberry Pi connects to your indoor trainer via Bluetooth to constantly read power data.
- **Dynamic LED Effects**: LEDs pulse slightly while in a zone and light up brighter during the first seconds when entering a new zone.

## Requirements

- Raspberry Pi 4
- LED strip with directly addressable LEDs (e.g., WS2812B)
- Indoor trainer with Bluetooth power output
- Intervals.icu account (optional for fetching power zones)

## Installation

1. **Set up the Raspberry Pi**:
    - Install the latest version of Raspberry Pi OS.
    - Ensure Bluetooth is enabled on the Raspberry Pi.

2. **Clone the Repository**:
    ```sh
    git clone https://github.com/your-username/Power2Color.git
    cd Power2Color
    ```

3. **Install Dependencies**:
    ```sh
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip
    pip3 install -r requirements.txt
    ```

4. **Configure Power Zones**:
    - Edit the `config.json` file to set your power zones manually.
    - Alternatively, configure your Intervals.icu account details in the `config.json` to fetch power zones automatically.

## Usage

1. **Connect to the Indoor Trainer**:
    - Ensure your indoor trainer is powered on and in Bluetooth pairing mode.
    - Run the connection script to pair with the trainer:
      ```sh
      python3 connect_trainer.py
      ```

2. **Start the Visualization**:
    - Run the main script to start visualizing your power zones:
      ```sh
      python3 main.py
      ```

## Configuration

The `config.json` file allows you to configure various settings:

- **Power Zones**: Define your power zones manually or set up your Intervals.icu account to fetch them automatically.
- **LED Strip Settings**: Configure the number of LEDs and the GPIO pin used for the LED strip.

Example `config.json`:
```json
{
  "power_zones": {
     "ftp": 250,
     "zones": [100, 150, 200, 250, 300, 350, 400]
  },
  "intervals_icu": {
     "enabled": true,
     "username": "your-username",
     "api_key": "your-api-key"
  },
  "led_strip": {
     "num_leds": 60,
     "gpio_pin": 18
  }
}
```


Contributing
Contributions are welcome! Please fork the repository and submit a pull request with your changes.

License
This project is licensed under the MIT License. See the LICENSE file for details.

Acknowledgements
Thanks to the developers of the libraries and tools used in this project.
Special thanks to the Intervals.icu team for their API.


Replace `your-username` and `your-api-key` with your actual GitHub username and Intervals.icu API key.