from flask import Blueprint, jsonify
import logging
import os
import requests
from datetime import datetime
import pytz
from pymongo import MongoClient


# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
burgos_bp = Blueprint('burgos', __name__)

# MongoDB connection
try:
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise ValueError("MONGODB_URI environment variable not set")

    client = MongoClient(mongo_uri)
    db = client.meteosarria
    rain_collection = db.burgos_rain_accumulation
    logger.info("Connected to MongoDB")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")
    raise

class AEMETWeatherAPI:
    def __init__(self, api_key):
        """
        Inicializa la clase con la API key de AEMET
        """
        self.api_key = api_key
        self.base_url = "https://opendata.aemet.es/opendata/api"
        self.session = requests.Session()
        # Configurar headers por defecto
        self.session.headers.update({
            'api_key': self.api_key,
            'Accept': 'application/json',
            'User-Agent': 'Python-AEMET-Client/1.0'
        })
        
        # ID de la estación de Burgos Villafría
        self.estacion_villafria = "2331"
    
    def obtener_datos_estacion(self, codigo_estacion=None):
        """
        Obtiene los datos meteorológicos de una estación específica
        """
        if codigo_estacion is None:
            codigo_estacion = self.estacion_villafria
            
        logger.info(f"Obteniendo datos de la estación {codigo_estacion}...")
        
        # Paso 1: Obtener todas las observaciones
        url_observaciones = f"{self.base_url}/observacion/convencional/todas"
        
        try:
            # Primera petición para obtener la URL de los datos
            response = self.session.get(url_observaciones, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Error en petición inicial: {response.status_code}")
                return None
            
            # Parsear respuesta JSON
            data = response.json()
            
            if 'datos' not in data:
                logger.error("Respuesta no contiene campo 'datos'")
                return None
            
            # Paso 2: Obtener los datos reales
            url_datos = data['datos']
            logger.info(f"Obteniendo datos desde: {url_datos}")
            
            response_datos = self.session.get(url_datos, timeout=10)
            
            if response_datos.status_code != 200:
                logger.error(f"Error obteniendo datos reales: {response_datos.status_code}")
                return None
            
            # Parsear datos meteorológicos
            observaciones = response_datos.json()
            
            # Buscar la estación específica
            for observacion in observaciones:
                if observacion.get('idema') == codigo_estacion:
                    return observacion
            
            logger.error(f"No se encontró la estación {codigo_estacion}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return None

@burgos_bp.route('/api/burgos-weather', methods=['GET'])
def get_burgos_weather():
    try:
        # Obtener la API key de AEMET
        api_key = os.getenv('AEMET_API_KEY')
        if not api_key:
            logger.error("AEMET_API_KEY no está configurada")
            return jsonify({"error": "API key no configurada"}), 500

        # Crear instancia de la API de AEMET
        aemet_api = AEMETWeatherAPI(api_key)
        
        # Obtener datos de la estación de Burgos Villafría
        datos_estacion = aemet_api.obtener_datos_estacion()
        
        if not datos_estacion:
            logger.error("No se pudieron obtener los datos de la estación")
            return jsonify({"error": "No se pudieron obtener los datos meteorológicos"}), 500

        # Obtener el último registro de lluvia acumulada
        last_rain_record = rain_collection.find_one(sort=[("date", -1)])
        total_rain = last_rain_record['accumulated'] if last_rain_record else 0

        # Convertir fecha de observación
        fecha_obs = datos_estacion.get('fint', '')
        try:
            if 'T' in fecha_obs:
                fecha_obs = fecha_obs.replace('Z', '+00:00')
                fecha_obs = datetime.fromisoformat(fecha_obs)
                fecha_obs = fecha_obs.strftime("%Y-%m-%d %H:%M:%S")
        except:
            fecha_obs = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Estructurar los datos de respuesta
        weather_data = {
            "temperature": datos_estacion.get("ta", 0),  # Temperatura actual
            "humidity": datos_estacion.get("hr", 0),     # Humedad relativa
            "pressure": datos_estacion.get("pres", 0),   # Presión
            "wind_speed": datos_estacion.get("vv", 0),   # Velocidad del viento
            "wind_direction": datos_estacion.get("dv", 0), # Dirección del viento
            "weather_overview": "Datos de AEMET",  # Descripción genérica
            "day_rain": datos_estacion.get("prec", 0),   # Precipitación
            "total_rain": round(total_rain, 1),           # Lluvia acumulada de MongoDB
            "max_temperature": datos_estacion.get("tamax", datos_estacion.get("ta", 0)), # Temp máxima
            "min_temperature": datos_estacion.get("tamin", datos_estacion.get("ta", 0)), # Temp mínima
            "clouds": 0,  # AEMET no proporciona datos de nubes
            "icon": "01d",  # Icono por defecto
            "description": "Datos de estación AEMET",
            "timestamp": datetime.now(pytz.UTC).isoformat(),
            "observation_time": fecha_obs,
            "station_id": datos_estacion.get("idema", ""),
            "station_name": datos_estacion.get("ubi", "Burgos Villafría")
        }

        return jsonify(weather_data)

    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500