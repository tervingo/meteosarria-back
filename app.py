from flask import Flask, jsonify
from livedata import get_meteohub_parameter
from flask_cors import CORS
from pymongo import MongoClient
import schedule
import time
from datetime import datetime
import threading
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)

# MongoDB connection
try:
    client = MongoClient("mongodb+srv://tervingo:mig.langar.inn@gagnagunnur.okrh1.mongodb.net/meteosarria")
    db = client.meteosarria
    collection = db.data
    logging.info("Connected to MongoDB")
except Exception as e:
    logging.error(f"Error connecting to MongoDB: {e}")

# Lock for synchronizing the logging function
log_lock = threading.Lock()

def log_weather_data():
    with log_lock:
        try:
            logging.info("Fetching weather data...")
            live_data = {
                "external_temperature": get_meteohub_parameter("ext_temp"),
                "internal_temperature": get_meteohub_parameter("int_temp"),
                "humidity": get_meteohub_parameter("hum"),
                "pressure": get_meteohub_parameter("press"),
                "wind_speed": get_meteohub_parameter("wind_speed"),
                "wind_direction": get_meteohub_parameter("wind_dir"),
                "current_rain_rate": get_meteohub_parameter("cur_rain"),
                "total_rain": get_meteohub_parameter("total_rain"),
                "solar_radiation": get_meteohub_parameter("rad"),
                "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M")
            }

            if any(value is None for value in live_data.values()):
                logging.warning("Could not retrieve complete live weather data")
                return

            collection.insert_one(live_data)
            logging.info(f"Logged weather data: {live_data}")
        except Exception as e:
            logging.error(f"Error logging weather data: {e}")

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

def run_scheduler():
    logging.info("Starting scheduler...")
    schedule.every(5).minutes.do(log_weather_data)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.start()
    app.run(debug=True, use_reloader=False)