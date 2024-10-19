import requests
import yaml
import json
from requests.auth import HTTPBasicAuth

# Load configuration from YAML file
with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

# Extract athlete ID, API key, and FTP type from configuration
athlete_id = config['athlete']['id']
api_key = config['athlete']['api_key']
ftp_type = config['athlete'].get('ftp_type', 'ftp')  # Default to 'ftp' if not specified

# Intervals.icu API URL
url = f"https://intervals.icu/api/v1/athlete/{athlete_id}"

# Make the API request with basic authentication
response = requests.get(url, auth=HTTPBasicAuth('API_KEY', api_key), headers={'accept': '*/*'})

# Check if the request was successful
if response.status_code == 200:
    # Get the response data
    data = response.json()
    
    # Find the relevant section in sportSettings where type contains "Ride"
    sport_settings = data.get('sportSettings', [])
    #print('found sport settings') 
    #print(sport_settings)
    ride_settings = next((setting for setting in sport_settings if 'Ride' in setting.get('types', '')), None)
    
    if ride_settings:
        # Extract FTP or indoor FTP based on configuration
        ftp = ride_settings.get(ftp_type)
        power_zones_percentages = ride_settings.get('power_zones', [])
        power_zone_names = ride_settings.get('power_zone_names', [])
        
        if ftp and power_zones_percentages and power_zone_names:
            # Calculate the power zones based on FTP and percentages
            power_zones = []

            # Add the first zone starting from 0
            min_watt = 0
            max_watt = ftp * power_zones_percentages[0] / 100
            zone_name = power_zone_names[0]
            power_zones.append({
                'zone_number': 1,
                'min_watt': min_watt,
                'max_watt': max_watt,
                'name': zone_name
            })

            # Add the remaining zones
            for i in range(1, len(power_zones_percentages)):
                min_watt = ftp * power_zones_percentages[i - 1] / 100
                max_watt = ftp * power_zones_percentages[i] / 100
                zone_name = power_zone_names[i]
                power_zones.append({
                    'zone_number': i + 1,
                    'min_watt': min_watt,
                    'max_watt': max_watt,
                    'name': zone_name
                })

            # Print the calculated power zones
            for zone in power_zones:
                print(f"Zone {zone['zone_number']} '{zone['name']}': {zone['min_watt']}W - {zone['max_watt']}W")
        else:
            print("Failed to retrieve FTP, power zones percentages, or power zone names from the Ride settings.")
    else:
        print("No Ride settings found in sportSettings.")
else:
    print(f"Failed to retrieve data: {response.status_code} - {response.text}")