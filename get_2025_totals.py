#!/usr/bin/env python3
"""
Script para obtener los totales de precipitación de 2025
para Sarrià (Barcelona) y Burgos desde la base de datos MongoDB
"""

import os
import logging
from pymongo import MongoClient

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, continue without it
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
try:
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        # Fallback: usar URI hardcodeada solo para esta consulta (no recomendado para producción)
        logger.warning("MONGODB_URI not found in environment variables, using fallback URI")
        mongo_uri = "mongodb+srv://tervingo:mig.langar.inn@gagnagunnur.okrh1.mongodb.net/meteosarria"

    client = MongoClient(mongo_uri)
    db = client.meteosarria
    logger.info("Connected to MongoDB")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")
    raise

def get_2025_total_sarria():
    """Obtener el total de precipitación de 2025 para Sarrià/Barcelona"""
    try:
        rain_collection = db.rain_accumulation
        
        # Buscar el último registro de 2025 (31 de diciembre de 2025)
        # Los registros tienen formato de fecha 'YYYY-MM-DD'
        last_2025_record = rain_collection.find_one(
            {"date": {"$regex": "^2025-"}},
            sort=[("date", -1)]
        )
        
        if not last_2025_record:
            logger.warning("No se encontraron registros de 2025 para Sarrià")
            return None
        
        # Buscar específicamente el registro del 31 de diciembre de 2025
        dec_31_2025 = rain_collection.find_one({"date": "2025-12-31"})
        
        if dec_31_2025:
            total = dec_31_2025.get('accumulated', 0)
            logger.info(f"Total de precipitación 2025 para Sarrià (31 dic): {total:.2f} mm")
            return total
        else:
            # Si no hay registro del 31 de diciembre, usar el último registro de 2025
            last_date = last_2025_record.get('date', '')
            if last_date.startswith('2025-'):
                total = last_2025_record.get('accumulated', 0)
                logger.info(f"Total de precipitación 2025 para Sarrià (último registro {last_date}): {total:.2f} mm")
                return total
            else:
                logger.warning(f"Último registro no es de 2025: {last_date}")
                return None
                
    except Exception as e:
        logger.error(f"Error obteniendo total de 2025 para Sarrià: {e}")
        return None

def get_2025_total_burgos():
    """Obtener el total de precipitación de 2025 para Burgos"""
    try:
        rain_collection = db.burgos_rain_accumulation
        
        # Buscar el último registro de 2025 (31 de diciembre de 2025)
        last_2025_record = rain_collection.find_one(
            {"date": {"$regex": "^2025-"}},
            sort=[("date", -1)]
        )
        
        if not last_2025_record:
            logger.warning("No se encontraron registros de 2025 para Burgos")
            return None
        
        # Buscar específicamente el registro del 31 de diciembre de 2025
        dec_31_2025 = rain_collection.find_one({"date": "2025-12-31"})
        
        if dec_31_2025:
            total = dec_31_2025.get('accumulated', 0)
            logger.info(f"Total de precipitación 2025 para Burgos (31 dic): {total:.2f} mm")
            return total
        else:
            # Si no hay registro del 31 de diciembre, usar el último registro de 2025
            last_date = last_2025_record.get('date', '')
            if last_date.startswith('2025-'):
                total = last_2025_record.get('accumulated', 0)
                logger.info(f"Total de precipitación 2025 para Burgos (último registro {last_date}): {total:.2f} mm")
                return total
            else:
                logger.warning(f"Último registro no es de 2025: {last_date}")
                return None
                
    except Exception as e:
        logger.error(f"Error obteniendo total de 2025 para Burgos: {e}")
        return None

def main():
    """Función principal"""
    print("\n" + "="*60)
    print("Consulta de totales de precipitación 2025")
    print("="*60 + "\n")
    
    # Obtener totales
    sarria_total = get_2025_total_sarria()
    burgos_total = get_2025_total_burgos()
    
    print("\n" + "-"*60)
    print("RESULTADOS:")
    print("-"*60)
    
    if sarria_total is not None:
        print(f"Sarria (Barcelona) 2025: {sarria_total:.2f} mm")
        print(f"   Valor para constants.js: RAIN_2025_CANBRUIXA = {sarria_total:.1f};")
    else:
        print("ERROR: No se pudo obtener el total de Sarria")
    
    if burgos_total is not None:
        print(f"Burgos 2025: {burgos_total:.2f} mm")
        print(f"   Valor para constants.js: RAIN_2025_BURGOS = {burgos_total:.1f};")
    else:
        print("ERROR: No se pudo obtener el total de Burgos")
    
    print("-"*60 + "\n")
    
    # También mostrar información adicional
    if sarria_total is not None or burgos_total is not None:
        print("Para actualizar constants.js, usa estos valores:")
        print()
        if sarria_total is not None:
            print(f"export const RAIN_2025_CANBRUIXA = {sarria_total:.1f}; // Total precipitation for Sarrià in 2025 (mm)")
        if burgos_total is not None:
            print(f"export const RAIN_2025_BURGOS = {burgos_total:.1f}; // Total precipitation for Burgos in 2025 (mm)")
        print()

if __name__ == '__main__':
    main()
