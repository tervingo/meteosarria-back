from flask import Blueprint, jsonify
from flask_cors import CORS
import logging
import os
import pytz
from datetime import datetime
import requests
from livedata import get_meteohub_parameter
from database import collection  # Import collection from database module

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
live_bp = Blueprint('live', __name__)

# Enable CORS for the blueprint
CORS(live_bp, resources={
    r"/api/*": {
        "origins": [
            "https://meteosarria.com",
            "http://localhost:3000",
            "http://127.0.0.1:3000"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

@live_bp.route('/api/live')
def live_weather():
    try:
        # Get current date in Madrid timezone
        madrid_tz = pytz.timezone('Europe/Madrid')
        now = datetime.now(madrid_tz)
        today = now.strftime("%d-%m-%Y")
        
        # Get today's temperature records
        today_records = list(collection.find({
            "timestamp": {"$regex": f"^{today}"}
        }).sort("timestamp", 1))
        
        # Calculate min and max temperatures for today
        today_temps = [float(record['external_temperature']) 
                      for record in today_records 
                      if 'external_temperature' in record 
                      and record['external_temperature'] is not None]
        
        max_temp = round(max(today_temps), 1) if today_temps else None
        min_temp = round(min(today_temps), 1) if today_temps else None

        BCN_LAT = 41.389
        BCN_LON = 2.159
        # First check if it's raining using OpenWeather's current weather
        OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
        if not OPENWEATHER_API_KEY:
            error_msg = "OpenWeatherMap API key not configured"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500
        
        # Get current weather data
        owm_url = f'https://api.openweathermap.org/data/2.5/weather?lat={BCN_LAT}&lon={BCN_LON}&units=metric&appid={OPENWEATHER_API_KEY}&lang=es'
        response = requests.get(owm_url)
        response.raise_for_status()
        owm_data = response.json()

        # Get weather overview
        overview_url = f'https://api.openweathermap.org/data/3.0/onecall/overview?lon={BCN_LON}&lat={BCN_LAT}&units=metric&appid={OPENWEATHER_API_KEY}'
        overview_response = requests.get(overview_url)
        overview_response.raise_for_status()
 
        live_data = {
            "external_temperature": get_meteohub_parameter("ext_temp"),
            "max_temperature": max_temp,
            "min_temperature": min_temp,
            "internal_temperature": get_meteohub_parameter("int_temp"),
            "humidity": get_meteohub_parameter("hum"),
            "wind_direction": get_meteohub_parameter("wind_dir"),
            "wind_speed": get_meteohub_parameter("wind_speed"),
            "gust_speed": get_meteohub_parameter("gust_speed"),
            "pressure": get_meteohub_parameter("sea_press"),
            "current_rain_rate": get_meteohub_parameter("cur_rain"),
            "total_rain": get_meteohub_parameter("total_rain"),
            "solar_radiation": get_meteohub_parameter("rad"),
            "uv_index": get_meteohub_parameter("uv"),
            'description': owm_data['weather'][0]['description'],
            "icon": owm_data['weather'][0]['icon']
        }

        if any(value is None for value in live_data.values()):
            return jsonify({"error": "Could not retrieve complete live weather data"}), 500

        return jsonify(live_data)
    except Exception as e:
        logging.error(f"Error in live_weather endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500 