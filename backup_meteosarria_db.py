import logging
import os
import csv
from pymongo import MongoClient
from datetime import datetime
import dropbox
from dropbox.files import WriteMode, DeleteError
from dropbox.exceptions import AuthError, ApiError
import pytz
import requests
from urllib.parse import quote

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


def create_new_dbx_instance(access_token):
    """Creates a new Dropbox instance with the given access token."""
    return dropbox.Dropbox(
        oauth2_access_token=access_token,
        oauth2_refresh_token=dropbox_refresh_token,
        app_key=dropbox_app_key,
        app_secret=dropbox_app_secret,
    )


def handle_dropbox_files():
    """
    Maneja los archivos en Dropbox:
    1. Intenta eliminar el archivo previo anterior si existe
    2. Renombra el archivo actual como previo
    """
    global dbx
    try:
        # Primero intentamos eliminar el archivo previo si existe
        try:
            dbx.files_delete_v2("/meteosarria_data_previo.csv")
            logging.info("Archivo previo anterior eliminado")
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                logging.info("No existe archivo previo para eliminar")
            else:
                raise

        # Ahora intentamos renombrar el archivo actual como previo
        try:
            dbx.files_move_v2(
                "/meteosarria_data.csv",
                "/meteosarria_data_previo.csv"
            )
            logging.info("Archivo actual renombrado como previo")
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                logging.info("No existe archivo actual para renombrar")
            else:
                raise

    except AuthError:
        logging.info("AuthError durante el manejo de archivos. Refreshing token.")
        new_access_token = refresh_dropbox_token()
        dbx = create_new_dbx_instance(new_access_token)
        # Retry the operation
        handle_dropbox_files()


def export_mongodb_to_csv_and_upload_to_dropbox():
    """
    Fetches data from MongoDB, creates a CSV file, and uploads it to Dropbox.
    Handles Dropbox access token refresh.
    """
    global dbx

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
        filename = "meteosarria_data.csv"
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

        # Manejar los archivos en Dropbox antes de subir el nuevo
        handle_dropbox_files()

        # Upload to Dropbox
        logging.info(f"Uploading CSV to Dropbox...")
        dropbox_path = f"/{filename}"

        with open(filepath, "rb") as f:
            try:
                dbx.files_upload(f.read(), dropbox_path, mode=WriteMode("overwrite"))
            except AuthError:
                logging.info("AuthError durante la subida. Refreshing token.")
                new_access_token = refresh_dropbox_token()
                dbx = create_new_dbx_instance(new_access_token)
                # Retry the upload
                with open(filepath, "rb") as f:
                    dbx.files_upload(f.read(), dropbox_path, mode=WriteMode("overwrite"))

        logging.info(f"CSV file uploaded to Dropbox: {dropbox_path}")

    except Exception as e:
        logging.error(f"Error during export/upload process: {e}")

    finally:
        # Clean up temporary file
        if "filepath" in locals() and os.path.exists(filepath):
            os.remove(filepath)
            logging.info(f"Temporary file {filepath} removed.")


# --- Main Execution ---
if __name__ == "__main__":
    export_mongodb_to_csv_and_upload_to_dropbox()