from flask import Flask, jsonify
from livedata import get_meteohub_parameter
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timedelta
import logging
import os

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

@app.route('/api/temperature-data')
def temperature_data():
    try:
        logging.info("temperature_data endpoint called")
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)

        # Convert datetime objects to the format "DD-MM-YYYY hh:mm"
        end_time_str = end_time.strftime("%d-%m-%Y %H:%M")
        start_time_str = start_time.strftime("%d-%m-%Y %H:%M")

        logging.info(f"Querying data from {start_time_str} to {end_time_str}")

        data = list(collection.find({"timestamp": {"$gte": start_time_str, "$lte": end_time_str}}).sort("timestamp", -1).limit(24 * 12))

        logging.info(f"Retrieved data: {data}")

        for entry in data:
            entry["_id"] = str(entry["_id"])  # Convert ObjectId to string for JSON serialization

        return jsonify(data)
    except Exception as e:
        logging.error(f"Error fetching temperature data: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)