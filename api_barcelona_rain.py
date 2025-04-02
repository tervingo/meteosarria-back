from flask import Blueprint, jsonify
import logging
import os
import requests
import json
from datetime import datetime, timedelta
import pytz
from database import db

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
barcelona_rain_bp = Blueprint('barcelona_rain', __name__)

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

@barcelona_rain_bp.route('/api/barcelona-rain')
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

@barcelona_rain_bp.route('/api/barcelona-rain/clear-cache', methods=['POST'])
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