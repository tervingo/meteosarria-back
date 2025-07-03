#!/usr/bin/env python3
"""
Script para verificar el estado de las colecciones históricas
"""

import os
from pymongo import MongoClient
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_historico_collections():
    """Verificar el estado de las colecciones históricas"""
    try:
        # Conectar a MongoDB
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            logger.error("MONGODB_URI environment variable not set")
            return False
        
        client = MongoClient(mongo_uri)
        db = client['meteosarria']
        
        logger.info("Connected to MongoDB")
        
        # Verificar colecciones existentes
        collections = db.list_collection_names()
        logger.info(f"Available collections: {collections}")
        
        # Verificar colecciones históricas específicas
        historico_collections = ['historico_intervalos', 'historico_diario']
        
        for collection_name in historico_collections:
            if collection_name in collections:
                collection = db[collection_name]
                count = collection.count_documents({})
                logger.info(f"Collection '{collection_name}': {count} documents")
                
                if count > 0:
                    # Mostrar algunos ejemplos
                    sample = collection.find().limit(1)
                    for doc in sample:
                        logger.info(f"Sample document from {collection_name}:")
                        logger.info(f"  Keys: {list(doc.keys())}")
                        if 'timestamp' in doc:
                            logger.info(f"  Timestamp: {doc['timestamp']}")
                        if 'fecha' in doc:
                            logger.info(f"  Fecha: {doc['fecha']}")
                        if 'temperatura' in doc:
                            logger.info(f"  Temperatura: {doc['temperatura']}")
            else:
                logger.warning(f"Collection '{collection_name}' does not exist")
        
        # Verificar colección principal de datos
        if 'data' in collections:
            data_collection = db['data']
            count = data_collection.count_documents({})
            logger.info(f"Main data collection: {count} documents")
            
            if count > 0:
                # Mostrar rango de fechas
                first_doc = data_collection.find().sort("timestamp", 1).limit(1)
                last_doc = data_collection.find().sort("timestamp", -1).limit(1)
                
                for doc in first_doc:
                    logger.info(f"First document timestamp: {doc.get('timestamp', 'N/A')}")
                for doc in last_doc:
                    logger.info(f"Last document timestamp: {doc.get('timestamp', 'N/A')}")
        
        client.close()
        return True
        
    except Exception as e:
        logger.error(f"Error checking collections: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Checking histórico collections...")
    success = check_historico_collections()
    
    if success:
        print("✅ Check completed successfully")
    else:
        print("❌ Check failed") 