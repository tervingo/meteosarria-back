from flask import Flask, jsonify, request, Response
from livedata import get_meteohub_parameter
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timedelta
import logging
import os
import pytz
import requests
from typing import Dict, Any, Tuple, Optional
import time
import json
from datetime import timezone
from google.cloud import translate_v2 as translate
import tempfile

app = Flask(__name__)
CORS(app)

# Initialize Google Cloud Translation with credentials from environment variable
credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
if credentials_json:
    # Create a temporary file with the credentials
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(credentials_json)
        temp_credentials_path = f.name
    
    # Set the environment variable to point to the temporary file
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
    translate_client = translate.Client()
else:
    logger.error("Google Cloud credentials not found in environment variables")
    translate_client = None

# Configuración para la API de Burgos Villafría
AEMET_API_KEY = os.getenv('AEMET_API_KEY', "TU_API_KEY_AQUI")
AEMET_BASE_URL = "https://opendata.aemet.es/opendata/api"
BURGOS_STATION_ID = "2331"  # ID de la estación de Burgos/Villafría
BASE_URL = "https://opendata.aemet.es/opendata/api"

# Configuración para la API de AEMET
FABRA_STATION_ID = "0200E"  # ID de la estación del Observatorio Fabra

# Configuración para la API de Meteocat
METEOCAT_API_KEY = os.getenv('METEOCAT_API_KEY', "TU_API_KEY_AQUI")
METEOCAT_BASE_URL = "https://api.meteo.cat/xema/v1"  # Updated base URL
FABRA_METEOCAT_ID = "D5"  # ID de la estación del Observatorio Fabra en Meteocat

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# MongoDB connection
try:
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise ValueError("MONGODB_URI environment variable not set")

    client = MongoClient(mongo_uri)
    db = client.meteosarria
    collection = db.data
    logging.info("Connected to MongoDB")
except Exception as e:
    logging.error(f"Error connecting to MongoDB: {e}")

# Cache for rain data
rain_cache = {
    'last_update': None,
    'data': None,
    'cache_duration': timedelta(hours=1)  # Default to 1 hour cache
}

def clear_rain_cache():
    """Clear the rain cache and log the action"""
    global rain_cache
    rain_cache = {
        'last_update': None,
        'data': None,
        'cache_duration': timedelta(hours=1)
    }
    logger.info("Rain cache cleared")

#-----------------------
# api/live
#-----------------------

