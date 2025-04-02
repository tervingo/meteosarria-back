from flask import Blueprint, jsonify
import logging
import os
import requests
import tempfile
from google.cloud import translate_v2 as translate

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
burgos_bp = Blueprint('burgos', __name__)

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

@burgos_bp.route('/api/burgos-weather')
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
                    translated_overview = data['weather'][0]['description']
                    logger.warning("Translation service not available, using OpenWeather description")
            except Exception as e:
                logger.error(f"Error translating weather overview: {e}")
                translated_overview = weather_overview
        else:
            translated_overview = data['weather'][0]['description']

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