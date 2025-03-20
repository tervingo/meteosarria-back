from pymongo import MongoClient
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_pressure_values():
    try:
        # Conectar a MongoDB
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            raise ValueError("MONGODB_URI environment variable not set")

        client = MongoClient(mongo_uri)
        db = client.meteosarria
        collection = db.data

        # Fecha límite
        end_date = "20-03-25 23:20"

        # Encontrar y actualizar documentos
        query = {
            "timestamp": {"$lte": end_date},
            "pressure": {"$exists": True}
        }

        # Contador para documentos actualizados
        updated_count = 0
        total_docs = collection.count_documents(query)
        logger.info(f"Found {total_docs} documents to update")

        # Actualizar documentos
        cursor = collection.find(query)
        for doc in cursor:
            try:
                old_pressure = float(doc['pressure'])
                new_pressure = old_pressure + 12.9
                
                result = collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"pressure": str(new_pressure)}}
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    if updated_count % 100 == 0:  # Log cada 100 actualizaciones
                        logger.info(f"Updated {updated_count}/{total_docs} documents")
                
            except (ValueError, KeyError) as e:
                logger.error(f"Error processing document {doc.get('timestamp', 'unknown')}: {e}")
                continue

        logger.info(f"Update completed. Total documents updated: {updated_count}")

    except Exception as e:
        logger.error(f"Error updating pressure values: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    update_pressure_values() 