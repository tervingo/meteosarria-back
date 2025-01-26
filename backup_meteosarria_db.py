import logging
import os
import csv
from pymongo import MongoClient
from datetime import datetime
import dropbox
from dropbox.files import WriteMode
import pytz

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
    exit(1)

# Dropbox connection
try:
    dropbox_token = os.getenv("DROPBOX_TOKEN")
    if not dropbox_token:
        raise ValueError("DROPBOX_TOKEN environment variable not set")

    dbx = dropbox.Dropbox(dropbox_token)
    logging.info("Connected to Dropbox")
except Exception as e:
    logging.error(f"Error connecting to Dropbox: {e}")
    exit(1)


def export_mongodb_to_csv_and_upload_to_dropbox():
    try:
        # Fetch data from MongoDB
        logging.info("Fetching data from MongoDB...")
        cursor = collection.find({})
        data = list(cursor)

        if not data:
            logging.warning("No data found in MongoDB collection.")
            return

        # Prepare CSV file
        logging.info("Preparing CSV file...")
        madrid_tz = pytz.timezone('Europe/Madrid')
        current_time_madrid = datetime.now(madrid_tz)
        filename = f"meteosarria_data_{current_time_madrid.strftime('%Y%m%d')}.csv"
        filepath = f"/tmp/{filename}"  # Use /tmp for temporary file in Render

        with open(filepath, 'w', newline='') as csvfile:
            fieldnames = [
                "external_temperature",
                "internal_temperature",
                "humidity",
                "pressure",
                "wind_speed",
                "wind_direction",
                "current_rain_rate",
                "total_rain",
                "solar_radiation",
                "timestamp"
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for doc in data:
                # Remove the _id field as it's not needed in the CSV and can cause issues
                doc.pop('_id', None)
                writer.writerow(doc)
            
        logging.info(f"Data written to local file: {filepath}")

        # Upload to Dropbox
        logging.info(f"Uploading CSV to Dropbox...")
        dropbox_path = f"/meteosarria/{filename}"  # Specify your desired Dropbox folder path

        with open(filepath, "rb") as f:
            dbx.files_upload(f.read(), dropbox_path, mode=WriteMode('overwrite'))

        logging.info(f"CSV file uploaded to Dropbox: {dropbox_path}")

    except Exception as e:
        logging.error(f"Error during export/upload process: {e}")

    finally:
        # Clean up temporary file
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
            logging.info(f"Temporary file {filepath} removed.")


if __name__ == '__main__':
    export_mongodb_to_csv_and_upload_to_dropbox()