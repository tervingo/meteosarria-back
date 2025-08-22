from flask import Blueprint, jsonify
import logging
import os
import requests
from datetime import datetime
import threading
import time
from database import get_db

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
weather_comparison_bp = Blueprint('weather_comparison', __name__)

# Weather API configuration
GOOGLE_WEATHER_API_KEY = os.getenv('GOOGLE_WEATHER_API_KEY')
VILLAFRIA_LAT = 42.36542
VILLAFRIA_LON = -3.61669
BURGOS_CENTER_LAT = 42.34106
BURGOS_CENTER_LON = -3.70184
SARRIA_LAT = 41.39525993208715
SARRIA_LON = 2.12245595765206

# Database collections
try:
    db = get_db()
    weather_collection = db.gw_burgos_data
    logger.info("Connected to gw_burgos_data collection")
except Exception as e:
    logger.error(f"Error connecting to gw_burgos_data collection: {e}")
    raise

# Weather data functions
def get_aemet_data():
    """Get weather data from AEMET for Villafría station"""
    try:
        # AEMET API endpoint for Villafría station (2331 is Burgos/Villafría)
        url = "https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/2331"
        api_key = os.getenv('AEMET_API_KEY')
        
        if not api_key:
            logger.warning("AEMET_API_KEY not configured")
            return None
            
        # AEMET uses query parameters for API key
        params = {'api_key': api_key}
        
        logger.info(f"Making AEMET API request to: {url}")
        logger.info(f"AEMET API params: {params}")
        
        # First request - get the data URL
        response = requests.get(url, params=params, timeout=10)
        
        logger.info(f"AEMET API response status: {response.status_code}")
        logger.info(f"AEMET API response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                metadata = response.json()
                logger.info(f"AEMET API metadata: {metadata}")
                
                # AEMET returns metadata with a 'datos' URL
                if 'datos' in metadata:
                    datos_url = metadata['datos']
                    logger.info(f"AEMET datos URL: {datos_url}")
                    
                    # Second request - get actual data
                    datos_response = requests.get(datos_url, timeout=10)
                    logger.info(f"AEMET datos response status: {datos_response.status_code}")
                    
                    if datos_response.status_code == 200:
                        try:
                            data = datos_response.json()
                            logger.info(f"AEMET datos response: {data}")
                            
                            # AEMET returns an array, get the last (most recent) item
                            if isinstance(data, list) and len(data) > 0:
                                latest_data = data[-1]
                                # Extract temperature ('ta' field)
                                temperature = latest_data.get('ta', None)
                                if temperature is not None:
                                    temperature = float(temperature)
                                
                                logger.info(f"Extracted temperature from AEMET: {temperature}")
                                
                                return {
                                    'source': 'AEMET',
                                    'temperature': temperature,
                                    'timestamp': datetime.now(),
                                    'raw_data': latest_data
                                }
                            else:
                                logger.warning("AEMET returned empty or invalid data array")
                                return None
                        except ValueError as json_error:
                            logger.error(f"AEMET datos JSON parse error: {json_error}")
                            logger.error(f"AEMET datos raw response: {datos_response.text}")
                            return None
                    else:
                        logger.warning(f"AEMET datos error: {datos_response.status_code} - {datos_response.text}")
                        return None
                else:
                    logger.warning("AEMET metadata does not contain 'datos' URL")
                    return None
                    
            except ValueError as json_error:
                logger.error(f"AEMET API JSON parse error: {json_error}")
                logger.error(f"AEMET API raw response: {response.text}")
                return None
        else:
            logger.warning(f"AEMET API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting AEMET data: {e}")
        return None

def get_google_weather_data_for_location(lat, lon, location_name):
    """Get weather data from Google Weather API for specific coordinates"""
    try:
        if not GOOGLE_WEATHER_API_KEY:
            logger.warning("GOOGLE_WEATHER_API_KEY not configured")
            return None
            
        # Google Weather API - try different endpoints based on API type
        # Option 1: Weather API v1
        url = "https://weather.googleapis.com/v1/currentConditions:lookup"
        params = {
            "key": GOOGLE_WEATHER_API_KEY,
            "location.latitude": lat,
            "location.longitude": lon,
            "languageCode": "es"
        }
        
        logger.info(f"Making Google Weather API request for {location_name} to: {url}")
        logger.info(f"Google Weather API params: {params}")
        
        response = requests.get(url, params=params, timeout=10)
        
        logger.info(f"Google Weather API response status for {location_name}: {response.status_code}")
        logger.info(f"Google Weather API response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                logger.info(f"Google Weather API response data for {location_name}: {data}")
                
                # Extract all available data from Google Weather response
                temperature = None
                humidity = None
                pressure = None
                wind_speed = None
                wind_direction = None
                weather_description = None
                clouds = None
                
                # Try different possible response structures
                if 'temperature' in data:
                    # Direct temperature field (Google Weather API v1 format)
                    temp_data = data['temperature']
                    if isinstance(temp_data, dict):
                        temperature = temp_data.get('degrees') or temp_data.get('value')
                    else:
                        temperature = temp_data
                elif 'currentConditions' in data:
                    current = data['currentConditions']
                    if 'temperature' in current:
                        if isinstance(current['temperature'], dict):
                            temperature = current['temperature'].get('degrees') or current['temperature'].get('value')
                        else:
                            temperature = current['temperature']
                    
                    # Extract additional fields
                    humidity = current.get('humidity')
                    pressure = current.get('pressure')
                    clouds = current.get('cloudiness')
                    
                    if 'wind' in current:
                        wind_data = current['wind']
                        wind_speed = wind_data.get('speed')
                        wind_direction = wind_data.get('direction')
                    
                    if 'weatherConditions' in current:
                        weather_description = current['weatherConditions'].get('description')
                        
                elif 'current' in data:
                    current = data['current']
                    temperature = current.get('temperature', current.get('temp'))
                    humidity = current.get('humidity')
                    pressure = current.get('pressure')
                    wind_speed = current.get('wind_speed')
                    wind_direction = current.get('wind_direction')
                    weather_description = current.get('description')
                    clouds = current.get('clouds')
                elif 'main' in data:
                    # OpenWeatherMap style response
                    temperature = data['main'].get('temp')
                    humidity = data['main'].get('humidity')
                    pressure = data['main'].get('pressure')
                    if 'wind' in data:
                        wind_speed = data['wind'].get('speed')
                        wind_direction = data['wind'].get('deg')
                    if 'weather' in data and len(data['weather']) > 0:
                        weather_description = data['weather'][0].get('description')
                    if 'clouds' in data:
                        clouds = data['clouds'].get('all')
                
                # Convert temperature to float
                if temperature is not None:
                    try:
                        temperature = float(temperature)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert temperature to float: {temperature}")
                        temperature = None
                
                # Convert other numeric fields
                if humidity is not None:
                    try:
                        humidity = float(humidity)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert humidity to float: {humidity}")
                        humidity = None
                        
                if pressure is not None:
                    try:
                        pressure = float(pressure)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert pressure to float: {pressure}")
                        pressure = None
                        
                if wind_speed is not None:
                    try:
                        wind_speed = float(wind_speed)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert wind_speed to float: {wind_speed}")
                        wind_speed = None
                        
                if wind_direction is not None:
                    try:
                        wind_direction = float(wind_direction)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert wind_direction to float: {wind_direction}")
                        wind_direction = None
                        
                if clouds is not None:
                    try:
                        clouds = float(clouds)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert clouds to float: {clouds}")
                        clouds = None
                
                logger.info(f"Extracted data from Google Weather for {location_name}: temp={temperature}, humidity={humidity}, pressure={pressure}, wind_speed={wind_speed}")
                
                return {
                    'source': f'Google Weather ({location_name})',
                    'temperature': temperature,
                    'humidity': humidity,
                    'pressure': pressure,
                    'wind_speed': wind_speed,
                    'wind_direction': wind_direction,
                    'weather_description': weather_description,
                    'clouds': clouds,
                    'timestamp': datetime.now(),
                    'raw_data': data
                }
            except ValueError as json_error:
                logger.error(f"Google Weather API JSON parse error: {json_error}")
                logger.error(f"Google Weather API raw response: {response.text}")
                return None
        else:
            logger.warning(f"Google Weather API error for {location_name}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting Google Weather data for {location_name}: {e}")
        return None

def get_google_weather_data():
    """Get weather data from Google Weather API for Villafría"""
    return get_google_weather_data_for_location(VILLAFRIA_LAT, VILLAFRIA_LON, "Villafría")

def get_google_weather_burgos_center_data():
    """Get weather data from Google Weather API for Burgos Center"""
    return get_google_weather_data_for_location(BURGOS_CENTER_LAT, BURGOS_CENTER_LON, "Burgos Centro")

def get_google_weather_sarria_data():
    """Get weather data from Google Weather API for Sarrià"""
    return get_google_weather_data_for_location(SARRIA_LAT, SARRIA_LON, "Sarrià")

def collect_weather_data():
    """Collect Google Weather data for Burgos Centro and store in database"""
    try:
        google_burgos_center_data = get_google_weather_burgos_center_data()
        
        if not google_burgos_center_data:
            logger.warning("No se pudieron obtener datos de Google Weather para Burgos Centro")
            return None
        
        timestamp = datetime.now()
        weather_record = {
            'timestamp': timestamp,
            'google_weather_burgos_center': google_burgos_center_data,
            'raw_data': google_burgos_center_data.get('raw_data', {})
        }
        
        # Store in database
        result = weather_collection.insert_one(weather_record)
        weather_record['_id'] = result.inserted_id
        logger.info(f"Burgos Centro weather data collected at {timestamp}")
        
        return weather_record
        
    except Exception as e:
        logger.error(f"Error collecting weather data: {e}")
        return None

# Weather API endpoints
@weather_comparison_bp.route('/api/weather/current', methods=['GET'])
def get_current_weather():
    """Get current weather comparison"""
    try:
        # Get latest weather data
        latest_record = weather_collection.find_one(sort=[('timestamp', -1)])
        
        if not latest_record:
            # If no data exists, collect it now
            latest_record = collect_weather_data()
        
        if latest_record:
            # Convert ObjectId to string and datetime to ISO format
            latest_record['_id'] = str(latest_record['_id'])
            latest_record['timestamp'] = latest_record['timestamp'].isoformat()
            
            return jsonify({
                'success': True,
                'data': latest_record
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Unable to get weather data'
            }), 500
            
    except Exception as e:
        logger.error(f"Error getting current weather: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@weather_comparison_bp.route('/api/weather/history', methods=['GET'])
def get_weather_history():
    """Get weather history (last 30 records)"""
    try:
        records = list(weather_collection.find().sort('timestamp', -1).limit(30))
        
        # Convert ObjectId to string and datetime to ISO format
        for record in records:
            record['_id'] = str(record['_id'])
            record['timestamp'] = record['timestamp'].isoformat()
        
        return jsonify({
            'success': True,
            'data': records,
            'count': len(records)
        })
        
    except Exception as e:
        logger.error(f"Error getting weather history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@weather_comparison_bp.route('/api/weather/collect', methods=['POST'])
def manual_collect_weather():
    """Manually trigger weather data collection"""
    try:
        weather_record = collect_weather_data()
        
        if weather_record:
            weather_record['_id'] = str(weather_record['_id'])
            weather_record['timestamp'] = weather_record['timestamp'].isoformat()
            
            return jsonify({
                'success': True,
                'data': weather_record,
                'message': 'Weather data collected successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to collect weather data'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in manual weather collection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@weather_comparison_bp.route('/api/weather/scheduler/status', methods=['GET'])
def get_scheduler_status_endpoint():
    """Get current scheduler status"""
    try:
        status = get_scheduler_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@weather_comparison_bp.route('/api/weather/scheduler/start', methods=['POST'])
def start_scheduler_endpoint():
    """Start the weather data scheduler"""
    try:
        result = start_weather_scheduler()
        if result:
            return jsonify({
                'success': True,
                'message': 'Weather data scheduler started',
                'status': get_scheduler_status()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Scheduler is already running',
                'status': get_scheduler_status()
            })
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@weather_comparison_bp.route('/api/weather/scheduler/stop', methods=['POST'])
def stop_scheduler_endpoint():
    """Stop the weather data scheduler"""
    try:
        result = stop_weather_scheduler()
        return jsonify({
            'success': True,
            'message': 'Weather data scheduler stop requested',
            'status': get_scheduler_status()
        })
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Scheduler control variables
scheduler_running = True
scheduler_thread = None

# Background task for automatic weather data collection
def weather_data_scheduler():
    """Background scheduler to collect weather data every 10 minutes"""
    global scheduler_running
    while scheduler_running:
        try:
            if scheduler_running:  # Double check before collecting
                collect_weather_data()
            time.sleep(600)  # 10 minutes = 600 seconds
        except Exception as e:
            logger.error(f"Error in weather scheduler: {e}")
            time.sleep(600)  # Continue trying every 10 minutes
    logger.info("Weather data scheduler stopped")

# Start background scheduler
def start_weather_scheduler():
    global scheduler_running, scheduler_thread
    if scheduler_thread is None or not scheduler_thread.is_alive():
        scheduler_running = True
        scheduler_thread = threading.Thread(target=weather_data_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info("✅ Weather data scheduler started (collects every 10 minutes)")
        return True
    return False

# Stop background scheduler
def stop_weather_scheduler():
    global scheduler_running
    scheduler_running = False
    logger.info("🛑 Weather data scheduler stop requested")
    return True

# Get scheduler status
def get_scheduler_status():
    global scheduler_running, scheduler_thread
    is_alive = scheduler_thread is not None and scheduler_thread.is_alive()
    return {
        'running': scheduler_running,
        'thread_alive': is_alive,
        'status': 'running' if scheduler_running and is_alive else 'stopped'
    }

# Initialize scheduler when blueprint is imported
start_weather_scheduler()