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

        # URL para obtener el resumen diario (si está disponible)
        day_summary_url = f"https://api.openweathermap.org/data/3.0/onecall/day_summary?lat={burgos_lat}&lon={burgos_lon}&date={date_str}&units=metric&appid={api_key}"

        # URL para obtener los datos actuales
        current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={burgos_lat}&lon={burgos_lon}&units=metric&appid={api_key}&lang=es"
        
        # URL para obtener el pronóstico de 5 días (con datos cada 3 horas)
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={burgos_lat}&lon={burgos_lon}&units=metric&appid={api_key}"

        # Hacer las llamadas a las APIs disponibles
        current_response = requests.get(current_url)
        current_response.raise_for_status()
        current_data = current_response.json()
        
        forecast_response = requests.get(forecast_url)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        
        # Intentar obtener datos del resumen diario si está disponible
        day_summary_data = {}
        try:
            day_summary_response = requests.get(day_summary_url)
            if day_summary_response.status_code == 200:
                day_summary_data = day_summary_response.json()
        except Exception as e:
            logger.warning(f"No se pudo obtener el resumen diario: {e}")

        # Calcular la precipitación del día actual usando datos disponibles
        day_rain = calculate_day_rain_from_forecast(forecast_data)
        
        # Si hay datos de lluvia actuales, añadirlos al total
        if 'rain' in current_data and '1h' in current_data['rain']:
            current_rain = current_data['rain']['1h']
            logger.debug(f"Lluvia actual: {current_rain} mm")
            # Solo sumar si no está ya incluida en los datos de pronóstico
            if not is_current_hour_in_forecast(forecast_data):
                day_rain += current_rain

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
            "day_rain": round(day_rain, 1),  # Usar el valor calculado
            "total_rain": round(total_rain, 1),
            "max_temperature": day_summary_data.get("temperature", {}).get("max", current_data["main"]["temp_max"]),
            "min_temperature": day_summary_data.get("temperature", {}).get("min", current_data["main"]["temp_min"]),
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

def calculate_day_rain_from_forecast(forecast_data):
    """
    Calcula la precipitación total del día actual (desde las 00:00 hasta ahora)
    basado en los datos del pronóstico de 5 días de OpenWeatherMap.
    """
    try:
        total_precipitation = 0
        today = datetime.now(pytz.UTC).date()
        current_time = datetime.now(pytz.UTC)
        
        # Recorrer datos del pronóstico
        for forecast in forecast_data.get('list', []):
            forecast_time = datetime.fromtimestamp(forecast.get('dt', 0), pytz.UTC)
            
            # Solo procesar datos de hoy hasta la hora actual
            if forecast_time.date() == today and forecast_time <= current_time:
                # La precipitación se guarda en 'rain.3h' si existe
                rain_data = forecast.get('rain', {})
                precipitation = rain_data.get('3h', 0) if isinstance(rain_data, dict) else 0
                total_precipitation += precipitation
                logger.debug(f"Precipitación {forecast_time}: {precipitation} mm")
        
        logger.debug(f"Precipitación calculada hoy desde pronóstico: {total_precipitation} mm")
        return total_precipitation
        
    except Exception as e:
        logger.error(f"Error al calcular la precipitación diaria: {str(e)}")
        return 0

def is_current_hour_in_forecast(forecast_data):
    """
    Verifica si la hora actual está incluida en los datos de pronóstico.
    """
    current_hour = datetime.now(pytz.UTC).replace(minute=0, second=0, microsecond=0)
    current_timestamp = int(current_hour.timestamp())
    
    # Buscar en los datos de pronóstico
    for forecast in forecast_data.get('list', []):
        if forecast.get('dt') == current_timestamp:
            return True
    
    return False