# Power2Color

Power2Color is a Raspberry Pi 4 based project that visualizes your current power zone on an indoor trainer using a LED strip with directly addressable LEDs. This project enhances your indoor training experience by providing real-time visual feedback on your power output.

## Features

- **Real-time Power Zone Visualization**: The LED strip lights up in different colors according to your current power zone.
- **Configurable Power Zones**: Power zones can be configured via a local config file or fetched from a configurable Intervals.icu account.
- **Bluetooth Connectivity**: The Raspberry Pi connects to your indoor trainer via Bluetooth to constantly read power data.
- **Dynamic LED Effects**: LEDs pulse slightly while in a zone and light up brighter during the first seconds when entering a new zone.

## Compatible Trainers
This was defeloped and tested only for the follwing Trainers:
- Wahoo Kickr Core, Model WF123, Version 1.0
Most shoud work but one needs to find out the following information. I will add info on how to derive this info for other trainers later.
- bluetooth adress (easy, like DF:36:42:3D:BD:A4)
- UUID of the bluetooth service (difficult, like 00002a63-0000-1000-8000-00805f9b34fb )
Both values need to be entered in the conf.yaml file.

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
    git clone https://github.com/AndreasSchaudt2/Power2Color.git
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
      ./run_power2color.sh
      ```

## Setting Up Automatic Startup

To ensure the script starts automatically when the Raspberry Pi boots up, you can create a systemd service:

1. **Create a systemd service file**:
    - Create a new service file in the `/etc/systemd/system/` directory. For example, `power2color.service`:
      ```sh
      sudo nano /etc/systemd/system/power2color.service
      ```

2. **Define the service**:
    - Add the following content to the `power2color.service` file:
      ```ini
      [Unit]
      Description=Power2Color Service
      After=network.target

      [Service]
      ExecStart=/home/pi/Power2Color/run_power2color.sh
      WorkingDirectory=/home/pi/Power2Color
      User=pi
      Restart=always

      [Install]
      WantedBy=multi-user.target
      ```
      make sure the paths are correct. They are depending on the user.

3. **Reload systemd to apply the new service**:
    ```sh
    sudo systemctl daemon-reload
    ```

4. **Enable the service to start on boot**:
    ```sh
    sudo systemctl enable power2color.service
    ```

5. **Start the service**:
    ```sh
    sudo systemctl start power2color.service
    ```

6. **Check the status of the service**:
    ```sh
    sudo systemctl status power2color.service
    ```

This setup will ensure that your script runs automatically on startup and keeps running even if it crashes.

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