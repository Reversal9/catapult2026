import requests

def get_solar_climate_data(lat, long, date):

    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={long}&start_date={date}&end_date={date}&hourly=rain,showers,snowfall,temperature_2m,relative_humidity_2m,cloud_cover,cloud_cover_low,cloud_cover_high,cloud_cover_mid,shortwave_radiation,direct_radiation,diffuse_radiation,global_tilted_irradiance"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data["hourly"]
    else:
        print(f"Error {response.status_code}: {response.text}")

def get_wind_climate_data(lat, long, data):
    
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={long}&start_date={date}&end_date={date}&hourly=rain,showers,snowfall,temperature_2m,relative_humidity_2m,wind_speed_10m,wind_speed_80m,wind_gusts_10m,wind_direction_10m,wind_direction_80m"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data["hourly"]
    else:
        print(f"Error {response.status_code}: {response.text}")