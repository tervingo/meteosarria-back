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
        # AEMET API endpoint for Villafría station (example URL - needs actual AEMET API key)
        # This is a placeholder - you'll need to get actual AEMET API access
        url = "https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/1109"
        headers = {'api_key': os.getenv('AEMET_API_KEY', 'your-aemet-api-key')}  # Use env var for API key
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Extract temperature from AEMET response (adjust based on actual API response)
            temperature = data.get('ta', None)  # 'ta' is typically temperature in AEMET
            return {
                'source': 'AEMET',
                'temperature': temperature,
                'timestamp': datetime.now(),
                'raw_data': data
            }
        else:
            logger.warning(f"AEMET API error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting AEMET data: {e}")
        # Return mock data for testing purposes
        return {
            'source': 'AEMET',
            'temperature': 18.5,  # Mock temperature
            'timestamp': datetime.now(),
            'raw_data': {'mock': True}
        }

def get_google_weather_data():
    """Get weather data from Google Weather API"""
    try:
        if not GOOGLE_WEATHER_API_KEY:
            logger.warning("No Google Weather API key provided")
            return None
            
        url = "https://weather.googleapis.com/v1/currentConditions:lookup"
        params = {
            "key": GOOGLE_WEATHER_API_KEY,
            "location.latitude": VILLAFRIA_LAT,
            "location.longitude": VILLAFRIA_LON
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Extract temperature from Google Weather response
            temperature = data.get('currentConditions', {}).get('temperature', {}).get('value')
            return {
                'source': 'Google Weather',
                'temperature': temperature,
                'timestamp': datetime.now(),
                'raw_data': data
            }
        else:
            logger.warning(f"Google Weather API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting Google Weather data: {e}")
        # Return mock data for testing purposes
        return {
            'source': 'Google Weather',
            'temperature': 19.2,  # Mock temperature
            'timestamp': datetime.now(),
            'raw_data': {'mock': True}
        }

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