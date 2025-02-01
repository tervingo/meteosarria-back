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
import ssl
import socket

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

        logging.info(f"Retrieved and sampled data: {sampled_data}")

        for entry in sampled_data:
            entry["_id"] = str(entry["_id"])

        return jsonify(sampled_data)

    except Exception as e:
        logging.error(f"Error fetching meteo data: {e}")
        return jsonify({"error": "Internal server error"}), 500

#-----------------------
# api/renuncio AP
#-----------------------


def create_ssl_context():
    """Crea un contexto SSL similar al que usa Rainmeter"""
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    context.set_ciphers('HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!aECDH')
    return context

def get_weather_data():
    """
    Obtiene los datos meteorológicos usando una conexión TLS directa
    similar a la que usa Rainmeter
    """
    try:
        # Crear socket
        sock = socket.create_connection(('renuncio.com', 443))
        context = create_ssl_context()
        
        # Envolver el socket con TLS
        ssock = context.wrap_socket(sock, server_hostname='renuncio.com')
        
        # Construir petición HTTP básica
        request = (
            'GET /meteorologia/actual HTTP/1.1\r\n'
            'Host: renuncio.com\r\n'
            'Cache-Control: no-cache\r\n'
            'Connection: close\r\n'
            '\r\n'
        )
        
        # Enviar petición
        ssock.send(request.encode())
        
        # Recibir respuesta
        response = b''
        while True:
            chunk = ssock.recv(8192)
            if not chunk:
                break
            response += chunk
            
        return response.decode('utf-8')
            
    except Exception as e:
        logger.error(f"Error en la petición: {str(e)}")
        return None
    finally:
        try:
            ssock.close()
        except:
            pass

class WeatherCache:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self.CACHE_DURATION = timedelta(minutes=1)  # Igual que Rainmeter

    def get(self):
        with self._lock:
            now = datetime.now()
            if 'weather' in self._cache:
                timestamp, content = self._cache['weather']
                if now - timestamp < self.CACHE_DURATION:
                    logger.info("Retornando contenido cacheado")
                    return content
            
            logger.info("Obteniendo contenido fresco")
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
        matches = re.findall(pattern, content)
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


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)