from flask import Blueprint, jsonify
import logging
import os
import requests
from datetime import datetime, timedelta
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
        # Conectar a la nueva colección de Google Weather
        from database import get_db
        db = get_db()
        gw_collection = db.gw_burgos_data
        
        # Obtener el último registro de Google Weather para Burgos Centro
        latest_record = gw_collection.find_one(sort=[('timestamp', -1)])
        
        if not latest_record:
            logger.error("No se encontraron datos de Google Weather para Burgos Centro")
            return jsonify({"error": "No hay datos meteorológicos disponibles"}), 500

        # Extraer datos de Google Weather
        gw_data = latest_record.get('google_weather_burgos_center', {})
        raw_data = gw_data.get('raw_data', {})
        
        logger.info(f"Datos de Google Weather: {raw_data}")

        # Obtener el último registro de lluvia acumulada
        last_rain_record = rain_collection.find_one(sort=[("date", -1)])
        total_rain = last_rain_record['accumulated'] if last_rain_record else 0

        # Fecha de observación
        observation_time = latest_record.get('timestamp', datetime.now())
        if isinstance(observation_time, str):
            observation_time = datetime.fromisoformat(observation_time.replace('Z', '+00:00'))
        fecha_obs = observation_time.strftime("%Y-%m-%d %H:%M:%S")

        # Extraer campos directamente del raw_data (estructura real de Google Weather)
        temperature = 0
        humidity = 0
        pressure = 0
        wind_speed = 0
        wind_direction = 0
        weather_description = "Google Weather"
        clouds = 0
        
        # Temperatura
        if 'temperature' in raw_data and isinstance(raw_data['temperature'], dict):
            temperature = raw_data['temperature'].get('degrees', 0)
            
        # Humedad relativa
        if 'relativeHumidity' in raw_data:
            humidity = raw_data['relativeHumidity']
            
        # Presión atmosférica
        if 'airPressure' in raw_data and isinstance(raw_data['airPressure'], dict):
            pressure = raw_data['airPressure'].get('meanSeaLevelMillibars', 0)
            
        # Viento
        if 'wind' in raw_data and isinstance(raw_data['wind'], dict):
            if 'speed' in raw_data['wind'] and isinstance(raw_data['wind']['speed'], dict):
                wind_speed = raw_data['wind']['speed'].get('value', 0)
            if 'direction' in raw_data['wind'] and isinstance(raw_data['wind']['direction'], dict):
                wind_direction = raw_data['wind']['direction'].get('degrees', 0)
                
        # Descripción del tiempo
        if 'weatherCondition' in raw_data and isinstance(raw_data['weatherCondition'], dict):
            if 'description' in raw_data['weatherCondition'] and isinstance(raw_data['weatherCondition']['description'], dict):
                weather_description = raw_data['weatherCondition']['description'].get('text', 'Google Weather')
                
        # Cobertura de nubes
        if 'cloudCover' in raw_data:
            clouds = raw_data['cloudCover']
            
        # Precipitación diaria del histórico
        day_rain = 0
        if 'currentConditionsHistory' in raw_data and isinstance(raw_data['currentConditionsHistory'], dict):
            if 'qpf' in raw_data['currentConditionsHistory'] and isinstance(raw_data['currentConditionsHistory']['qpf'], dict):
                day_rain = raw_data['currentConditionsHistory']['qpf'].get('quantity', 0)

        # Calcular máximas y mínimas del histórico diario si está disponible
        max_temperature = temperature
        min_temperature = temperature
        
        if 'currentConditionsHistory' in raw_data:
            history = raw_data['currentConditionsHistory']
            if isinstance(history, dict):
                # Extraer temperatura máxima
                if 'maxTemperature' in history:
                    max_temp_obj = history['maxTemperature']
                    if isinstance(max_temp_obj, dict) and 'degrees' in max_temp_obj:
                        try:
                            max_temperature = float(max_temp_obj['degrees'])
                        except (ValueError, TypeError):
                            pass
                
                # Extraer temperatura mínima  
                if 'minTemperature' in history:
                    min_temp_obj = history['minTemperature']
                    if isinstance(min_temp_obj, dict) and 'degrees' in min_temp_obj:
                        try:
                            min_temperature = float(min_temp_obj['degrees'])
                        except (ValueError, TypeError):
                            pass
                
                logger.info(f"Temperaturas del histórico diario extraídas: Max: {max_temperature}°C, Min: {min_temperature}°C")

        # Calcular dirección del viento en texto
        wind_direction_text = ""
        if isinstance(wind_direction, (int, float)) and wind_direction > 0:
            direcciones = [
                "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
            ]
            index = round(float(wind_direction) / 22.5) % 16
            wind_direction_text = direcciones[index]

        # Google Weather ya devuelve velocidad del viento en km/h según el JSON
        wind_speed_kmh = round(float(wind_speed), 1) if wind_speed else 0

        # Estructurar los datos de respuesta manteniendo la misma estructura que AEMET
        weather_data = {
            "temperature": temperature,
            "humidity": humidity,
            "pressure": pressure,
            "wind_speed": round(wind_speed / 3.6, 1) if wind_speed else 0,  # Convertir de km/h a m/s para compatibilidad
            "wind_speed_kmh": wind_speed_kmh,
            "wind_direction": wind_direction,
            "wind_direction_text": wind_direction_text,
            "weather_overview": weather_description,
            "day_rain": day_rain,
            "total_rain": round(total_rain, 1),
            "max_temperature": max_temperature,
            "min_temperature": min_temperature,
            "clouds": clouds,
            "icon": "01d",  # Icono por defecto
            "description": weather_description,
            "timestamp": datetime.now(pytz.UTC).isoformat(),
            "observation_time": fecha_obs,
            "station_id": "google_weather",
            "station_name": "Burgos Centro (Google Weather)",
            # Campos adicionales (no disponibles en Google Weather)
            "visibility": 0,
            "insolation": 0,
            "dew_point": 0,
            "soil_temperature": 0,
            "soil_temp_5cm": 0,
            "soil_temp_20cm": 0,
            "wind_gust": 0
        }

        return jsonify(weather_data)

    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500