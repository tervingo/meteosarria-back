#!/usr/bin/env python3
"""
Script para actualizar datos históricos consultando el endpoint /api/live
Se ejecuta cada 30 minutos via cron job
"""

import requests
import os
import logging
from datetime import datetime, timedelta
import pytz
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import json

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HistoricalDataUpdater:
    def __init__(self):
        # Configuración desde variables de entorno
        self.api_base_url = os.getenv('API_BASE_URL', 'https://meteosarria.com')
        self.mongodb_uri = os.getenv('MONGODB_URI')
        self.db_name = os.getenv('DB_NAME', 'meteorologia')
        
        # Timezone Madrid
        self.madrid_tz = pytz.timezone('Europe/Madrid')
        
        # Conexión a MongoDB
        self.client = MongoClient(self.mongodb_uri)
        self.db = self.client[self.db_name]
        
        # Colecciones
        self.historico_diario = self.db['historico_diario']
        self.historico_intervalos = self.db['historico_intervalos']
        
        # Crear índices únicos si no existen
        self.create_indexes()
    
    def create_indexes(self):
        """Crear índices únicos para evitar duplicados"""
        try:
            # Índice único para datos diarios (fecha)
            self.historico_diario.create_index("fecha", unique=True)
            
            # Índice único para datos por intervalos (timestamp)
            self.historico_intervalos.create_index("timestamp", unique=True)
            
            logger.info("Índices creados correctamente")
        except Exception as e:
            logger.error(f"Error creando índices: {e}")
    
    def get_live_data(self):
        """Obtener datos del endpoint /api/live"""
        try:
            url = f"{self.api_base_url}/api/live"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info("Datos obtenidos del endpoint /api/live")
            return data
            
        except requests.RequestException as e:
            logger.error(f"Error obteniendo datos del endpoint: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando JSON: {e}")
            return None
    
    def update_intervalos(self, live_data):
        """Actualizar colección historico_intervalos (solo temperatura y humedad)"""
        now = datetime.now(self.madrid_tz)
        timestamp = now.strftime("%d-%m-%Y %H:%M:%S")
        
        # Preparar documento para intervalos - SOLO temperatura y humedad
        intervalo_doc = {
            'timestamp': timestamp,
            'external_temperature': live_data.get('external_temperature'),
            'humidity': live_data.get('humidity'),
            'created_at': now.isoformat()
        }
        
        try:
            result = self.historico_intervalos.insert_one(intervalo_doc)
            logger.info(f"Registro de intervalo insertado: {result.inserted_id}")
            return True
        except DuplicateKeyError:
            logger.warning(f"Registro duplicado para timestamp: {timestamp}")
            return False
        except Exception as e:
            logger.error(f"Error insertando registro de intervalo: {e}")
            return False
    
    def update_diario(self, live_data):
        """Actualizar colección historico_diario (solo temperatura y humedad)"""
        now = datetime.now(self.madrid_tz)
        fecha = now.strftime("%d-%m-%Y")
        
        # Obtener temperaturas máxima y mínima actuales
        temp_actual = live_data.get('external_temperature')
        temp_max = live_data.get('max_temperature')
        temp_min = live_data.get('min_temperature')
        
        if temp_actual is None:
            logger.warning("Temperatura actual no disponible")
            return False
        
        # Buscar registro existente del día
        existing_doc = self.historico_diario.find_one({'fecha': fecha})
        
        if existing_doc:
            # Actualizar temperaturas máxima y mínima si es necesario
            updates = {}
            
            if temp_max is not None:
                if 'temp_max' not in existing_doc or temp_max > existing_doc.get('temp_max', -999):
                    updates['temp_max'] = temp_max
            
            if temp_min is not None:
                if 'temp_min' not in existing_doc or temp_min < existing_doc.get('temp_min', 999):
                    updates['temp_min'] = temp_min
            
            # Actualizar temperatura actual y humedad
            updates.update({
                'temp_actual': temp_actual,
                'humidity': live_data.get('humidity'),
                'updated_at': now.isoformat()
            })
            
            if updates:
                try:
                    result = self.historico_diario.update_one(
                        {'fecha': fecha},
                        {'$set': updates}
                    )
                    logger.info(f"Registro diario actualizado para {fecha}")
                    return True
                except Exception as e:
                    logger.error(f"Error actualizando registro diario: {e}")
                    return False
        else:
            # Crear nuevo registro diario - SOLO temperatura y humedad
            diario_doc = {
                'fecha': fecha,
                'temp_actual': temp_actual,
                'temp_max': temp_max or temp_actual,
                'temp_min': temp_min or temp_actual,
                'humidity': live_data.get('humidity'),
                'created_at': now.isoformat(),
                'updated_at': now.isoformat()
            }
            
            try:
                result = self.historico_diario.insert_one(diario_doc)
                logger.info(f"Nuevo registro diario creado: {result.inserted_id}")
                return True
            except Exception as e:
                logger.error(f"Error creando registro diario: {e}")
                return False
    
    def cleanup_old_data(self, days_to_keep=90):
        """Limpiar datos antiguos de historico_intervalos"""
        cutoff_date = datetime.now(self.madrid_tz) - timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.strftime("%d-%m-%Y")
        
        try:
            # Eliminar registros antiguos de intervalos
            result = self.historico_intervalos.delete_many({
                'timestamp': {'$lt': cutoff_str}
            })
            
            if result.deleted_count > 0:
                logger.info(f"Eliminados {result.deleted_count} registros antiguos de intervalos")
            
        except Exception as e:
            logger.error(f"Error limpiando datos antiguos: {e}")
    
    def run(self):
        """Ejecutar actualización completa"""
        logger.info("Iniciando actualización de datos históricos")
        
        # Obtener datos del endpoint
        live_data = self.get_live_data()
        if not live_data:
            logger.error("No se pudieron obtener datos del endpoint")
            return False
        
        # Actualizar ambas colecciones
        success_intervalos = self.update_intervalos(live_data)
        success_diario = self.update_diario(live_data)
        
        # Limpiar datos antiguos (solo una vez al día, a las 00:00)
        now = datetime.now(self.madrid_tz)
        if now.hour == 0 and now.minute < 30:
            self.cleanup_old_data()
        
        if success_intervalos or success_diario:
            logger.info("Actualización completada exitosamente")
            return True
        else:
            logger.error("Falló la actualización")
            return False
    
    def __del__(self):
        """Cerrar conexión a MongoDB"""
        if hasattr(self, 'client'):
            self.client.close()

def main():
    """Función principal"""
    try:
        updater = HistoricalDataUpdater()
        success = updater.run()
        
        if success:
            print("Actualización completada exitosamente")
            exit(0)
        else:
            print("Error en la actualización")
            exit(1)
            
    except Exception as e:
        logger.error(f"Error crítico: {e}")
        print(f"Error crítico: {e}")
        exit(1)

if __name__ == "__main__":
    main()