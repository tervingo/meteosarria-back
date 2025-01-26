import logging
import os
import csv
from pymongo import MongoClient
from datetime import datetime
import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import AuthError
import pytz
import requests

# ... (rest of your imports)

# Configure logging
logging.basicConfig(level=logging.INFO)

# MongoDB connection
# ... (your MongoDB connection code)

# Dropbox connection
try:
    dropbox_refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")
    dropbox_app_key = os.getenv("DROPBOX_CLIENT_ID")
    dropbox_app_secret = os.getenv("DROPBOX_CLIENT_SECRET")

    if not dropbox_refresh_token or not dropbox_app_key or not dropbox_app_secret:
        raise ValueError("DROPBOX_REFRESH_TOKEN, DROPBOX_CLIENT_ID, and DROPBOX_CLIENT_SECRET environment variables must be set")

    # Initialize Dropbox with a dummy access token, as it will be refreshed immediately
    dbx = dropbox.Dropbox(oauth2_access_token='dummy', oauth2_refresh_token=dropbox_refresh_token, app_key=dropbox_app_key, app_secret=dropbox_app_secret)
    logging.info("Connected to Dropbox")

except Exception as e:
    logging.error(f"Error connecting to Dropbox: {e}")
    exit(1)

def refresh_dropbox_token():
    """Refreshes the Dropbox access token using the refresh token."""
    token_url = "https://api.dropboxapi.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": dropbox_refresh_token,
        "client_id": dropbox_app_key,
        "client_secret": dropbox_app_secret,
    }
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    token_data = response.json()
    return token_data["access_token"]

def export_mongodb_to_csv_and_upload_to_dropbox():
    try:
        # ... (your MongoDB data fetching and CSV creation code)

        # Upload to Dropbox
        logging.info(f"Uploading CSV to Dropbox...")
        dropbox_path = f"Meteosarria//{filename}"

        with open(filepath, "rb") as f:
            try:
                dbx.files_upload(f.read(), dropbox_path, mode=WriteMode('overwrite'))
            except AuthError as e:
                logging.info(f"AuthError: {e}. Refreshing token and retrying.")
                new_access_token = refresh_dropbox_token()
                
                # Update Dropbox client with the new access token
                global dbx
                dbx = dropbox.Dropbox(oauth2_access_token=new_access_token, oauth2_refresh_token=dropbox_refresh_token, app_key=dropbox_app_key, app_secret=dropbox_app_secret)
                
                # Retry the upload
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