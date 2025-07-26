from flask import Blueprint, jsonify
import logging
import os
import requests
from datetime import datetime
import pytz
from pymongo import MongoClient

# Fetch data from AEMET
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
            'User-Agent': 'Python-AEMET-Client/2.0'
        })
        
        # ID de la estación de Burgos Villafría
        self.estacion_villafria = "2331"
    
    def obtener_datos_estacion_villafria(self):
        """
        Obtiene los datos meteorológicos de la estación de Villafría
        
        Returns:
            dict: Datos meteorológicos más recientes o None si hay error
        """
        logger.info(f"Obteniendo datos de Villafría (estación {self.estacion_villafria})...")
        
        # Usar endpoint específico de la estación
        url_estacion = f"{self.base_url}/observacion/convencional/datos/estacion/{self.estacion_villafria}"
        
        try:
            # Primera petición para obtener la URL de los datos
            logger.info(f"Solicitando metadata: {url_estacion}")
            response = self.session.get(url_estacion, timeout=15)
            
            if response.status_code != 200:
                logger.error(f"Error en petición inicial: {response.status_code}")
                logger.error(f"Respuesta: {response.text}")
                return None
            
            # Parsear respuesta JSON
            data = response.json()
            logger.info(f"Respuesta de metadata: {data}")
            
            if 'datos' not in data:
                logger.error("Respuesta no contiene campo 'datos'")
                logger.error(f"Respuesta completa: {data}")
                return None
            
            # Segunda petición para obtener los datos reales
            url_datos = data['datos']
            logger.info(f"Obteniendo datos desde: {url_datos}")
            
            response_datos = self.session.get(url_datos, timeout=30)
            
            if response_datos.status_code != 200:
                logger.error(f"Error obteniendo datos reales: {response_datos.status_code}")
                return None
            
            # Parsear datos meteorológicos
            observaciones = response_datos.json()
            logger.info(f"Registros recibidos: {len(observaciones)}")
            
            if len(observaciones) == 0:
                logger.error("No se recibieron datos de la estación")
                return None
            
            # Tomar el registro más reciente (último en la lista)
            observacion_actual = observaciones[-1] if isinstance(observaciones, list) else observaciones
            
            # Verificar que sea de Villafría
            station_id = observacion_actual.get('idema')
            station_name = observacion_actual.get('ubi', 'Sin nombre')
            
            logger.info(f"Datos de: {station_id} - {station_name}")
            logger.info(f"Hora observación: {observacion_actual.get('fint', 'N/A')}")
            
            return observacion_actual
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return None

    def calcular_max_min_diarias(self, observaciones):
        """
        Calcula las máximas y mínimas diarias reales desde las 00:00 hasta la actual
        
        Args:
            observaciones (list): Lista de observaciones horarias
            
        Returns:
            tuple: (max_temp_diaria, min_temp_diaria)
        """
        from datetime import datetime, timezone
        
        # Obtener fecha actual
        hoy = datetime.now().date()
        
        # Filtrar observaciones de hoy
        observaciones_hoy = []
        for obs in observaciones:
            try:
                # Parsear fecha de observación (los datos crudos de AEMET usan 'fint')
                fecha_str = obs.get('fint', '')
                if 'T' in fecha_str:
                    fecha_str = fecha_str.replace('Z', '+00:00')
                    fecha_obs = datetime.fromisoformat(fecha_str)
                    # Convertir a hora local (UTC+1 en España)
                    fecha_obs = fecha_obs.replace(tzinfo=timezone.utc).astimezone()
                    
                    # Verificar que sea de hoy
                    if fecha_obs.date() == hoy:
                        observaciones_hoy.append(obs)
            except Exception as e:
                logger.warning(f"Error parseando fecha: {e}")
                continue
        
        logger.info(f"Observaciones de hoy: {len(observaciones_hoy)}")
        
        # Calcular máximas y mínimas
        temperaturas = []
        for obs in observaciones_hoy:
            temp = obs.get('ta')
            if temp is not None and temp != "":
                try:
                    temperaturas.append(float(temp))
                except (ValueError, TypeError):
                    continue
        
        if temperaturas:
            max_temp_diaria = max(temperaturas)
            min_temp_diaria = min(temperaturas)
            logger.info(f"Temperaturas de hoy: {len(temperaturas)} registros, Max: {max_temp_diaria}°C, Min: {min_temp_diaria}°C")
            return max_temp_diaria, min_temp_diaria
        else:
            logger.warning("No se encontraron temperaturas válidas para hoy")
            return None, None

    def obtener_datos_completos_villafria(self):
        """
        Obtiene los datos meteorológicos completos de Villafría con cálculo de máximas/minimas diarias
        
        Returns:
            dict: Datos meteorológicos con máximas/minimas diarias calculadas
        """
        logger.info(f"Obteniendo datos completos de Villafría (estación {self.estacion_villafria})...")
        
        # Usar endpoint específico de la estación
        url_estacion = f"{self.base_url}/observacion/convencional/datos/estacion/{self.estacion_villafria}"
        
        try:
            # Primera petición para obtener la URL de los datos
            logger.info(f"Solicitando metadata: {url_estacion}")
            response = self.session.get(url_estacion, timeout=15)
            
            if response.status_code != 200:
                logger.error(f"Error en petición inicial: {response.status_code}")
                logger.error(f"Respuesta: {response.text}")
                return None
            
            # Parsear respuesta JSON
            data = response.json()
            
            if 'datos' not in data:
                logger.error("Respuesta no contiene campo 'datos'")
                return None
            
            # Segunda petición para obtener los datos reales
            url_datos = data['datos']
            logger.info(f"Obteniendo datos desde: {url_datos}")
            
            response_datos = self.session.get(url_datos, timeout=30)
            
            if response_datos.status_code != 200:
                logger.error(f"Error obteniendo datos reales: {response_datos.status_code}")
                return None
            
            # Parsear datos meteorológicos
            observaciones = response_datos.json()
            logger.info(f"Registros recibidos: {len(observaciones)}")
            
            if len(observaciones) == 0:
                logger.error("No se recibieron datos de la estación")
                return None
            
            # Tomar el registro más reciente
            observacion_actual = observaciones[-1] if isinstance(observaciones, list) else observaciones
            
            # Calcular máximas y mínimas diarias
            max_temp_diaria, min_temp_diaria = self.calcular_max_min_diarias(observaciones)
            
            # Agregar las máximas y mínimas calculadas al registro actual
            if max_temp_diaria is not None:
                observacion_actual['tamax_diaria'] = max_temp_diaria
            if min_temp_diaria is not None:
                observacion_actual['tamin_diaria'] = min_temp_diaria
            
            return observacion_actual
            
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
        
        # Obtener datos de la estación de Burgos Villafría con máximas/minimas diarias
        datos_estacion = aemet_api.obtener_datos_completos_villafria()
        
        if not datos_estacion:
            logger.error("No se pudieron obtener los datos de la estación")
            return jsonify({"error": "No se pudieron obtener los datos meteorológicos"}), 500

        # Obtener el último registro de lluvia acumulada
        last_rain_record = rain_collection.find_one(sort=[("date", -1)])
        total_rain = last_rain_record['accumulated'] if last_rain_record else 0

        # Usar la fecha de observación que ya viene formateada de AEMET
        fecha_obs = datos_estacion.get('observation_time', '')
        logger.info(f"Fecha de observación: {fecha_obs}")
        if not fecha_obs:
            fecha_obs = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Calcular dirección del viento en texto
        wind_direction_text = ""
        wind_direction = datos_estacion.get("dv", 0)
        if isinstance(wind_direction, (int, float)):
            direcciones = [
                "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
            ]
            index = round(float(wind_direction) / 22.5) % 16
            wind_direction_text = direcciones[index]

        # Convertir velocidad del viento a km/h
        wind_speed_kmh = 0
        wind_speed = datos_estacion.get("vv", 0)
        if isinstance(wind_speed, (int, float)):
            wind_speed_kmh = round(float(wind_speed) * 3.6, 1)

        # Estructurar los datos de respuesta
        weather_data = {
            "temperature": datos_estacion.get("ta", 0),  # Temperatura actual
            "humidity": datos_estacion.get("hr", 0),     # Humedad relativa
            "pressure": datos_estacion.get("pres", 0),   # Presión
            "wind_speed": datos_estacion.get("vv", 0),   # Velocidad del viento (m/s)
            "wind_speed_kmh": wind_speed_kmh,            # Velocidad del viento (km/h)
            "wind_direction": datos_estacion.get("dv", 0), # Dirección del viento (grados)
            "wind_direction_text": wind_direction_text,   # Dirección del viento (texto)
            "weather_overview": "Datos de AEMET",  # Descripción genérica
            "day_rain": datos_estacion.get("prec", 0),   # Precipitación
            "total_rain": round(total_rain, 1),           # Lluvia acumulada de MongoDB
            "max_temperature": datos_estacion.get("tamax_diaria", datos_estacion.get("tamax", datos_estacion.get("ta", 0))), # Temp máxima diaria calculada
            "min_temperature": datos_estacion.get("tamin_diaria", datos_estacion.get("tamin", datos_estacion.get("ta", 0))), # Temp mínima diaria calculada
            "clouds": 0,  # AEMET no proporciona datos de nubes
            "icon": "01d",  # Icono por defecto
            "description": "Datos de estación AEMET",
            "timestamp": datetime.now(pytz.UTC).isoformat(),
            "observation_time": fecha_obs,
            "station_id": datos_estacion.get("idema", ""),
            "station_name": datos_estacion.get("ubi", "Burgos Villafría"),
            # Campos adicionales de AEMET
            "visibility": datos_estacion.get("vis", 0),   # Visibilidad (km)
            "insolation": datos_estacion.get("inso", 0),  # Insolación (W/m²)
            "dew_point": datos_estacion.get("tpr", 0),    # Punto de rocío (°C)
            "soil_temperature": datos_estacion.get("ts", 0), # Temperatura suelo (°C)
            "soil_temp_5cm": datos_estacion.get("tss5cm", 0), # Temp suelo 5cm (°C)
            "soil_temp_20cm": datos_estacion.get("tss20cm", 0), # Temp suelo 20cm (°C)
            "wind_gust": datos_estacion.get("vmax", 0)    # Racha máxima (m/s)
        }

        return jsonify(weather_data)

    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500