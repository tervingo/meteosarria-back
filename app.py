from flask import Flask, jsonify, request, Response
from flask_cors import CORS
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

# Import blueprints and database
from api_live import live_bp
from api_meteo_data import meteo_bp
from api_yearly_data import yearly_bp
from api_burgos_weather import burgos_bp
from database import collection, db

app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(live_bp)
app.register_blueprint(meteo_bp)
app.register_blueprint(yearly_bp)
app.register_blueprint(burgos_bp)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
                    # Fall back to OpenWeather data we already have
                    current_rain = today_rain
                    using_meteocat = False
                    logger.info(f"Falling back to OpenWeather data: {current_rain:.2f}mm")
                else:
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
    endpoint = f"{AEMET_BASE_URL}/red/radar/nacional"
    
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