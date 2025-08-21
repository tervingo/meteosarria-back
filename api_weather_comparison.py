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

# Database collections
try:
    db = get_db()
    weather_collection = db.weather_data
    logger.info("Connected to weather_data collection")
except Exception as e:
    logger.error(f"Error connecting to weather_data collection: {e}")
    raise

# Weather data functions
def get_aemet_data():
    """Get weather data from AEMET for Villafría station"""
    try:
        # AEMET API endpoint for Villafría station (1109 is Burgos/Villafría)
        url = "https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/1109"
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
                            
                            # AEMET returns an array, get the first (most recent) item
                            if isinstance(data, list) and len(data) > 0:
                                latest_data = data[0]
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

def get_google_weather_data():
    """Get weather data from Google Weather API"""
    try:
        if not GOOGLE_WEATHER_API_KEY:
            logger.warning("GOOGLE_WEATHER_API_KEY not configured")
            return None
            
        # Google Weather API - try different endpoints based on API type
        # Option 1: Weather API v1
        url = "https://weather.googleapis.com/v1/currentConditions:lookup"
        params = {
            "key": GOOGLE_WEATHER_API_KEY,
            "location.latitude": VILLAFRIA_LAT,
            "location.longitude": VILLAFRIA_LON,
            "languageCode": "es"
        }
        
        logger.info(f"Making Google Weather API request to: {url}")
        logger.info(f"Google Weather API params: {params}")
        
        response = requests.get(url, params=params, timeout=10)
        
        logger.info(f"Google Weather API response status: {response.status_code}")
        logger.info(f"Google Weather API response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                logger.info(f"Google Weather API response data: {data}")
                
                # Extract temperature from Google Weather response (try different structures)
                temperature = None
                
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
                elif 'current' in data:
                    current = data['current']
                    temperature = current.get('temperature', current.get('temp'))
                elif 'main' in data:
                    # OpenWeatherMap style response
                    temperature = data['main'].get('temp')
                
                if temperature is not None:
                    try:
                        temperature = float(temperature)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert temperature to float: {temperature}")
                        temperature = None
                
                logger.info(f"Extracted temperature from Google Weather: {temperature}")
                
                return {
                    'source': 'Google Weather',
                    'temperature': temperature,
                    'timestamp': datetime.now(),
                    'raw_data': data
                }
            except ValueError as json_error:
                logger.error(f"Google Weather API JSON parse error: {json_error}")
                logger.error(f"Google Weather API raw response: {response.text}")
                return None
        else:
            logger.warning(f"Google Weather API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting Google Weather data: {e}")
        return None

def collect_weather_data():
    """Collect data from both sources and store in database"""
    try:
        aemet_data = get_aemet_data()
        google_data = get_google_weather_data()
        
        timestamp = datetime.now()
        weather_record = {
            'timestamp': timestamp,
            'aemet': aemet_data,
            'google_weather': google_data
        }
        
        # Store in database
        result = weather_collection.insert_one(weather_record)
        weather_record['_id'] = result.inserted_id
        logger.info(f"Weather data collected at {timestamp}")
        
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

# Background task for automatic weather data collection
def weather_data_scheduler():
    """Background scheduler to collect weather data every 10 minutes"""
    while True:
        try:
            collect_weather_data()
            time.sleep(600)  # 10 minutes = 600 seconds
        except Exception as e:
            logger.error(f"Error in weather scheduler: {e}")
            time.sleep(600)  # Continue trying every 10 minutes

# Start background scheduler
def start_weather_scheduler():
    scheduler_thread = threading.Thread(target=weather_data_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("✅ Weather data scheduler started (collects every 10 minutes)")

# Initialize scheduler when blueprint is imported
start_weather_scheduler()