from flask import Blueprint, jsonify
import logging
import os
import requests
from datetime import datetime
import pytz
from pymongo import MongoClient


# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
burgos_bp = Blueprint('burgos', __name__)

# MongoDB connection
try:
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise ValueError("MONGODB_URI environment variable not set")

    client = MongoClient(mongo_uri)
    db = client.meteosarria
    rain_collection = db.burgos_rain_accumulation
    logger.info("Connected to MongoDB")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")
    raise

@burgos_bp.route('/api/burgos-weather', methods=['GET'])
def get_burgos_weather():
    try:
        # Obtener la API key de OpenWeather
        api_key = os.getenv('OPENWEATHER_API_KEY')
        if not api_key:
            logger.error("OPENWEATHER_API_KEY no está configurada")
            return jsonify({"error": "API key no configurada"}), 500

        # Coordenadas de Burgos
        burgos_lat = 42.3500
        burgos_lon = -3.7000

        # Obtener la fecha actual en formato yyyy-mm-dd
        date_str = datetime.now().strftime('%Y-%m-%d')

        # URL para obtener el resumen diario
        day_summary_url = f"https://api.openweathermap.org/data/3.0/onecall/day_summary?lat={burgos_lat}&lon={burgos_lon}&date={date_str}&units=metric&appid={api_key}"

        # URL para obtener los datos actuales
        current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={burgos_lat}&lon={burgos_lon}&units=metric&appid={api_key}&lang=es"

        # Hacer las dos llamadas en paralelo
        day_summary_response = requests.get(day_summary_url)
        current_response = requests.get(current_url)

        # Verificar si las respuestas son exitosas
        day_summary_response.raise_for_status()
        current_response.raise_for_status()

        # Obtener los datos
        day_summary_data = day_summary_response.json()
        current_data = current_response.json()

        # Obtener el último registro de lluvia acumulada
        last_rain_record = rain_collection.find_one(sort=[("date", -1)])
        total_rain = last_rain_record['accumulated'] if last_rain_record else 0

        # Estructurar los datos de respuesta
        weather_data = {
            "temperature": current_data["main"]["temp"],
            "humidity": current_data["main"]["humidity"],
            "pressure": current_data["main"]["pressure"],
            "wind_speed": current_data["wind"]["speed"],
            "wind_direction": current_data["wind"]["deg"],
            "weather_overview": current_data["weather"][0]["description"],
            "day_rain": day_summary_data.get("precipitation", {}).get("total", 0),
            "total_rain": round(total_rain, 1),
            "max_temperature": day_summary_data.get("temperature", {}).get("max", current_data["main"]["temp"]),
            "min_temperature": day_summary_data.get("temperature", {}).get("min", current_data["main"]["temp"]),
            "icon": current_data["weather"][0]["icon"],
            "description": current_data["weather"][0]["description"],
            "timestamp": datetime.now(pytz.UTC).isoformat()
        }

        return jsonify(weather_data)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener datos de OpenWeather: {str(e)}")
        return jsonify({"error": "Error al obtener datos meteorológicos"}), 500
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500 