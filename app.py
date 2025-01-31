from flask import Flask, jsonify, request, Response
from livedata import get_meteohub_parameter
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timedelta
import logging
import os
import pytz
import requests
import re
import undetected_chromedriver as uc
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
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

@app.route('/api/live')
def live_weather():
    try:
        live_data = {
            "external_temperature": get_meteohub_parameter("ext_temp"),
            "internal_temperature": get_meteohub_parameter("int_temp"),
            "humidity": get_meteohub_parameter("hum"),
            "wind_direction": get_meteohub_parameter("wind_dir"),
            "wind_speed": get_meteohub_parameter("wind_speed"),
            "gust_speed": get_meteohub_parameter("gust_speed"),
            "pressure": get_meteohub_parameter("press"),
            "current_rain_rate": get_meteohub_parameter("cur_rain"),
            "total_rain": get_meteohub_parameter("total_rain"),
            "solar_radiation": get_meteohub_parameter("rad"),
            "uv_index": get_meteohub_parameter("uv"),
        }

        if any(value is None for value in live_data.values()):
            return jsonify({"error": "Could not retrieve complete live weather data"}), 500

        return jsonify(live_data)
    except Exception as e:
        logging.error(f"Error in live_weather endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500

def setup_chrome_options():
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    # Configuración específica para Render
    if os.environ.get('RENDER'):
        chrome_binary = "/usr/bin/google-chrome-stable"
        if os.path.exists(chrome_binary):
            logger.info(f"Setting chrome binary location to {chrome_binary}")
            options.binary_location = chrome_binary
        else:
            logger.error(f"Chrome binary not found at {chrome_binary}")
    
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    return options

def get_weather_data():
    driver = None
    try:
        options = setup_chrome_options()
        logger.info("Chrome options configured")
        
        # No especificar driver_executable_path para permitir que undetected_chromedriver lo maneje
        driver = uc.Chrome(
            options=options,
            version_main=120  # Asegúrate de que esto coincida con la versión de Chrome instalada
        )
        logger.info("Chrome driver initialized")
        
        driver.set_page_load_timeout(20)
        logger.info("Loading page...")
        
        driver.get('https://renuncio.com/meteorologia/actual')
        logger.info("Page loaded")
        
        time.sleep(5)
        content = driver.page_source
        logger.info("Content retrieved successfully")
        
        return content
            
    except Exception as e:
        logger.error(f"Error in get_weather_data: {str(e)}")
        return None
        
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Driver closed successfully")
            except Exception as e:
                logger.error(f"Error closing driver: {str(e)}")

class WeatherCache:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self.CACHE_DURATION = timedelta(minutes=2)

    def get(self):
        with self._lock:
            now = datetime.now()
            if 'weather' in self._cache:
                timestamp, content = self._cache['weather']
                if now - timestamp < self.CACHE_DURATION:
                    logger.info("Returning cached content")
                    return content
            
            logger.info("Fetching fresh content")
            content = get_weather_data()
            if content:
                self._cache['weather'] = (now, content)
            return content

weather_cache = WeatherCache()


        
@app.route('/api/renuncio')
async def renuncio_data():
    try:
        logging.info("renuncio endpoint called")
 
        logger.info("Weather endpoint called")
        content = weather_cache.get()
 
        # Configure Chrome options for headless mode

        logging.info(f"HTML Content: {content}...")

        # Define the regular expression pattern to extract the data
 
        pattern = r"(?si)(.*)Actualizado el(.*)>(.*)<\/span> a las(.*)>(.*)<\/span>(.*)<div class=\"temperatura_valor\">(.*)<\/div>(.*)VIENTO<(.*)(\d+(?:,\d+)?) km\/h \- (.*)\n.*<\/div>(.*)(\d+) %(.*)(\d+(?:,\d+)?)(.*)\sW\/(.*)/"
        # Find all matches of the pattern in the HTML content
        matches = re.findall(pattern, html_content)
        logging.info(f"Matches: {matches}")

        # Extract the data from the matches
#        date = matches[0][2]
#        logging.info(f"Date: {date}")
#        time = matches[0][4]
#        logging.info(f"Time: {time}")
#        temperature = matches[0][7]
#        logging.info(f"Temperature: {temperature}")

#        wind_speed = matches[0][10]
#        logging.info(f"Wind speed: {wind_speed}")
#        wind_direction = matches[0][11]
#        logging.info(f"Wind direction: {wind_direction}")
#        humidity = matches[0][13]
#        logging.info(f"Humidity: {humidity}")
#        solar_radiation = matches[0][15]
#        logging.info(f"Solar radiation: {solar_radiation}")


        date = "29/01/25"
        time = "1200"
        temperature = "12"
        wind_speed = "4"
        wind_direction = "NNW"
        humidity = "98"
        solar_radiation = "0"


        # Format the data
        data = {
            "date": date,
            "time": time,
            "temperature": temperature,
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "humidity": humidity,
            "solar_radiation": solar_radiation
        }

        jsonData = jsonify(data)
        logging.info(f"Data extracted from renuncio.com: {jsonData}")   
        # Return the data as a JSON response
        return jsonData
    except Exception as e:
        logging.error(f"Error fetching data from renuncio.com: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/meteo-data')
def temperature_data():
    try:
        logging.info("meteo-data endpoint called")
        time_range = request.args.get('timeRange', '24h')
        end_time = datetime.now(pytz.timezone('Europe/Madrid'))

        if time_range == '24h':
            start_time = end_time - timedelta(hours=24)
            interval = 1 # Every 5 minutes (no skipping)
        elif time_range == '48h':
            start_time = end_time - timedelta(hours=48)
            interval = 2 # Every 10 minutes (skip every other data point)
        elif time_range == '7d':
            start_time = end_time - timedelta(days=7)
            interval = 6 # Every 30 minutes (skip 5 data points, take the 6th)
        else:
            return jsonify({"error": "Invalid time range"}), 400

        end_time_str = end_time.strftime("%d-%m-%Y %H:%M")
        start_time_str = start_time.strftime("%d-%m-%Y %H:%M")

        logging.info(f"Querying data from {start_time_str} to {end_time_str} for time range: {time_range}")

        # Fetch data with sampling based on time range
        data = list(
            collection.find({"timestamp": {"$gte": start_time_str, "$lte": end_time_str}})
            .sort("timestamp", 1)
        )

        # Apply sampling
        sampled_data = data[::interval]

#        logging.info(f"Retrieved and sampled data: {sampled_data}")

        for entry in sampled_data:
            entry["_id"] = str(entry["_id"])

        return jsonify(sampled_data)

    except Exception as e:
        logging.error(f"Error fetching meteo data: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/webcam-image')
def webcam_image():
    logging.info("webcam-image endpoint called")
    image_url = "https://ibericam.com/espana/burgos/webcam-burgos-catedral-de-burgos/"
    proxy_url = f"https://api.allorigins.win/raw?url={image_url}"  # Using the public proxy
    response = requests.get(proxy_url)
    logging.info(f"Response status code: {response.status_code}")
    return Response(response.content, content_type=response.headers['Content-Type'])



if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)