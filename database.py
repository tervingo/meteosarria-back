from pymongo import MongoClient
import logging
import os
from threading import local

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Thread-local storage for MongoDB connections
_thread_local = local()

def get_mongo_client():
    """Get a MongoDB client instance that's safe for use with Gunicorn"""
    if not hasattr(_thread_local, 'mongo_client'):
        try:
            mongo_uri = os.getenv("MONGODB_URI")
            if not mongo_uri:
                raise ValueError("MONGODB_URI environment variable not set")

            _thread_local.mongo_client = MongoClient(mongo_uri)
            logging.info("Created new MongoDB client")
        except Exception as e:
            logging.error(f"Error creating MongoDB client: {e}")
            raise
    
    return _thread_local.mongo_client

def get_db():
    """Get the database instance"""
    client = get_mongo_client()
    return client.meteosarria

def get_collection():
    """Get the collection instance"""
    db = get_db()
    return db.data

# Initialize connection on module import
try:
    client = get_mongo_client()
    db = get_db()
    collection = get_collection()
    logging.info("Connected to MongoDB")
except Exception as e:
    logging.error(f"Error connecting to MongoDB: {e}")
    raise 