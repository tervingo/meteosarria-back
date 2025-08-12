#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para actualizar automáticamente la colección 'burgos_historico_temps'
con los últimos datos de temperatura disponibles en la API de AEMET.

El script:
1. Obtiene la última fecha disponible en la BD
2. Consulta la API de AEMET desde esa fecha hasta hoy
3. Actualiza la BD con los nuevos datos
4. Registra todas las operaciones en logs

Autor: Generado para meteosarria.com
Fecha: 2025-08-10
"""

import os
import logging
import requests
import json
from datetime import datetime, timedelta, date
import pytz
from pymongo import MongoClient
from typing import Optional, List, Dict, Any
import time
import sys

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('update_burgos_historico.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BurgosHistoricoUpdater:
    def __init__(self, api_key: str, mongodb_uri: str):
        """
        Inicializa el actualizador de datos históricos de Burgos
        
        Args:
            api_key (str): Clave de API de AEMET
            mongodb_uri (str): URI de conexión a MongoDB
        """
        self.api_key = api_key
        self.mongodb_uri = mongodb_uri
        self.base_url = "https://opendata.aemet.es/opendata/api"
        self.estacion_villafria = "2331"
        self.spain_tz = pytz.timezone('Europe/Madrid')
        
        # Configurar sesión HTTP
        self.session = requests.Session()
        self.session.headers.update({
            'api_key': self.api_key,
            'Accept': 'application/json',
            'User-Agent': 'MeteosarriaBurgosUpdater/1.0'
        })
        
        # Conectar a MongoDB
        self.client = None
        self.db = None
        self.collection = None
        self._connect_mongodb()
    
    def _connect_mongodb(self):
        """Establece conexión con MongoDB"""
        try:
            self.client = MongoClient(self.mongodb_uri)
            self.db = self.client.meteosarria
            self.collection = self.db.burgos_historico_temps
            logger.info("Conectado a MongoDB correctamente")
        except Exception as e:
            logger.error(f"Error conectando a MongoDB: {e}")
            raise
    
    def get_ultima_fecha_bd(self) -> Optional[date]:
        """
        Obtiene la última fecha disponible en la base de datos
        
        Returns:
            date: Última fecha en la BD o None si no hay datos
        """
        try:
            # Buscar el documento con la fecha más reciente
            ultimo_doc = self.collection.find().sort("fecha_datetime", -1).limit(1)
            ultimo_doc = list(ultimo_doc)
            
            if ultimo_doc:
                fecha_datetime = ultimo_doc[0]['fecha_datetime']
                ultima_fecha = fecha_datetime.date()
                logger.info(f"Última fecha en BD: {ultima_fecha}")
                return ultima_fecha
            else:
                logger.warning("No se encontraron datos en la BD")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo última fecha de BD: {e}")
            return None
    
    def obtener_datos_aemet_rango(self, fecha_inicio: date, fecha_fin: date) -> List[Dict[Any, Any]]:
        """
        Obtiene datos de AEMET para un rango de fechas
        
        Args:
            fecha_inicio (date): Fecha de inicio
            fecha_fin (date): Fecha de fin
            
        Returns:
            List[Dict]: Lista de observaciones meteorológicas
        """
        datos_completos = []
        
        # AEMET limita las consultas a períodos cortos, consultamos día por día
        fecha_actual = fecha_inicio
        
        while fecha_actual <= fecha_fin:
            logger.info(f"Consultando datos AEMET para {fecha_actual}")
            
            try:
                datos_dia = self._obtener_datos_aemet_dia(fecha_actual)
                if datos_dia:
                    datos_completos.extend(datos_dia)
                
                # Pausa para evitar límites de rate limiting
                time.sleep(3)
                
                fecha_actual += timedelta(days=1)
                
            except Exception as e:
                logger.error(f"Error obteniendo datos para {fecha_actual}: {e}")
                fecha_actual += timedelta(days=1)
                continue
        
        logger.info(f"Total de registros obtenidos de AEMET: {len(datos_completos)}")
        return datos_completos
    
    def _obtener_datos_aemet_dia(self, fecha: date) -> Optional[List[Dict[Any, Any]]]:
        """
        Obtiene datos de AEMET para un día específico
        
        Args:
            fecha (date): Fecha para consultar
            
        Returns:
            List[Dict]: Datos del día o None si hay error
        """
        fecha_str = fecha.strftime("%Y-%m-%d")
        
        # Endpoint para datos climatológicos diarios
        url = f"{self.base_url}/valores/climatologicos/diarios/datos/fechaini/{fecha_str}T00:00:00UTC/fechafin/{fecha_str}T23:59:59UTC/estacion/{self.estacion_villafria}"
        
        # Retry logic para manejar rate limiting
        max_retries = 3
        for intento in range(max_retries):
            try:
                # Primera petición para obtener URL de datos
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 404:
                    logger.warning(f"No hay datos disponibles para {fecha}")
                    return None
                elif response.status_code == 429:
                    if intento < max_retries - 1:
                        wait_time = 60 + (intento * 30)  # Esperar 60, 90, 120 segundos
                        logger.warning(f"Rate limit alcanzado para {fecha}, esperando {wait_time} segundos antes del reintento {intento + 2}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Rate limit alcanzado para {fecha} después de {max_retries} intentos")
                        return None
                elif response.status_code != 200:
                    logger.error(f"Error en petición AEMET ({response.status_code}): {response.text}")
                    return None
                
                # Si llegamos aquí, la petición fue exitosa
                break
                
            except requests.exceptions.RequestException as e:
                if intento < max_retries - 1:
                    logger.warning(f"Error de conexión para {fecha}, reintentando en 5 segundos...")
                    time.sleep(5)
                    continue
                else:
                    logger.error(f"Error de conexión consultando AEMET para {fecha}: {e}")
                    return None
            
        try:
            data = response.json()
            
            if 'datos' not in data:
                logger.warning(f"Respuesta AEMET sin campo 'datos' para {fecha}")
                return None
            
            # Segunda petición para obtener los datos reales
            url_datos = data['datos']
            response_datos = self.session.get(url_datos, timeout=30)
            
            if response_datos.status_code != 200:
                logger.error(f"Error obteniendo datos reales para {fecha}: {response_datos.status_code}")
                return None
            
            observaciones = response_datos.json()
            
            if not observaciones:
                logger.warning(f"Sin observaciones para {fecha}")
                return None
            
            # Filtrar solo datos de Villafría (por si acaso)
            datos_villafria = [obs for obs in observaciones if obs.get('indicativo') == self.estacion_villafria or obs.get('idema') == self.estacion_villafria]
            
            logger.info(f"Obtenidas {len(datos_villafria)} observaciones para {fecha}")
            return datos_villafria
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON para {fecha}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado consultando {fecha}: {e}")
            return None
    
    def procesar_y_guardar_datos(self, datos_aemet: List[Dict[Any, Any]]) -> int:
        """
        Procesa los datos de AEMET y los guarda en la BD
        
        Args:
            datos_aemet (List[Dict]): Datos obtenidos de AEMET
            
        Returns:
            int: Número de registros insertados
        """
        registros_insertados = 0
        registros_procesados = {}  # Para evitar duplicados por fecha
        
        for observacion in datos_aemet:
            try:
                # Extraer fecha y temperaturas (formato climatológico diario)
                fecha_str = observacion.get('fecha', '')  # Ya viene en formato YYYY-MM-DD
                temp_maxima = observacion.get('tmax')
                temp_minima = observacion.get('tmin')
                
                if not fecha_str:
                    logger.warning("Observación sin fecha válida, omitiendo")
                    continue
                
                # Convertir temperaturas a float (manejar formato español con comas)
                try:
                    if temp_maxima is not None and temp_maxima != '':
                        temp_maxima = float(str(temp_maxima).replace(',', '.'))
                    else:
                        temp_maxima = None
                except (ValueError, TypeError):
                    temp_maxima = None
                
                try:
                    if temp_minima is not None and temp_minima != '':
                        temp_minima = float(str(temp_minima).replace(',', '.'))
                    else:
                        temp_minima = None
                except (ValueError, TypeError):
                    temp_minima = None
                
                # Saltar si no hay datos de temperatura
                if temp_maxima is None and temp_minima is None:
                    continue
                
                # Para evitar duplicados, tomar la mejor observación por día
                if fecha_str in registros_procesados:
                    # Si ya tenemos datos para este día, mantener el que tenga más información
                    registro_existente = registros_procesados[fecha_str]
                    temp_max_existente = registro_existente.get('temp_maxima')
                    temp_min_existente = registro_existente.get('temp_minima')
                    
                    # Preferir registro que tenga ambas temperaturas
                    if (temp_maxima is not None and temp_minima is not None) and \
                       (temp_max_existente is None or temp_min_existente is None):
                        # El nuevo registro es mejor
                        pass
                    else:
                        # Mantener el existente
                        continue
                
                # Crear fecha datetime
                fecha_date = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                fecha_datetime = self.spain_tz.localize(datetime.combine(fecha_date, datetime.min.time()))
                
                # Crear documento
                documento = {
                    'fecha': fecha_str,
                    'fecha_datetime': fecha_datetime,
                    'temp_maxima': temp_maxima,
                    'temp_minima': temp_minima,
                    'imported_at': datetime.now(self.spain_tz),
                    'source': 'AEMET_API_update',
                    'estacion_id': self.estacion_villafria,
                    'observacion_completa': observacion  # Guardar observación completa para referencia
                }
                
                registros_procesados[fecha_str] = documento
                
            except Exception as e:
                logger.error(f"Error procesando observación: {e}")
                continue
        
        # Insertar registros únicos en la BD
        if registros_procesados:
            try:
                # Verificar que no existan ya en la BD
                registros_a_insertar = []
                
                for fecha_str, documento in registros_procesados.items():
                    # Verificar si ya existe
                    existe = self.collection.find_one({'fecha': fecha_str})
                    if not existe:
                        registros_a_insertar.append(documento)
                    else:
                        logger.info(f"Registro para {fecha_str} ya existe, omitiendo")
                
                if registros_a_insertar:
                    resultado = self.collection.insert_many(registros_a_insertar)
                    registros_insertados = len(resultado.inserted_ids)
                    logger.info(f"Insertados {registros_insertados} nuevos registros en BD")
                else:
                    logger.info("No hay registros nuevos para insertar")
                
            except Exception as e:
                logger.error(f"Error insertando datos en BD: {e}")
        
        return registros_insertados
    
    def actualizar_datos(self):
        """
        Función principal que ejecuta todo el proceso de actualización
        """
        logger.info("=== INICIANDO ACTUALIZACION DE DATOS HISTORICOS DE BURGOS ===")
        
        try:
            # 1. Obtener última fecha en BD
            ultima_fecha_bd = self.get_ultima_fecha_bd()
            
            if ultima_fecha_bd is None:
                logger.error("No se pudo obtener la ultima fecha de la BD")
                return False
            
            # 2. Calcular rango de fechas a consultar
            fecha_inicio = ultima_fecha_bd + timedelta(days=1)
            fecha_fin = date.today()
            
            logger.info(f"Consultando datos desde {fecha_inicio} hasta {fecha_fin}")
            
            if fecha_inicio > fecha_fin:
                logger.info("La BD ya esta actualizada, no hay nuevos datos que consultar")
                return True
            
            # 3. Obtener datos de AEMET
            datos_aemet = self.obtener_datos_aemet_rango(fecha_inicio, fecha_fin)
            
            if not datos_aemet:
                logger.warning("No se obtuvieron datos de AEMET")
                return False
            
            # 4. Procesar y guardar datos
            registros_insertados = self.procesar_y_guardar_datos(datos_aemet)
            
            logger.info(f"=== ACTUALIZACION COMPLETADA: {registros_insertados} registros nuevos ===")
            return True
            
        except Exception as e:
            logger.error(f"Error en proceso de actualización: {e}")
            return False
        finally:
            if self.client:
                self.client.close()
                logger.info("Conexión MongoDB cerrada")

def main():
    """
    Función principal del script
    """
    # Configuración
    API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqNGFsb25zb0BnbWFpbC5jb20iLCJqdGkiOiI2NWE3MWZmOS1jMjgzLTRmOTMtYjE5NS05YzQ1ZjBmNzI1YTgiLCJpc3MiOiJBRU1FVCIsImlhdCI6MTczOTUyNTYxOSwidXNlcklkIjoiNjVhNzFmZjktYzI4My00ZjkzLWIxOTUtOWM0NWYwZjcyNWE4Iiwicm9sZSI6IiJ9.6cauQ28EPJdrTPc5YIRl0UrIh_76uUP6WYYvIgJKU88"
    MONGODB_URI = "mongodb+srv://tervingo:mig.langar.inn@gagnagunnur.okrh1.mongodb.net/meteosarria"
    
    if not API_KEY or API_KEY == "TU_API_KEY_AQUI":
        logger.error("API key de AEMET no configurada")
        sys.exit(1)
    
    if not MONGODB_URI:
        logger.error("URI de MongoDB no configurada")
        sys.exit(1)
    
    # Crear actualizador y ejecutar
    updater = BurgosHistoricoUpdater(API_KEY, MONGODB_URI)
    
    success = updater.actualizar_datos()
    
    if success:
        logger.info("Script completado exitosamente")
        sys.exit(0)
    else:
        logger.error("Script completado con errores")
        sys.exit(1)

if __name__ == "__main__":
    main()