import requests
import yaml
from requests.auth import HTTPBasicAuth

# Load configuration from YAML file
with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

# Extract athlete ID and API key from configuration
athlete_id = config['athlete']['id']
api_key = config['athlete']['api_key']

# Intervals.icu API URL
url = f"https://intervals.icu/api/v1/athlete/{athlete_id}"

# Make the API request with basic authentication
response = requests.get(url, auth=HTTPBasicAuth('API_KEY', api_key), headers={'accept': '*/*'})

# Check if the request was successful
if response.status_code == 200:
    # Get the response data
    data = response.json()
    
    # Print the response data to understand its structure
    print(data)
    
    # Extract power zones from configuration
    config_power_zones = config['power_zones']
    
    # Check if power zones are contained in the response
    if 'powerZones' in data:
        api_power_zones = data['powerZones']
        
        # Compare the power zones
        for config_zone in config_power_zones:
            found = False
            for api_zone in api_power_zones:
                if (config_zone['min_watt'] == api_zone['min'] and
                    config_zone['max_watt'] == api_zone['max'] and
                    config_zone['name'] == api_zone['name']):
                    found = True
                    break
            if found:
                print(f"Power zone '{config_zone['name']}' is contained in the response.")
            else:
                print(f"Power zone '{config_zone['name']}' is NOT contained in the response.")
    else:
        print("No power zones found in the response.")
else:
    print(f"Failed to retrieve data: {response.status_code} - {response.text}")