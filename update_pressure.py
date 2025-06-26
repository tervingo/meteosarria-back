import logging
import os
from datetime import datetime, timedelta
import pytz
from database import get_collection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_pressure_values():
    try:
        # Encontrar documentos con pressure que tengan 13 decimales
        # El patrón busca números como 1017.6999999999999
        pattern = r'\d+\.\d{13}$'
        query = {
            "pressure": {"$exists": True},
            "pressure": {"$regex": pattern}
        }

        collection = get_collection()

        # Contador para documentos actualizados
        updated_count = 0
        total_docs = collection.count_documents(query)
        logger.info(f"Found {total_docs} documents with 13 decimal places")

        # Actualizar documentos
        cursor = collection.find(query)
        for doc in cursor:
            try:
                current_pressure = float(doc['pressure'])
                rounded_pressure = round(current_pressure, 1)
                
                result = collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"pressure": str(rounded_pressure)}}
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    if updated_count % 100 == 0:  # Log cada 100 actualizaciones
                        logger.info(f"Updated {updated_count} documents")
                    logger.info(f"Updated pressure from {current_pressure} to {rounded_pressure}")
                
            except (ValueError, KeyError) as e:
                logger.error(f"Error processing document {doc.get('timestamp', 'unknown')}: {e}")
                continue

        logger.info(f"Update completed. Total documents updated: {updated_count}")

    except Exception as e:
        logger.error(f"Error updating pressure values: {e}")

if __name__ == "__main__":
    update_pressure_values() 