import logging
import os
from datetime import datetime
from livedata import get_meteohub_parameter
import pytz
import json
from database import get_collection

# Configure logging
logging.basicConfig(level=logging.INFO)

def log_weather_data():
    try:
        logging.info("Fetching weather data...")
        live_data = {
            "external_temperature": get_meteohub_parameter("ext_temp"),
            "internal_temperature": get_meteohub_parameter("int_temp"),
            "humidity": get_meteohub_parameter("hum"),
            "pressure": get_meteohub_parameter("sea_press"),
            "wind_speed": get_meteohub_parameter("wind_speed"),
            "wind_direction": get_meteohub_parameter("wind_dir"),
            "current_rain_rate": get_meteohub_parameter("cur_rain"),
            "total_rain": get_meteohub_parameter("total_rain"),
            "solar_radiation": get_meteohub_parameter("rad"),
            "timestamp": datetime.now(pytz.timezone('Europe/Madrid')).strftime("%d-%m-%Y %H:%M")
        }

        if any(value is None for value in live_data.values()):
            logging.warning("Could not retrieve complete live weather data")
            return

        get_collection().insert_one(live_data)
        logging.info(f"Logged weather data: {live_data}")
    except Exception as e:
        logging.error(f"Error logging weather data: {e}")

if __name__ == '__main__':
    log_weather_data()