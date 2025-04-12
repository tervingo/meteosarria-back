from flask import Blueprint, jsonify
import logging
import os
import requests
from datetime import datetime
import pytz


# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
burgos_bp = Blueprint('burgos', __name__)


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
        current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={burgos_lat}&lon={burgos_lon}&units=metric&appid={api_key}"

        # Hacer las dos llamadas en paralelo
        day_summary_response = requests.get(day_summary_url)
        current_response = requests.get(current_url)

        # Verificar si las respuestas son exitosas
        day_summary_response.raise_for_status()
        current_response.raise_for_status()

        # Obtener los datos
        day_summary_data = day_summary_response.json()
        current_data = current_response.json()

        # Estructurar los datos de respuesta
        weather_data = {
            "temperature": current_data["main"]["temp"],
            "humidity": current_data["main"]["humidity"],
            "pressure": current_data["main"]["pressure"],
            "wind_speed": current_data["wind"]["speed"],
            "wind_direction": current_data["wind"]["deg"],
            "weather_overview": current_data["weather"][0]["description"],
            "day_rain": day_summary_data.get("precipitation", {}).get("total", 0),
            "max_temperature": day_summary_data.get("temperature", {}).get("max", current_data["main"]["temp"]),
            "min_temperature": day_summary_data.get("temperature", {}).get("min", current_data["main"]["temp"]),
            "timestamp": datetime.now(pytz.UTC).isoformat()
        }

        return jsonify(weather_data)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener datos de OpenWeather: {str(e)}")
        return jsonify({"error": "Error al obtener datos meteorológicos"}), 500
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500 