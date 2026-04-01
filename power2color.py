from dotenv import load_dotenv, find_dotenv
import argparse

from app.application import Power2ColorApp
from app.renderer import LEDControl



# Load environment variables from .env file if it exists
load_dotenv(find_dotenv())

async def main(app):
    await app.run()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Power2Color")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--fakeinput", type=bool, nargs='?', const=True, default=False, help="Enable fake input mode")
    args = parser.parse_args()

    debug = args.debug
    fakeinput = args.fakeinput

    config_path = 'config.yaml'
    led_control = LEDControl(config_path)
    app = Power2ColorApp(config_path, led_control, debug=debug, fake_input=fakeinput)
    try:
        import asyncio
        asyncio.run(main(app))
    except KeyboardInterrupt:
        led_control.turn_off_leds()
        print("Program interrupted by user.")