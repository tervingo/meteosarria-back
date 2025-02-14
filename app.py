from flask import Flask, jsonify, request, Response
from livedata import get_meteohub_parameter
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timedelta
import logging
import os
import pytz
import requests
from typing import Dict, Any, Tuple, Optional

app = Flask(__name__)
CORS(app)

# Configuración para la API de Burgos Villafría
AEMET_API_KEY = os.getenv('AEMET_API_KEY', "TU_API_KEY_AQUI")
BURGOS_STATION_ID = "2331"  # ID de la estación de Burgos/Villafría
BASE_URL = "https://opendata.aemet.es/opendata/api"




# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# MongoDB connection
try:
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise ValueError("MONGODB_URI environment variable not set")

    client = MongoClient(mongo_uri)
    db = client.meteosarria
    collection = db.data
    logging.info("Connected to MongoDB")
except Exception as e:
    logging.error(f"Error connecting to MongoDB: {e}")

@app.route('/api/live')
def live_weather():
    try:
        live_data = {
            "external_temperature": get_meteohub_parameter("ext_temp"),
            "internal_temperature": get_meteohub_parameter("int_temp"),
            "humidity": get_meteohub_parameter("hum"),
            "wind_direction": get_meteohub_parameter("wind_dir"),
            "wind_speed": get_meteohub_parameter("wind_speed"),
            "gust_speed": get_meteohub_parameter("gust_speed"),
            "pressure": get_meteohub_parameter("press"),
            "current_rain_rate": get_meteohub_parameter("cur_rain"),
            "total_rain": get_meteohub_parameter("total_rain"),
            "solar_radiation": get_meteohub_parameter("rad"),
            "uv_index": get_meteohub_parameter("uv"),
        }

        if any(value is None for value in live_data.values()):
            return jsonify({"error": "Could not retrieve complete live weather data"}), 500

        return jsonify(live_data)
    except Exception as e:
        logging.error(f"Error in live_weather endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500

#-----------------------
# api/meteo-data AP
#-----------------------

@app.route('/api/meteo-data')
def temperature_data():
    try:
        logging.info("meteo-data endpoint called")
        time_range = request.args.get('timeRange', '24h')
        end_time = datetime.now(pytz.timezone('Europe/Madrid'))
        
        if time_range == '24h':
            start_time = end_time - timedelta(hours=24)
            interval = 1
        elif time_range == '48h':
            start_time = end_time - timedelta(hours=48)
            interval = 2
        elif time_range == '7d':
            start_time = end_time - timedelta(days=7)
            interval = 6
        else:
            return jsonify({"error": "Invalid time range"}), 400

        # Obtener los días a consultar
        days_to_query = []
        current_day = start_time
        while current_day <= end_time:
            day_str = current_day.strftime("%d-%m-%Y")
            days_to_query.append(day_str)
            current_day += timedelta(days=1)

        logging.info(f"Días a consultar: {days_to_query}")

        # Construir consulta para obtener documentos por día
        query = {
            "$or": [
                {"timestamp": {"$regex": f"^{day}"}} for day in days_to_query
            ]
        }
        
        logging.info(f"Query: {query}")
        
        # Obtener documentos
        all_data = list(collection.find(query).sort("timestamp", 1))
        logging.info(f"Documentos encontrados antes de filtrar por hora: {len(all_data)}")
        
        if all_data:
            logging.info(f"Primer documento: {all_data[0]['timestamp']}")
            logging.info(f"Último documento: {all_data[-1]['timestamp']}")

        # Función para convertir timestamp string a datetime
        def parse_timestamp(ts):
            return datetime.strptime(ts, "%d-%m-%Y %H:%M")

        # Convertir las fechas límite a datetime
        start_dt = parse_timestamp(start_time.strftime("%d-%m-%Y %H:%M"))
        end_dt = parse_timestamp(end_time.strftime("%d-%m-%Y %H:%M"))
        
        # Filtrar los datos usando objetos datetime para la comparación
        filtered_data = [
            doc for doc in all_data 
            if start_dt <= parse_timestamp(doc['timestamp']) <= end_dt
        ]
        
        logging.info(f"Documentos después de filtrar por hora: {len(filtered_data)}")
        if filtered_data:
            logging.info(f"Primer documento filtrado: {filtered_data[0]['timestamp']}")
            logging.info(f"Último documento filtrado: {filtered_data[-1]['timestamp']}")
            logging.info(f"Hora inicio filtro: {start_dt}")
            logging.info(f"Hora fin filtro: {end_dt}")

        # Aplicar sampling
        sampled_data = filtered_data[::interval]
        
        # Preparar para JSON
        for entry in sampled_data:
            entry["_id"] = str(entry["_id"])
        
        return jsonify(sampled_data)
        
    except Exception as e:
        logging.error(f"Error fetching meteo data: {e}", exc_info=True)
        logging.error("Error detallado:", exc_info=True)
        return jsonify({"error": str(e)}), 500

#-----------------------
# api/burgos (AEMET Villafría)
#-----------------------

class AEMETError(Exception):
    """Excepción personalizada para errores de la API de AEMET"""
    pass

def get_aemet_data(endpoint: str) -> Tuple[Dict[str, Any], int]:
    """
    Realiza una petición a la API de AEMET
    """
    headers = {
        'api_key': AEMET_API_KEY,
        'Accept': 'application/json'
    }
    
    try:
        logger.debug(f"Realizando petición a AEMET: {BASE_URL}/{endpoint}")
        # Primera petición para obtener la URL de los datos
        response = requests.get(f"{BASE_URL}/{endpoint}", headers=headers)
        response.raise_for_status()
        
        data = response.json()
        logger.debug(f"Respuesta inicial de AEMET: {data}")
        
        data_url = data.get('datos')
        if not data_url:
            logger.error("No se encontró URL de datos en la respuesta")
            raise AEMETError("No se obtuvo URL de datos en la respuesta")
            
        # Segunda petición para obtener los datos reales
        logger.debug(f"Obteniendo datos de: {data_url}")
        data_response = requests.get(data_url)
        data_response.raise_for_status()
        
        return data_response.json(), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error en la petición HTTP: {str(e)}")
        raise AEMETError(f"Error en la petición HTTP: {str(e)}")
    except ValueError as e:
        logger.error(f"Error al procesar JSON: {str(e)}")
        raise AEMETError(f"Error al procesar JSON: {str(e)}")

@app.route('/api/burgos', methods=['GET'])
def get_burgos_weather():
    """
    Endpoint para obtener datos meteorológicos actuales de Burgos/Villafría
    """
    try:
        logger.info("Iniciando petición de datos de Burgos")
        
        if AEMET_API_KEY == "TU_API_KEY_AQUI":
            logger.error("API key no configurada")
            return jsonify({
                'status': 'error',
                'message': 'API key de AEMET no configurada'
            }), 500
        
        # Obtener datos de la estación específica
        endpoint = f"observacion/convencional/datos/estacion/{BURGOS_STATION_ID}"
        raw_data, status_code = get_aemet_data(endpoint)
        
        logger.debug(f"Datos recibidos de AEMET: {raw_data}")
        
        if not raw_data:
            return jsonify({
                'status': 'error',
                'message': 'No hay datos disponibles para la estación'
            }), 404
            
        # Procesar datos - tomar la última medición
        latest_data = raw_data[0] if raw_data else None
        
        if not latest_data:
            return jsonify({
                'status': 'error',
                'message': 'No hay datos recientes disponibles'
            }), 404
            
        processed_data = {
            'temperature': latest_data.get('ts'),  # Cambiado de 'ta' a 'ts' para temperatura superficial
            'temperature_air': latest_data.get('ta'),  # Añadimos también la temperatura del aire
            'humidity': latest_data.get('hr'),
            'wind_speed': latest_data.get('vv'),
            'wind_direction': latest_data.get('dv'),
            'pressure': latest_data.get('pres'),
            'timestamp': latest_data.get('fint'),
            'station_name': 'Burgos/Villafría'
        }
        
        return jsonify({
            'status': 'success',
            'data': processed_data,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except AEMETError as e:
        logger.error(f"Error de AEMET: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error interno del servidor: {str(e)}"
        }), 500


#---------------------------
# Debug
#---------------------------

@app.route('/api/debug/last-records')
def debug_last_records():
    try:
        # Obtener los últimos 5 registros
        last_records = list(collection.find().sort("timestamp", -1).limit(5))
        
        # Convertir ObjectId a string
        for record in last_records:
            record["_id"] = str(record["_id"])
            
        return jsonify({
            "count": len(last_records),
            "records": last_records
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)