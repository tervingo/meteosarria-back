import os
import logging
from datetime import datetime, timedelta
import pytz
import requests
import time
from pymongo import MongoClient
import sys

def get_daily_rain(date_str=None) -> float:
    """Get rain data for a specific date from Meteocat API for Fabra Observatory (D5)
    
    Args:
        date_str (str, optional): Date in dd-mm-yyyy format. If None, uses today's date.
    
    Returns:
        float: Total daily rain in mm
    """
    METEOCAT_API_KEY = os.getenv('METEOCAT_API_KEY')
    if not METEOCAT_API_KEY:
        raise ValueError("Meteocat API key not found in environment variables")

    barcelona_tz = pytz.timezone('Europe/Madrid')
    
    if date_str:
        try:
            # Parse the input date string
            day, month, year = map(int, date_str.split('-'))
            target_date = datetime(year, month, day, tzinfo=barcelona_tz)
        except ValueError as e:
            raise ValueError(f"Invalid date format. Expected dd-mm-yyyy, got {date_str}") from e
    else:
        target_date = datetime.now(barcelona_tz)
    
    # Format the date components for the URL
    month = str(target_date.month).zfill(2)
    day = str(target_date.day).zfill(2)
    year = target_date.year
    
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
            daily_rain += float(lecture.get('valor', 0))
        
        print(f"Rain for {target_date.strftime('%Y-%m-%d')}: {daily_rain:.2f}mm")
        return daily_rain
    except Exception as e:
        print(f"Error getting rain data for {target_date.strftime('%Y-%m-%d')}: {e}")
        return 0.0

if __name__ == "__main__":
    # Check if a date argument was provided
    if len(sys.argv) > 1:
        date_arg = sys.argv[1]
        get_daily_rain(date_arg)
    else:
        get_daily_rain()