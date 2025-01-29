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

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)

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

@app.route('/api/renuncio')
def renuncio_data():
    try:
        logging.info("renuncio endpoint called")
        # Define the URL to scrape
        url = "https://renuncio.com/meteorologia/actual"

        # Use requests to get the HTML content of the URL
        response = requests.get(url)
        html_content = response.text

        # Define the regular expression pattern to extract the data
    #    pattern = r"(?siU)(.*)Actualizado el(.*)>(.*)<\/span> a las(.*)>(.*)<\/span>(.*)<div class='temperatura_valor'>(.*)<\/div>(.*)VIENTO<(.*)(\d+(?:,\d+)?) km\/h \- (.*)\n.*<\/div>(.*)(\d+) %(.*)(\d+(?:,\d+)?) \sW\/(.*)"

        pattern = r"(?si)(.*)Actualizado el(.*)>(.*)<\/span> a las(.*)>(.*)<\/span>(.*)<div class=\"temperatura_valor\">(.*)<\/div>(.*)VIENTO<(.*)(\d+(?:,\d+)?) km\/h \- (.*)\n.*<\/div>(.*)(\d+) %(.*)(\d+(?:,\d+)?)(.*)\sW\/(.*)/"
        # Find all matches of the pattern in the HTML content
        matches = re.findall(pattern, html_content)

        # Extract the data from the matches
        date = matches[0][2]
        logging.info(f"Date: {date}")
        time = matches[0][4]
        logging.info(f"Time: {time}")
        temperature = matches[0][7]
        logging.info(f"Temperature: {temperature}")

#        wind_speed = matches[0][10]
#        logging.info(f"Wind speed: {wind_speed}")
#        wind_direction = matches[0][11]
#        logging.info(f"Wind direction: {wind_direction}")
#        humidity = matches[0][13]
#        logging.info(f"Humidity: {humidity}")
#        solar_radiation = matches[0][15]
#        logging.info(f"Solar radiation: {solar_radiation}")

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

        logging.info(f"Retrieved and sampled data: {sampled_data}")

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