import os
import logging
from datetime import datetime, timedelta
import pytz
import requests
import time
from pymongo import MongoClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('update_rain_meteocat.log'),
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
    """Get rain data for a specific date from Meteocat API for Fabra Observatory (D5)"""
    METEOCAT_API_KEY = os.getenv('METEOCAT_API_KEY')
    if not METEOCAT_API_KEY:
        raise ValueError("Meteocat API key not found in environment variables")

    # Format the date components for the URL
    month = str(date.month).zfill(2)
    day = str(date.day).zfill(2)
    year = date.year
    
    url = f'https://api.meteo.cat/xema/v1/variables/mesurades/35/{year}/{month}/{day}?codiEstacio=D5'
    
    headers = {
        'Content-Type': 'application/json',
        'X-Api-Key': METEOCAT_API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Sum all precipitation values for each half-hour interval
        daily_rain = 0.0
        for lecture in data.get('lectures', []):
            if lecture.get('estat') == 'V':  # Only count valid measurements
                daily_rain += float(lecture.get('valor', 0))
        
        logger.info(f"Rain for {date.strftime('%Y-%m-%d')}: {daily_rain:.2f}mm")
        return daily_rain
    except Exception as e:
        logger.error(f"Error getting rain data for {date.strftime('%Y-%m-%d')}: {e}")
        return 0.0

def get_accumulated_rain(start_date: datetime, end_date: datetime) -> float:
    """Get accumulated rain between two dates"""
    accumulated = 0
    current_date = start_date
    
    while current_date <= end_date:
        daily_rain = get_daily_rain(current_date)
        accumulated += daily_rain
        current_date += timedelta(days=1)
        time.sleep(1)  # Respect API rate limits with a 1-second delay
        
    return accumulated

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
                
            # Get the date of the last record and make it timezone-aware
            last_date = datetime.strptime(last_record['date'], '%Y-%m-%d')
            last_date = barcelona_tz.localize(last_date)
            # Start from the day after the last record
            start_date = last_date + timedelta(days=1)
            accumulated_rain = last_record['accumulated']
            
        else:
            # If no previous record exists, start from January 1st (timezone-aware)
            start_date = barcelona_tz.localize(datetime(year=today.year, month=1, day=1))
            logger.info(f"No previous records found, getting data from {start_date.strftime('%Y-%m-%d')}")
            accumulated_rain = 0

        # Get rain data for all missing days
        new_rain = get_accumulated_rain(start_date, yesterday)
        new_accumulated = accumulated_rain + new_rain

        # Save new accumulation
        rain_collection.insert_one({
            'date': yesterday_date,
            'daily_rain': get_daily_rain(yesterday),  # Store yesterday's rain separately
            'accumulated': new_accumulated,
            'timestamp': datetime.now(barcelona_tz),
            'source': 'Meteocat Fabra Observatory'
        })

        logger.info(f"Updated rain accumulation: {new_accumulated:.2f}mm")

    except Exception as e:
        logger.error(f"Error updating rain accumulation: {e}")
        raise

if __name__ == '__main__':
    try:
        logger.info("Starting rain accumulation update from Meteocat")
        update_rain_accumulation()
        logger.info("Finished rain accumulation update from Meteocat")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        raise 