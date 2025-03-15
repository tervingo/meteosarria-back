import os
import logging
from datetime import datetime, timedelta
import pytz
import requests
import time
from pymongo import MongoClient

def get_daily_rain() -> float:
    """Get rain data for a specific date from Meteocat API for Fabra Observatory (D5)"""
    METEOCAT_API_KEY = os.getenv('METEOCAT_API_KEY')
    if not METEOCAT_API_KEY:
        raise ValueError("Meteocat API key not found in environment variables")

    barcelona_tz = pytz.timezone('Europe/Madrid')
    today = datetime.now(barcelona_tz)
    # Format the date components for the URL
    month = str(today.month).zfill(2)
    day = str(today.day).zfill(2)
    year = today.year
    
    url = f'https://api.meteo.cat/xema/v1/variables/mesurades/35/{year}/{month}/{day}?codiEstacio=D5'
    
    headers = {
        'Content-Type': 'application/json',
        'X-Api-Key': METEOCAT_API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        print(data)

        # Sum all precipitation values for each half-hour interval
        daily_rain = 0.0
        for lecture in data.get('lectures', []):
#            if lecture.get('estat') == 'V':  # Only count valid measurements
            daily_rain += float(lecture.get('valor', 0))
        
        print(f"Rain for {today.strftime('%Y-%m-%d')}: {daily_rain:.2f}mm")
        return daily_rain
    except Exception as e:
        print(f"Error getting rain data for {today.strftime('%Y-%m-%d')}: {e}")
        return 0.0

if __name__ == "__main__":
    get_daily_rain()