@app.route('/api/live')
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
        overview_data = overview_response.json()

        # Translate weather overview to Spanish using Google Cloud Translation
        weather_overview = overview_data.get('weather_overview', '')
        if weather_overview:
            try:
                if translate_client:
                    # Translate using Google Cloud Translation
                    result = translate_client.translate(
                        weather_overview,
                        target_language='es',
                        source_language='en'
                    )
                    translated_overview = result['translatedText']
                    logger.info(f"Translated weather overview: {translated_overview}")
                else:
                    # Fallback to OpenWeather description if translation is not available
                    translated_overview = owm_data['weather'][0]['description']
                    logger.warning("Translation service not available, using OpenWeather description")
            except Exception as e:
                logger.error(f"Error translating weather overview: {e}")
                translated_overview = weather_overview
        else:
            translated_overview = owm_data['weather'][0]['description']
 
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
            'resumen': translated_overview,
            'description': owm_data['weather'][0]['description'],
            "icon": owm_data['weather'][0]['icon']
        }

        if any(value is None for value in live_data.values()):
            return jsonify({"error": "Could not retrieve complete live weather data"}), 500

        return jsonify(live_data)
    except Exception as e:
        logging.error(f"Error in live_weather endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500


#-----------------------
# api/meteo-data AP
#-----------------------

@app.route('/api/meteo-data')
def temperature_data():
    try:
        logging.info("meteo-data endpoint called")
        time_range = request.args.get('timeRange', '24h')
        end_time = datetime.now(pytz.timezone('Europe/Madrid'))
        
        if time_range == '24h':
            start_time = end_time - timedelta(hours=24)
            interval = 1
        elif time_range == '48h':
            start_time = end_time - timedelta(hours=48)
            interval = 2
        elif time_range == '7d':
            start_time = end_time - timedelta(days=7)
            interval = 6
        else:
            return jsonify({"error": "Invalid time range"}), 400

        # Obtener los días a consultar
        days_to_query = []
        current_day = start_time
        while current_day <= end_time:
            day_str = current_day.strftime("%d-%m-%Y")
            days_to_query.append(day_str)
            current_day += timedelta(days=1)

        logging.info(f"Días a consultar: {days_to_query}")

        # Construir consulta para obtener documentos por día
        query = {
            "$or": [
                {"timestamp": {"$regex": f"^{day}"}} for day in days_to_query
            ]
        }
        
        logging.info(f"Query: {query}")
        
        # Obtener documentos
        all_data = list(collection.find(query).sort("timestamp", 1))
        logging.info(f"Documentos encontrados antes de filtrar por hora: {len(all_data)}")
        
        if all_data:
            logging.info(f"Primer documento: {all_data[0]['timestamp']}")
            logging.info(f"Último documento: {all_data[-1]['timestamp']}")

        # Función para convertir timestamp string a datetime
        def parse_timestamp(ts):
            return datetime.strptime(ts, "%d-%m-%Y %H:%M")

        # Convertir las fechas límite a datetime
        start_dt = parse_timestamp(start_time.strftime("%d-%m-%Y %H:%M"))
        end_dt = parse_timestamp(end_time.strftime("%d-%m-%Y %H:%M"))
        
        # Filtrar los datos usando objetos datetime para la comparación
        filtered_data = [
            doc for doc in all_data 
            if start_dt <= parse_timestamp(doc['timestamp']) <= end_dt
        ]
        
        logging.info(f"Documentos después de filtrar por hora: {len(filtered_data)}")
        if filtered_data:
            logging.info(f"Primer documento filtrado: {filtered_data[0]['timestamp']}")
            logging.info(f"Último documento filtrado: {filtered_data[-1]['timestamp']}")
            logging.info(f"Hora inicio filtro: {start_dt}")
            logging.info(f"Hora fin filtro: {end_dt}")

        # Aplicar sampling
        sampled_data = filtered_data[::interval]
        
        # Preparar para JSON
        for entry in sampled_data:
            entry["_id"] = str(entry["_id"])
        
        return jsonify(sampled_data)
        
    except Exception as e:
        logging.error(f"Error fetching meteo data: {e}", exc_info=True)
        logging.error("Error detallado:", exc_info=True)
        return jsonify({"error": str(e)}), 500

#-----------------------
# api/yearly-data
#-----------------------

@app.route('/api/yearly-data')
def yearly_temperature_data():
    try:
        logging.info("yearly-data endpoint called")
        
        # Definir zona horaria
        madrid_tz = pytz.timezone('Europe/Madrid')
        
        # Obtener el año actual y crear fechas con zona horaria
        now = datetime.now(madrid_tz)
        current_year = now.year
        
        # Crear start_date con zona horaria
        start_date = madrid_tz.localize(datetime(current_year, 1, 1))
        end_date = now

        logging.info(f"Consultando datos desde {start_date.strftime('%d-%m-%Y')} hasta {end_date.strftime('%d-%m-%Y')}")

        # Obtener los días a consultar
        days_to_query = []
        current_day = start_date
        while current_day <= end_date:
            day_str = current_day.strftime("%d-%m-%Y")
            days_to_query.append(day_str)
            current_day += timedelta(days=1)

        # Construir consulta para obtener documentos por día
        query = {
            "$or": [
                {"timestamp": {"$regex": f"^{day}"}} for day in days_to_query
            ]
        }
        
        logging.info(f"Consultando {len(days_to_query)} días")
        
        # Obtener documentos
        all_data = list(collection.find(query).sort("timestamp", 1))
        logging.info(f"Encontrados {len(all_data)} registros")
        
        # Procesar datos para obtener máximas, mínimas y medias por día
        daily_data = {}
        
        for entry in all_data:
            try:
                # Parsear timestamp y convertir a zona horaria de Madrid
                timestamp = datetime.strptime(entry['timestamp'], "%d-%m-%Y %H:%M")
                timestamp = madrid_tz.localize(timestamp)
                date_key = timestamp.strftime("%Y-%m-%d")
                
                if date_key not in daily_data:
                    daily_data[date_key] = {
                        'temps': [],
                        'date': date_key
                    }
                
                if 'external_temperature' in entry and entry['external_temperature'] is not None:
                    temp = float(entry['external_temperature'])
                    # Filtrar valores atípicos (opcional)
                    if -40 <= temp <= 50:  # Rango razonable de temperaturas
                        daily_data[date_key]['temps'].append(temp)
                
            except (ValueError, TypeError) as e:
                logging.warning(f"Error procesando entrada {entry['timestamp']}: {str(e)}")
                continue

        # Calcular estadísticas diarias
        processed_data = []
        for date_key, data in daily_data.items():
            if data['temps']:
                temps = data['temps']
                processed_data.append({
                    'date': date_key,
                    'max': round(max(temps), 1),
                    'min': round(min(temps), 1),
                    'mean': round(sum(temps) / len(temps), 1)
                })

        # Ordenar por fecha
        processed_data.sort(key=lambda x: x['date'])
        
        logging.info(f"Procesados datos para {len(processed_data)} días")
        
        return jsonify({
            'status': 'success',
            'data': processed_data
        })
        
    except Exception as e:
        logging.error(f"Error fetching yearly data: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

#-----------------------
# api/burgos (AEMET Villafría)
#-----------------------

class AEMETError(Exception):
    """Excepción personalizada para errores de la API de AEMET"""
    pass

def get_aemet_data(endpoint: str) -> Tuple[Dict[str, Any], int]:
    """
    Realiza una petición a la API de AEMET
    """
    headers = {
        'api_key': AEMET_API_KEY,
        'Accept': 'application/json'
    }
    
    try:
        logger.debug(f"Realizando petición a AEMET: {BASE_URL}/{endpoint}")
        # Primera petición para obtener la URL de los datos
        response = requests.get(f"{BASE_URL}/{endpoint}", headers=headers)
        response.raise_for_status()
        
        data = response.json()
        logger.debug(f"Respuesta inicial de AEMET: {data}")
        
        data_url = data.get('datos')
        if not data_url:
            logger.error("No se encontró URL de datos en la respuesta")
            raise AEMETError("No se obtuvo URL de datos en la respuesta")
            
        # Segunda petición para obtener los datos reales
        logger.debug(f"Obteniendo datos de: {data_url}")
        data_response = requests.get(data_url)
        data_response.raise_for_status()
        
        return data_response.json(), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en la petición HTTP: {str(e)}")
        raise AEMETError(f"Error en la petición HTTP: {str(e)}")
    except ValueError as e:
        logger.error(f"Error al procesar JSON: {str(e)}")
        raise AEMETError(f"Error al procesar JSON: {str(e)}")

# OpenWeatherMap API endpoint for Burgos
@app.route('/api/burgos-weather')
def get_burgos_weather():
    try:
        OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
        if not OPENWEATHER_API_KEY:
            logger.error("OpenWeather API key not found in environment variables")
            return jsonify({'error': 'API key not configured'}), 500

        BURGOS_LAT = 42.3439
        BURGOS_LON = -3.6970
        
        url = f'https://api.openweathermap.org/data/2.5/weather?lat={BURGOS_LAT}&lon={BURGOS_LON}&units=metric&appid={OPENWEATHER_API_KEY}&lang=es'
        
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

                # Get weather overview
        overview_url = f'https://api.openweathermap.org/data/3.0/onecall/overview?lon={BURGOS_LON}&lat={BURGOS_LAT}&units=metric&appid={OPENWEATHER_API_KEY}'
        overview_response = requests.get(overview_url)
        overview_response.raise_for_status()
        overview_data = overview_response.json()

        # Translate weather overview to Spanish using Google Cloud Translation
        weather_overview = overview_data.get('weather_overview', '')
        if weather_overview:
            try:
                if translate_client:
                    # Translate using Google Cloud Translation
                    result = translate_client.translate(
                        weather_overview,
                        target_language='es',
                        source_language='en'
                    )
                    translated_overview = result['translatedText']
                    logger.info(f"Translated weather overview: {translated_overview}")
                else:
                    # Fallback to OpenWeather description if translation is not available
                    translated_overview = owm_data['weather'][0]['description']
                    logger.warning("Translation service not available, using OpenWeather description")
            except Exception as e:
                logger.error(f"Error translating weather overview: {e}")
                translated_overview = weather_overview
        else:
            translated_overview = owm_data['weather'][0]['description']

        weather_data = {
            'temperature': data['main']['temp'],
            'humidity': data['main']['humidity'],
            'pressure': data['main']['pressure'],
            'windSpeed': data['wind']['speed'] * 3.6,  # Convert m/s to km/h
            'windDirection': data['wind']['deg'],
            'description': data['weather'][0]['description'],
            'icon': data['weather'][0]['icon'],
            'resumen': translated_overview,
            'timestamp': data['dt']
        }

        logger.debug(f"Successfully fetched Burgos weather data: {weather_data}")
        return jsonify(weather_data)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Burgos weather data: {str(e)}")
        return jsonify({'error': 'Failed to fetch weather data'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_burgos_weather: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

#---------------------------
# Debug
#---------------------------

@app.route('/api/debug/last-records')
def debug_last_records():
    try:
        # Obtener los últimos 5 registros
        last_records = list(collection.find().sort("timestamp", -1).limit(5))
        
        # Convertir ObjectId a string
        for record in last_records:
            record["_id"] = str(record["_id"])
            
        return jsonify({
            "count": len(last_records),
            "records": last_records
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/barcelona-rain')
def get_barcelona_rain():
    try:
        logger.info("************ barcelona-rain endpoint called ************")
        
        # Get current time in Madrid timezone
        now = datetime.now(pytz.timezone('Europe/Madrid'))

        # First check if it's raining using OpenWeather's current weather
        OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
        if not OPENWEATHER_API_KEY:
            error_msg = "OpenWeatherMap API key not configured"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500

        BARCELONA_LAT = 41.389
        BARCELONA_LON = 2.159
        current_url = f'https://api.openweathermap.org/data/3.0/onecall?lat={BARCELONA_LAT}&lon={BARCELONA_LON}&appid={OPENWEATHER_API_KEY}&exclude=minutely,daily,alerts&units=metric'
        
        try:
            response = requests.get(current_url)
            response.raise_for_status()
            current_data = response.json()
            
            # Check if it's raining in the current hour
            current_hour_rain = current_data.get('hourly', [{}])[0].get('rain', {}).get('1h', 0)
            is_raining = current_hour_rain > 0
            logger.info(f"OpenWeather reports rain in current hour: {current_hour_rain}mm")
            
            # Get today's total rain from hourly data
            today_rain = sum(hour.get('rain', {}).get('1h', 0) for hour in current_data.get('hourly', []))
            logger.info(f"OpenWeather reports total rain today: {today_rain}mm")
            
        except Exception as e:
            logger.error(f"Error getting current weather data: {e}")
            is_raining = False
            today_rain = 0

        # Get last accumulation record from MongoDB
        last_record = db.rain_accumulation.find_one(sort=[("date", -1)])
        if not last_record:
            error_msg = "No rain accumulation data found in database"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500

        accumulated_rain = last_record['accumulated']
        logger.info(f"Found accumulated rain until {last_record['date']}: {accumulated_rain:.2f}mm")

        # Check if we need to update Meteocat data
        need_meteocat_update = (
            is_raining or  # It's raining
            not rain_cache['data'] or  # No cache data
            (rain_cache['data'] and rain_cache['data'].get('station_name') == 'OpenWeatherMap Barcelona') or  # Currently using OpenWeather
            (rain_cache['last_update'] and rain_cache['last_update'].date() < now.date())  # Cache is from a previous day
        )

        if need_meteocat_update:
            logger.info("Updating Meteocat data because: " + 
                       ("it's raining" if is_raining else "") +
                       ("no cache data" if not rain_cache['data'] else "") +
                       ("using OpenWeather" if rain_cache['data'] and rain_cache['data'].get('station_name') == 'OpenWeatherMap Barcelona' else "") +
                       ("cache from previous day" if rain_cache['last_update'] and rain_cache['last_update'].date() < now.date() else ""))
            
            try:
                # Get Meteocat API key
                METEOCAT_API_KEY = os.getenv('METEOCAT_API_KEY')
                if not METEOCAT_API_KEY:
                    raise ValueError("Meteocat API key not configured")

                # Format date components for Meteocat URL
                month = str(now.month).zfill(2)
                day = str(now.day).zfill(2)
                year = now.year
                
                meteocat_url = f'https://api.meteo.cat/xema/v1/variables/mesurades/35/{year}/{month}/{day}?codiEstacio=D5'
                
                headers = {
                    'Content-Type': 'application/json',
                    'X-Api-Key': METEOCAT_API_KEY
                }
                
                logger.info(f"Making Meteocat API call to: {meteocat_url}")
                response = requests.get(meteocat_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                # Pretty print the response for debugging
                logger.info("Meteocat API Response:")
                logger.info(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Process data
                if not data or 'lectures' not in data:
                    logger.error("No data or 'lectures' key not found in response")
                    return None
                
                # Sum all precipitation values for each half-hour interval
                current_rain = 0.0
                for lecture in data.get('lectures', []):
                    if lecture.get('estat') in ['V', ' ']:  # Count both valid and empty state measurements
                        current_rain += float(lecture.get('valor', 0))
                
                logger.info(f"Meteocat reports today's rain: {current_rain:.2f}mm")
                using_meteocat = True
            except Exception as e:
                logger.error(f"Error getting Meteocat data: {e}")
                # If Meteocat fails, use OpenWeather data we already have
                current_rain = today_rain
                using_meteocat = False
                logger.info(f"Falling back to OpenWeather data: {current_rain:.2f}mm")
        else:
            # If not raining and we have Meteocat data, use cached data
            current_rain = rain_cache['data'].get('today_rain', 0)
            using_meteocat = rain_cache['data'].get('station_name') == 'Meteocat Fabra Observatory'
            logger.info(f"Using cached {'Meteocat' if using_meteocat else 'OpenWeather'} data: {current_rain:.2f}mm")

        # Calculate total rain
        total_rain = accumulated_rain + current_rain

        response_data = {
            'yearly_rain': round(total_rain, 1),
            'today_rain': round(current_rain, 1),
            'accumulated_until_yesterday': round(accumulated_rain, 1),
            'station_name': 'Meteocat Fabra Observatory' if using_meteocat else 'OpenWeatherMap Barcelona',
            'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
            'last_available_date': last_record['date']
        }
        
        # Update cache with dynamic duration
        rain_cache['data'] = response_data
        rain_cache['last_update'] = now
        # If it's raining, cache for 20 minutes, otherwise for 1 hour
        rain_cache['cache_duration'] = timedelta(minutes=20) if is_raining else timedelta(hours=1)
        
        logger.info(f"Updated cache with new rain data. Cache duration: {rain_cache['cache_duration']}")
        return jsonify(response_data)
        
    except Exception as e:
        error_msg = f"Unexpected error in get_barcelona_rain: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return jsonify({'error': error_msg}), 500

@app.route('/api/barcelona-rain/clear-cache', methods=['POST'])
def clear_barcelona_rain_cache():
    try:
        clear_rain_cache()
        return jsonify({
            'status': 'success',
            'message': 'Rain cache cleared successfully'
        })
    except Exception as e:
        error_msg = f"Error clearing rain cache: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return jsonify({'error': error_msg}), 500

def convert_spanish_decimal(value: str) -> float:
    """Convierte un número en formato español (con coma decimal) a float."""
    try:
        if value is None:
            return 0.0
        # Reemplazar coma por punto y convertir a float
        return float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0
    
# URL de ejemplo para pruebas (imagen de radar peninsular de muestra)
SAMPLE_RADAR_URL = "https://www.aemet.es/imagenes_d/eltiempo/observacion/radar/r8pen_202403310100.jpg"

DEVELOPMENT_MODE = True

@app.route('/api/radar/peninsula', methods=['GET'])
def obtener_radar_peninsula():
    """
    Obtiene datos del radar meteorológico de la Península de AEMET.
    
    :return: JSON con la URL de la imagen del radar y metadatos
    """
    # En modo desarrollo sin API key, devolver una URL de muestra
    if DEVELOPMENT_MODE and not AEMET_API_KEY:
        logger.info("Usando URL de radar de muestra para desarrollo")
        return jsonify({
            'tipo': 'imagen',
            'formato': 'image/jpeg',
            'url': SAMPLE_RADAR_URL,
            'timestamp': datetime.now().isoformat(),
            'mode': 'development_sample'
        })
    
    # Utilizamos el radar regional para la península
    endpoint = f"{AEMET_BASE_URL}/red/radar/regional/pe"
    
    try:
        # Realizar petición a la API de AEMET
        params = {'api_key': AEMET_API_KEY}
        response = requests.get(endpoint, params=params)
        
        # Comprobar si la petición fue exitosa
        if response.status_code != 200:
            logger.error(f"Error en la petición a AEMET: {response.status_code}, {response.text}")
            return jsonify({
                'error': 'Error al obtener datos del radar',
                'status': response.status_code
            }), response.status_code
        
        # La API de AEMET devuelve una URL donde se encuentran los datos reales
        data = response.json()
        
        # Verificar si AEMET devolvió un error interno (puede devolver 200 pero con error)
        if 'estado' in data and data['estado'] != 200:
            error_msg = data.get('descripcion', 'Error desconocido en la API de AEMET')
            logger.error(f"Error interno de AEMET: {error_msg}")
            
            # Si estamos en modo desarrollo, usar la imagen de muestra
            if DEVELOPMENT_MODE:
                logger.info("Usando URL de radar de muestra debido a error de AEMET")
                return jsonify({
                    'tipo': 'imagen',
                    'formato': 'image/jpeg',
                    'url': SAMPLE_RADAR_URL,
                    'timestamp': datetime.now().isoformat(),
                    'mode': 'development_sample_fallback',
                    'aemet_error': error_msg
                })
            
            return jsonify({
                'error': f'Error de AEMET: {error_msg}',
                'status': data.get('estado', 500)
            }), 500
        
        if 'datos' not in data:
            logger.error(f"Respuesta inesperada de AEMET: {data}")
            
            # Si estamos en modo desarrollo, usar la imagen de muestra
            if DEVELOPMENT_MODE:
                logger.info("Usando URL de radar de muestra debido a formato inesperado")
                return jsonify({
                    'tipo': 'imagen',
                    'formato': 'image/jpeg',
                    'url': SAMPLE_RADAR_URL,
                    'timestamp': datetime.now().isoformat(),
                    'mode': 'development_sample_fallback'
                })
                
            return jsonify({'error': 'Formato de respuesta inesperado'}), 500
        
        # Obtener los datos reales (normalmente una imagen o un JSON con la URL de la imagen)
        try:
            datos_response = requests.get(data['datos'], timeout=10)  # Añadir timeout
            
            if datos_response.status_code != 200:
                logger.error(f"Error al obtener datos de la URL proporcionada: {datos_response.status_code}")
                
                # Si estamos en modo desarrollo, usar la imagen de muestra
                if DEVELOPMENT_MODE:
                    logger.info("Usando URL de radar de muestra debido a error en datos")
                    return jsonify({
                        'tipo': 'imagen',
                        'formato': 'image/jpeg',
                        'url': SAMPLE_RADAR_URL,
                        'timestamp': datetime.now().isoformat(),
                        'mode': 'development_sample_fallback'
                    })
                    
                return jsonify({'error': 'Error al obtener la imagen del radar'}), datos_response.status_code
            
            # Si la respuesta es una imagen directamente
            if 'image' in datos_response.headers.get('Content-Type', ''):
                # En una implementación real, podrías almacenar esta imagen temporalmente
                # y devolver su URL, o convertirla a base64
                return jsonify({
                    'tipo': 'imagen',
                    'formato': datos_response.headers.get('Content-Type'),
                    'url': data['datos'],  # URL directa para que el frontend la use
                    'timestamp': datetime.now().isoformat()
                })
            
            # Si la respuesta es JSON con metadatos
            try:
                metadatos = datos_response.json()
                return jsonify({
                    'tipo': 'json',
                    'datos': metadatos,
                    'timestamp': datetime.now().isoformat()
                })
            except:
                # Si no es JSON ni una imagen reconocible, devolvemos la URL directa
                return jsonify({
                    'tipo': 'desconocido',
                    'url': data['datos'],
                    'timestamp': datetime.now().isoformat()
                })
                
        except requests.RequestException as e:
            logger.exception(f"Error al obtener datos de la URL {data.get('datos')}: {str(e)}")
            
            # Si estamos en modo desarrollo, usar la imagen de muestra
            if DEVELOPMENT_MODE:
                logger.info("Usando URL de radar de muestra debido a error de conexión")
                return jsonify({
                    'tipo': 'imagen',
                    'formato': 'image/jpeg',
                    'url': SAMPLE_RADAR_URL,
                    'timestamp': datetime.now().isoformat(),
                    'mode': 'development_sample_fallback'
                })
                
            return jsonify({'error': f'Error al acceder a los datos: {str(e)}'}), 500
            
    except requests.RequestException as e:
        logger.exception("Error en la conexión con la API de AEMET")
        return jsonify({'error': f'Error de conexión: {str(e)}'}), 500
    except Exception as e:
        logger.exception("Error inesperado")
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500
    
    try:
        # Realizar petición a la API de AEMET
        params = {'api_key': AEMET_API_KEY}
        response = requests.get(endpoint, params=params)
        
        # Comprobar si la petición fue exitosa
        if response.status_code != 200:
            logger.error(f"Error en la petición a AEMET: {response.status_code}, {response.text}")
            return jsonify({
                'error': 'Error al obtener datos del radar',
                'status': response.status_code
            }), response.status_code
        
        # La API de AEMET devuelve una URL donde se encuentran los datos reales
        data = response.json()
        
        if 'datos' not in data:
            logger.error(f"Respuesta inesperada de AEMET: {data}")
            return jsonify({'error': 'Formato de respuesta inesperado'}), 500
        
        # Obtener los datos reales (normalmente una imagen o un JSON con la URL de la imagen)
        datos_response = requests.get(data['datos'])
        
        if datos_response.status_code != 200:
            logger.error(f"Error al obtener datos de la URL proporcionada: {datos_response.status_code}")
            return jsonify({'error': 'Error al obtener la imagen del radar'}), datos_response.status_code
        
        # Si la respuesta es una imagen directamente
        if 'image' in datos_response.headers.get('Content-Type', ''):
            # En una implementación real, podrías almacenar esta imagen temporalmente
            # y devolver su URL, o convertirla a base64
            return jsonify({
                'tipo': 'imagen',
                'formato': datos_response.headers.get('Content-Type'),
                'url': data['datos'],  # URL directa para que el frontend la use
                'timestamp': datetime.now().isoformat()
            })
        
        # Si la respuesta es JSON con metadatos
        try:
            metadatos = datos_response.json()
            return jsonify({
                'tipo': 'json',
                'datos': metadatos,
                'timestamp': datetime.now().isoformat()
            })
        except:
            # Si no es JSON ni una imagen reconocible, devolvemos la URL directa
            return jsonify({
                'tipo': 'desconocido',
                'url': data['datos'],
                'timestamp': datetime.now().isoformat()
            })
            
    except requests.RequestException as e:
        logger.exception("Error en la conexión con la API de AEMET")
        return jsonify({'error': f'Error de conexión: {str(e)}'}), 500
    except Exception as e:
        logger.exception("Error inesperado")
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500


@app.route('/api/radar/estado', methods=['GET'])
def verificar_estado():
    """
    Verifica la conectividad con la API de AEMET
    """
    try:
        response = requests.get(f"{AEMET_BASE_URL}/red/radar/nacional", 
                               params={'api_key': AEMET_API_KEY})
        
        if response.status_code == 200:
            return jsonify({
                'estado': 'OK',
                'mensaje': 'Conexión con AEMET establecida correctamente',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'estado': 'ERROR',
                'mensaje': f'Error de conexión con AEMET: {response.status_code}',
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        return jsonify({
            'estado': 'ERROR',
            'mensaje': f'Error al verificar estado: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)