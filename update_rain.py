import os
import logging
from datetime import datetime, timedelta
import pytz
import requests
from pymongo import MongoClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('update_rain.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MongoDB connection
try:
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise ValueError("MONGODB_URI environment variable not set")

    client = MongoClient(mongo_uri)
    db = client.meteosarria
    rain_collection = db.rain_accumulation
    logger.info("Connected to MongoDB")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")
    raise

def get_daily_rain(date: datetime) -> float:
    """Get rain data for a specific date from OpenWeatherMap API"""
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
    if not OPENWEATHER_API_KEY:
        raise ValueError("OpenWeather API key not found in environment variables")

    BARCELONA_LAT = 41.3874
    BARCELONA_LON = 2.1686
    
    date_str = date.strftime('%Y-%m-%d')
    url = f'https://api.openweathermap.org/data/3.0/onecall/day_summary?lat={BARCELONA_LAT}&lon={BARCELONA_LON}&date={date_str}&appid={OPENWEATHER_API_KEY}'
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        daily_rain = data.get('precipitation', {}).get('total', 0)
        logger.info(f"Rain for {date_str}: {daily_rain:.2f}mm")
        return daily_rain
    except Exception as e:
        logger.error(f"Error getting rain data for {date_str}: {e}")
        return 0.0

def update_rain_accumulation():
    """Update the rain accumulation in MongoDB"""
    try:
        # Get current date in Barcelona timezone
        barcelona_tz = pytz.timezone('Europe/Madrid')
        today = datetime.now(barcelona_tz)
        yesterday = today - timedelta(days=1)
        yesterday_date = yesterday.strftime('%Y-%m-%d')

        # Get last accumulation record
        last_record = rain_collection.find_one(sort=[("date", -1)])
        
        if last_record:
            logger.info(f"Found last record: {last_record['date']} with accumulation: {last_record['accumulated']:.2f}mm")
            
            # If yesterday's data is already recorded, exit
            if last_record['date'] == yesterday_date:
                logger.info("Rain data for yesterday already recorded")
                return
                
            accumulated_rain = last_record['accumulated']
        else:
            # If no previous record exists, initialize with yesterday's data
            logger.info("No previous records found, initializing accumulation")
            accumulated_rain = 0

        # Get yesterday's rain
        daily_rain = get_daily_rain(yesterday)
        new_accumulated = accumulated_rain + daily_rain

        # Save new accumulation
        rain_collection.insert_one({
            'date': yesterday_date,
            'daily_rain': daily_rain,
            'accumulated': new_accumulated,
            'timestamp': datetime.now(barcelona_tz)
        })

        logger.info(f"Updated rain accumulation: {new_accumulated:.2f}mm")

    except Exception as e:
        logger.error(f"Error updating rain accumulation: {e}")
        raise

if __name__ == '__main__':
    try:
        logger.info("Starting rain accumulation update")
        update_rain_accumulation()
        logger.info("Finished rain accumulation update")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        raise 