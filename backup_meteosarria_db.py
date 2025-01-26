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
from urllib.parse import quote  # Import for URL encoding

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- MongoDB Connection ---
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

# --- Dropbox Connection (using refresh token) ---
try:
    dropbox_refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")
    dropbox_app_key = os.getenv("DROPBOX_CLIENT_ID")
    dropbox_app_secret = os.getenv("DROPBOX_CLIENT_SECRET")

    if not dropbox_refresh_token or not dropbox_app_key or not dropbox_app_secret:
        raise ValueError(
            "DROPBOX_REFRESH_TOKEN, DROPBOX_CLIENT_ID, and DROPBOX_CLIENT_SECRET environment variables must be set"
        )

    # Initialize Dropbox client (dummy access token, it will be refreshed)
    dbx = dropbox.Dropbox(
        oauth2_access_token="dummy",
        oauth2_refresh_token=dropbox_refresh_token,
        app_key=dropbox_app_key,
        app_secret=dropbox_app_secret,
    )
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
    """
    Fetches data from MongoDB, creates a CSV file, and uploads it to Dropbox.
    Handles Dropbox access token refresh.
    """
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
        madrid_tz = pytz.timezone("Europe/Madrid")
        current_time_madrid = datetime.now(madrid_tz)
        filename = f"meteosarria_data_{current_time_madrid.strftime('%Y%m%d')}.csv"
        filepath = f"/tmp/{filename}"  # Use /tmp for temporary file

        with open(filepath, "w", newline="") as csvfile:
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
                "timestamp",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for doc in data:
                doc.pop("_id", None)
                writer.writerow(doc)

        logging.info(f"Data written to local file: {filepath}")

        # Upload to Dropbox
        logging.info(f"Uploading CSV to Dropbox...")
        dropbox_path = f"/{filename}"

        with open(filepath, "rb") as f:
            try:
                dbx.files_upload(f.read(), dropbox_path, mode=WriteMode("overwrite"))
            except AuthError as e:
                logging.info(f"AuthError: {e}. Refreshing token and retrying.")
                new_access_token = refresh_dropbox_token()

                # Update Dropbox client with the new access token
                global dbx
                dbx = dropbox.Dropbox(
                    oauth2_access_token=new_access_token,
                    oauth2_refresh_token=dropbox_refresh_token,
                    app_key=dropbox_app_key,
                    app_secret=dropbox_app_secret,
                )

                # Retry the upload
                dbx.files_upload(f.read(), dropbox_path, mode=WriteMode("overwrite"))

        logging.info(f"CSV file uploaded to Dropbox: {dropbox_path}")

    except Exception as e:
        logging.error(f"Error during export/upload process: {e}")

    finally:
        # Clean up temporary file
        if "filepath" in locals() and os.path.exists(filepath):
            os.remove(filepath)
            logging.info(f"Temporary file {filepath} removed.")


# --- Refresh Token Logic (Run this part ONLY LOCALLY to get the refresh token) ---
def get_refresh_token(client_id, client_secret, redirect_uri):
    """
    Guides the user through the Dropbox OAuth 2.0 flow to obtain a refresh token.
    This function should be run locally, not on Render.
    """
    encoded_redirect_uri = quote(redirect_uri)
    authorization_base_url = "https://www.dropbox.com/oauth2/authorize"
    authorization_url = f"{authorization_base_url}?client_id={client_id}&redirect_uri={encoded_redirect_uri}&response_type=code&token_access_type=offline"

    print(
        "1. Go to this URL in your browser to authorize the app:\n",
        authorization_url,
        "\n",
    )
    print("2. Authorize the app in your browser.")
    print("3. Copy the authorization code from the URL.")
    print("4. Paste the authorization code here and press Enter:\n")

    authorization_code = input("Paste the authorization code here: ")

    token_url = "https://api.dropboxapi.com/oauth2/token"
    data = {
        "code": authorization_code,
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }

    response = requests.post(token_url, data=data)
    response.raise_for_status()
    token_data = response.json()

    print("Refresh Token:", token_data["refresh_token"])
    print(
        "Store this refresh token securely as the DROPBOX_REFRESH_TOKEN environment variable."
    )
    return token_data["refresh_token"]


# --- Main Execution ---
if __name__ == "__main__":
    export_mongodb_to_csv_and_upload_to_dropbox()