import os
import logging
import csv
from datetime import datetime
import pytz
from pymongo import MongoClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('import_villafria_historico.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MongoDB connection
try:
    mongo_uri = "mongodb+srv://tervingo:mig.langar.inn@gagnagunnur.okrh1.mongodb.net/meteosarria"
    if not mongo_uri:
        raise ValueError("MONGODB_URI environment variable not set")

    client = MongoClient(mongo_uri)
    db = client.meteosarria
    temps_collection = db.burgos_historico_temps
    logger.info("Connected to MongoDB")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")
    raise

def import_historical_temperatures():
    """Import historical temperature data from CSV to MongoDB"""
    try:
        # Path to the CSV file
        csv_file_path = os.path.join(os.path.dirname(__file__), '..', 'villafria_temperaturas_historicas.csv')
        
        if not os.path.exists(csv_file_path):
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
        
        # Spain timezone
        spain_tz = pytz.timezone('Europe/Madrid')
        
        # Clear existing data (optional - remove if you want to preserve existing data)
        result = temps_collection.delete_many({})
        logger.info(f"Cleared {result.deleted_count} existing records")
        
        # Read and import CSV data
        imported_count = 0
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                try:
                    # Parse the date
                    fecha = datetime.strptime(row['fecha'], '%Y-%m-%d')
                    fecha = spain_tz.localize(fecha)
                    
                    # Parse temperatures (handle potential empty values)
                    temp_maxima = float(row['temp_maxima']) if row['temp_maxima'] else None
                    temp_minima = float(row['temp_minima']) if row['temp_minima'] else None
                    
                    # Create document
                    document = {
                        'fecha': row['fecha'],  # Store as string for easy querying
                        'fecha_datetime': fecha,  # Store as datetime for date operations
                        'temp_maxima': temp_maxima,
                        'temp_minima': temp_minima,
                        'imported_at': datetime.now(spain_tz),
                        'source': 'villafria_temperaturas_historicas.csv'
                    }
                    
                    # Insert document
                    temps_collection.insert_one(document)
                    imported_count += 1
                    
                    if imported_count % 1000 == 0:
                        logger.info(f"Imported {imported_count} records...")
                        
                except Exception as e:
                    logger.error(f"Error processing row {row}: {e}")
                    continue
        
        logger.info(f"Successfully imported {imported_count} temperature records")
        
        # Create index on fecha for better query performance
        temps_collection.create_index("fecha")
        temps_collection.create_index("fecha_datetime")
        logger.info("Created indexes on fecha fields")
        
    except Exception as e:
        logger.error(f"Error importing historical temperatures: {e}")
        raise

if __name__ == '__main__':
    try:
        logger.info("Starting import of historical temperature data from Villafría")
        import_historical_temperatures()
        logger.info("Finished importing historical temperature data")
    except Exception as e:
        logger.error(f"Import script failed: {e}")
        raise