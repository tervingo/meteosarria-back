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
        self.api_base_url = os.getenv('API_BASE_URL', 'https://meteosarria-back.onrender.com')
        self.mongodb_uri = os.getenv('MONGODB_URI')
        self.db_name = os.getenv('DB_NAME', 'meteosarria')  # Cambiado a meteosarria
        
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
            # Verificar si los índices ya existen antes de crearlos
            existing_indexes_diario = [idx['name'] for idx in self.historico_diario.list_indexes()]
            existing_indexes_intervalos = [idx['name'] for idx in self.historico_intervalos.list_indexes()]
            
            # Crear índice único para datos diarios si no existe
            if 'fecha_1_unique' not in existing_indexes_diario:
                self.historico_diario.create_index("fecha", unique=True, name="fecha_1_unique")
                logger.info("Índice único 'fecha' creado en historico_diario")
            
            # Crear índice único para datos por intervalos si no existe
            if 'timestamp_1_unique' not in existing_indexes_intervalos:
                self.historico_intervalos.create_index("timestamp", unique=True, name="timestamp_1_unique")
                logger.info("Índice único 'timestamp' creado en historico_intervalos")
            
            logger.info("Verificación de índices completada")
        except Exception as e:
            logger.error(f"Error gestionando índices: {e}")
    
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
        """Actualizar colección historico_intervalos (estructura similar al CSV)"""
        now = datetime.now(self.madrid_tz)
        
        # Obtener valores de temperatura y humedad
        temp = live_data.get('external_temperature')
        hum = live_data.get('humidity')
        
        if temp is None or hum is None:
            logger.warning("Datos de temperatura o humedad no disponibles")
            return False
        
        # Preparar documento con la misma estructura que el CSV
        intervalo_doc = {
            "timestamp": now,  # datetime object, no string
            "fecha": now.strftime("%Y-%m-%d"),
            "hora": now.strftime("%H:%M:%S"),
            "año": now.year,
            "mes": now.month,
            "dia": now.day,
            "temperatura": {
                "promedio": round(float(temp), 1),
                "minima": round(float(temp), 1),
                "maxima": round(float(temp), 1)
            },
            "humedad": {
                "promedio": round(float(hum), 1),
                "minima": round(float(hum), 1),
                "maxima": round(float(hum), 1)
            },
            "num_lecturas": 1,
            "intervalo_minutos": 60,  # cada hora
            "datos_corregidos": {
                "temp_corrections": 0,
                "hum_corrections": 0,
                "total_corrections": 0
            },
            "created_at": now
        }
        
        try:
            result = self.historico_intervalos.insert_one(intervalo_doc)
            logger.info(f"Registro de intervalo insertado: {result.inserted_id}")
            return True
        except DuplicateKeyError:
            logger.warning(f"Registro duplicado para timestamp: {now}")
            return False
        except Exception as e:
            logger.error(f"Error insertando registro de intervalo: {e}")
            return False
    
    def update_diario(self, live_data):
        """Actualizar colección historico_diario (estructura similar al CSV)"""
        now = datetime.now(self.madrid_tz)
        fecha_str = now.strftime("%Y-%m-%d")
        
        # Obtener valores actuales
        temp_actual = live_data.get('external_temperature')
        temp_max = live_data.get('max_temperature')
        temp_min = live_data.get('min_temperature')
        hum_actual = live_data.get('humidity')
        
        if temp_actual is None or hum_actual is None:
            logger.warning("Datos de temperatura o humedad no disponibles")
            return False
        
        temp_actual = float(temp_actual)
        hum_actual = float(hum_actual)
        
        # Buscar registro existente del día
        existing_doc = self.historico_diario.find_one({'fecha': fecha_str})
        
        if existing_doc:
            # Actualizar temperaturas máxima y mínima
            current_temp_max = existing_doc.get('temperatura', {}).get('maxima', temp_actual)
            current_temp_min = existing_doc.get('temperatura', {}).get('minima', temp_actual)
            current_hum_max = existing_doc.get('humedad', {}).get('maxima', hum_actual)
            current_hum_min = existing_doc.get('humedad', {}).get('minima', hum_actual)
            
            # Calcular nuevos valores máximos y mínimos
            new_temp_max = max(current_temp_max, temp_actual)
            new_temp_min = min(current_temp_min, temp_actual)
            new_hum_max = max(current_hum_max, hum_actual)
            new_hum_min = min(current_hum_min, hum_actual)
            
            # Si viene temp_max/min del endpoint, usarlos si son mejores
            if temp_max is not None:
                new_temp_max = max(new_temp_max, float(temp_max))
            if temp_min is not None:
                new_temp_min = min(new_temp_min, float(temp_min))
            
            # Calcular promedio (aproximado)
            new_temp_avg = round((new_temp_max + new_temp_min) / 2, 1)
            new_hum_avg = round((new_hum_max + new_hum_min) / 2, 1)
            
            updates = {
                'temperatura': {
                    'promedio': new_temp_avg,
                    'minima': new_temp_min,
                    'maxima': new_temp_max
                },
                'humedad': {
                    'promedio': new_hum_avg,
                    'minima': new_hum_min,
                    'maxima': new_hum_max
                },
                'updated_at': now
            }
            
            try:
                result = self.historico_diario.update_one(
                    {'fecha': fecha_str},
                    {'$set': updates}
                )
                logger.info(f"Registro diario actualizado para {fecha_str}")
                return True
            except Exception as e:
                logger.error(f"Error actualizando registro diario: {e}")
                return False
        else:
            # Crear nuevo registro diario con estructura del CSV
            diario_doc = {
                "timestamp": now.replace(hour=0, minute=0, second=0, microsecond=0),
                "fecha": fecha_str,
                "año": now.year,
                "mes": now.month,
                "dia": now.day,
                "tipo": "resumen_diario",
                "temperatura": {
                    "promedio": round(temp_actual, 1),
                    "minima": float(temp_min) if temp_min is not None else temp_actual,
                    "maxima": float(temp_max) if temp_max is not None else temp_actual
                },
                "humedad": {
                    "promedio": round(hum_actual, 1),
                    "minima": hum_actual,
                    "maxima": hum_actual
                },
                "num_intervalos": 1,
                "datos_corregidos": {
                    "total_corrections": 0
                },
                "created_at": now
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
        """Cerrar conexión a MongoDB de forma segura"""
        try:
            if hasattr(self, 'client'):
                self.client.close()
        except:
            # Ignorar errores al cerrar durante shutdown
            pass

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