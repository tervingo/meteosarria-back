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

# Configuración para la API de AEMET
FABRA_STATION_ID = "0200E"  # ID de la estación del Observatorio Fabra

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

# ... existing code ...

@app.route('/api/live')
def live_weather():
    try:
        # Get current date in Madrid timezone
        madrid_tz = pytz.timezone('Europe/Madrid')
        now = datetime.now(madrid_tz)
        today = now.strftime("%d-%m-%Y")
        
        # Get today's temperature records
        today_records = list(collection.find({
            "timestamp": {"$regex": f"^{today}"}
        }).sort("timestamp", 1))
        
        # Calculate min and max temperatures for today
        today_temps = [float(record['external_temperature']) 
                      for record in today_records 
                      if 'external_temperature' in record 
                      and record['external_temperature'] is not None]
        
        max_temp = round(max(today_temps), 1) if today_temps else None
        min_temp = round(min(today_temps), 1) if today_temps else None

        live_data = {
            "external_temperature": get_meteohub_parameter("ext_temp"),
            "max_temperature": max_temp,
            "min_temperature": min_temp,
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
# api/yearly-data
#-----------------------

@app.route('/api/yearly-data')
def yearly_temperature_data():
    try:
        logging.info("yearly-data endpoint called")
        
        # Definir zona horaria
        madrid_tz = pytz.timezone('Europe/Madrid')
        
        # Obtener el año actual y crear fechas con zona horaria
        now = datetime.now(madrid_tz)
        current_year = now.year
        
        # Crear start_date con zona horaria
        start_date = madrid_tz.localize(datetime(current_year, 1, 1))
        end_date = now

        logging.info(f"Consultando datos desde {start_date.strftime('%d-%m-%Y')} hasta {end_date.strftime('%d-%m-%Y')}")

        # Obtener los días a consultar
        days_to_query = []
        current_day = start_date
        while current_day <= end_date:
            day_str = current_day.strftime("%d-%m-%Y")
            days_to_query.append(day_str)
            current_day += timedelta(days=1)

        # Construir consulta para obtener documentos por día
        query = {
            "$or": [
                {"timestamp": {"$regex": f"^{day}"}} for day in days_to_query
            ]
        }
        
        logging.info(f"Consultando {len(days_to_query)} días")
        
        # Obtener documentos
        all_data = list(collection.find(query).sort("timestamp", 1))
        logging.info(f"Encontrados {len(all_data)} registros")
        
        # Procesar datos para obtener máximas, mínimas y medias por día
        daily_data = {}
        
        for entry in all_data:
            try:
                # Parsear timestamp y convertir a zona horaria de Madrid
                timestamp = datetime.strptime(entry['timestamp'], "%d-%m-%Y %H:%M")
                timestamp = madrid_tz.localize(timestamp)
                date_key = timestamp.strftime("%Y-%m-%d")
                
                if date_key not in daily_data:
                    daily_data[date_key] = {
                        'temps': [],
                        'date': date_key
                    }
                
                if 'external_temperature' in entry and entry['external_temperature'] is not None:
                    temp = float(entry['external_temperature'])
                    # Filtrar valores atípicos (opcional)
                    if -40 <= temp <= 50:  # Rango razonable de temperaturas
                        daily_data[date_key]['temps'].append(temp)
                
            except (ValueError, TypeError) as e:
                logging.warning(f"Error procesando entrada {entry['timestamp']}: {str(e)}")
                continue

        # Calcular estadísticas diarias
        processed_data = []
        for date_key, data in daily_data.items():
            if data['temps']:
                temps = data['temps']
                processed_data.append({
                    'date': date_key,
                    'max': round(max(temps), 1),
                    'min': round(min(temps), 1),
                    'mean': round(sum(temps) / len(temps), 1)
                })

        # Ordenar por fecha
        processed_data.sort(key=lambda x: x['date'])
        
        logging.info(f"Procesados datos para {len(processed_data)} días")
        
        return jsonify({
            'status': 'success',
            'data': processed_data
        })
        
    except Exception as e:
        logging.error(f"Error fetching yearly data: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

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

# OpenWeatherMap API endpoint for Burgos
@app.route('/api/burgos-weather')
def get_burgos_weather():
    try:
        OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
        if not OPENWEATHER_API_KEY:
            logger.error("OpenWeather API key not found in environment variables")
            return jsonify({'error': 'API key not configured'}), 500

        BURGOS_LAT = 42.3439
        BURGOS_LON = -3.6970
        
        url = f'https://api.openweathermap.org/data/2.5/weather?lat={BURGOS_LAT}&lon={BURGOS_LON}&units=metric&appid={OPENWEATHER_API_KEY}&lang=es'
        
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        weather_data = {
            'temperature': data['main']['temp'],
            'humidity': data['main']['humidity'],
            'pressure': data['main']['pressure'],
            'windSpeed': data['wind']['speed'] * 3.6,  # Convert m/s to km/h
            'windDirection': data['wind']['deg'],
            'description': data['weather'][0]['description'],
            'icon': data['weather'][0]['icon'],
            'timestamp': data['dt']
        }

        logger.debug(f"Successfully fetched Burgos weather data: {weather_data}")
        return jsonify(weather_data)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Burgos weather data: {str(e)}")
        return jsonify({'error': 'Failed to fetch weather data'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_burgos_weather: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

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

@app.route('/api/barcelona-rain')
def get_barcelona_rain():
    try:
        logger.info("barcelona-rain endpoint called")
        
        # Verificar API key
        if not AEMET_API_KEY or AEMET_API_KEY == "TU_API_KEY_AQUI":
            error_msg = "AEMET API key not configured"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500

        # Obtener fecha actual en zona horaria de Madrid
        madrid_tz = pytz.timezone('Europe/Madrid')
        today = datetime.now(madrid_tz)
        
        # Intentar con fechas de enero primero
        dates_to_try = [
            today.replace(month=1, day=31),
            today.replace(month=1, day=30),
            today.replace(month=1, day=15),
            today.replace(month=2, day=28),
            today.replace(month=2, day=27)
        ]
        daily_rain = 0
        daily_data_found = False
        last_available_date = None

        for try_date in dates_to_try:
            if daily_data_found:
                break

            logger.debug(f"Trying date: {try_date.strftime('%Y-%m-%d')} for daily data")
            
            daily_endpoint = f"valores/climatologicos/diarios/datos/fechaini/{try_date.strftime('%Y-%m-%d')}T00:00:00UTC/fechafin/{try_date.strftime('%Y-%m-%d')}T23:59:59UTC/estacion/{FABRA_STATION_ID}"
            
            try:
                logger.debug(f"Requesting daily data from AEMET: {daily_endpoint}")
                logger.debug(f"Using API key: {AEMET_API_KEY[:5]}...")  # Log solo los primeros 5 caracteres
                
                daily_response = requests.get(f"{BASE_URL}/{daily_endpoint}", headers={
                    'api_key': AEMET_API_KEY,
                    'Accept': 'application/json'
                })
                daily_response.raise_for_status()
                response_json = daily_response.json()
                logger.debug(f"AEMET daily response: {response_json}")
                
                # Verificar si la respuesta indica un error
                if response_json.get('estado') == 404:
                    logger.warning(f"AEMET returned 404 for date {try_date.strftime('%Y-%m-%d')}: {response_json.get('descripcion')}")
                    continue

                if not response_json.get('datos'):
                    logger.warning(f"No data URL in AEMET response for date {try_date.strftime('%Y-%m-%d')}")
                    continue

                daily_data_response = requests.get(response_json['datos'])
                daily_data_response.raise_for_status()
                daily_data = daily_data_response.json()
                logger.debug(f"Received daily data: {daily_data}")
                
                if daily_data and len(daily_data) > 0:
                    daily_rain = convert_spanish_decimal(daily_data[0].get('prec', 0))
                    if daily_rain is not None:
                        daily_data_found = True
                        last_available_date = try_date
                        logger.info(f"Found valid daily rain data: {daily_rain} for date {try_date.strftime('%Y-%m-%d')}")
            except Exception as e:
                logger.warning(f"Error getting data for {try_date.strftime('%Y-%m-%d')}: {str(e)}")
                continue

        # Obtener datos anuales (meses completos)
        yearly_endpoint = f"valores/climatologicos/mensualesanuales/datos/anioini/{today.year}/aniofin/{today.year}/estacion/{FABRA_STATION_ID}"
        monthly_rain = 0
        current_month_rain = 0
        
        try:
            logger.debug(f"Requesting yearly data from AEMET: {yearly_endpoint}")
            yearly_response = requests.get(f"{BASE_URL}/{yearly_endpoint}", headers={
                'api_key': AEMET_API_KEY,
                'Accept': 'application/json'
            })
            yearly_response.raise_for_status()
            yearly_response_json = yearly_response.json()
            logger.debug(f"AEMET yearly response: {yearly_response_json}")
            
            # Verificar si la respuesta indica un error
            if yearly_response_json.get('estado') == 404:
                logger.warning(f"AEMET returned 404 for yearly data: {yearly_response_json.get('descripcion')}")
                # Intentar con una petición diaria para todo enero
                try:
                    jan_endpoint = f"valores/climatologicos/diarios/datos/fechaini/{today.year}-01-01T00:00:00UTC/fechafin/{today.year}-01-31T23:59:59UTC/estacion/{FABRA_STATION_ID}"
                    logger.debug(f"Trying to get January data: {jan_endpoint}")
                    jan_response = requests.get(f"{BASE_URL}/{jan_endpoint}", headers={
                        'api_key': AEMET_API_KEY,
                        'Accept': 'application/json'
                    })
                    jan_response.raise_for_status()
                    jan_json = jan_response.json()
                    logger.debug(f"January response: {jan_json}")
                    
                    if jan_json.get('datos'):
                        jan_data_response = requests.get(jan_json['datos'])
                        jan_data_response.raise_for_status()
                        jan_data = jan_data_response.json()
                        logger.debug(f"January data: {jan_data}")
                        
                        if jan_data:
                            monthly_rain = sum(convert_spanish_decimal(day.get('prec', 0)) for day in jan_data)
                            logger.info(f"Calculated January rain from daily data: {monthly_rain}")
                except Exception as e:
                    logger.warning(f"Error getting January data: {str(e)}")
            elif yearly_response_json.get('datos'):
                yearly_data_response = requests.get(yearly_response_json['datos'])
                yearly_data_response.raise_for_status()
                yearly_data = yearly_data_response.json()
                logger.debug(f"Received yearly data: {yearly_data}")
                
                if yearly_data and len(yearly_data) > 0:
                    try:
                        # Sumar solo los meses completos (excluyendo el mes actual)
                        monthly_rain = sum(
                            convert_spanish_decimal(month.get('p_mes', 0))
                            for month in yearly_data 
                            if int(month.get('mes', 0)) < today.month
                        )
                        logger.info(f"Sum of complete months rain: {monthly_rain}")

                        # Obtener la lluvia del mes actual
                        if today.day > 1:  # Solo si no estamos en el primer día del mes
                            # Calcular la lluvia del mes actual hasta ayer
                            month_start = today.replace(day=1)
                            yesterday = today - timedelta(days=1)
                            
                            current_month_endpoint = f"valores/climatologicos/diarios/datos/fechaini/{month_start.strftime('%Y-%m-%d')}T00:00:00UTC/fechafin/{yesterday.strftime('%Y-%m-%d')}T23:59:59UTC/estacion/{FABRA_STATION_ID}"
                            
                            logger.debug(f"Requesting current month data from AEMET: {current_month_endpoint}")
                            current_month_response = requests.get(f"{BASE_URL}/{current_month_endpoint}", headers={
                                'api_key': AEMET_API_KEY,
                                'Accept': 'application/json'
                            })
                            current_month_response.raise_for_status()
                            current_month_json = current_month_response.json()
                            logger.debug(f"AEMET current month response: {current_month_json}")
                            
                            if current_month_json.get('estado') != 404 and current_month_json.get('datos'):
                                current_month_data_response = requests.get(current_month_json['datos'])
                                current_month_data_response.raise_for_status()
                                current_month_data = current_month_data_response.json()
                                logger.debug(f"Received current month data: {current_month_data}")
                                
                                # Sumar todas las precipitaciones diarias del mes actual
                                current_month_rain = sum(
                                    convert_spanish_decimal(day.get('prec', 0))
                                    for day in current_month_data
                                )
                                logger.info(f"Current month rain (until yesterday): {current_month_rain}")
                            else:
                                logger.warning("No data available for current month")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error calculating rain totals: {str(e)}")
            else:
                logger.warning("No data URL in AEMET yearly response")
        except Exception as e:
            logger.warning(f"Error getting yearly data: {str(e)}")
        
        # Calcular el total anual: meses completos + mes actual hasta ayer + día actual
        yearly_rain = monthly_rain + current_month_rain + (daily_rain or 0)
        
        response_data = {
            'daily_rain': float(daily_rain or 0),
            'yearly_rain': yearly_rain,
            'monthly_rain': monthly_rain,  # lluvia de meses completos
            'current_month_rain': current_month_rain,  # lluvia del mes actual hasta ayer
            'station_name': 'Observatorio Fabra',
            'station_id': FABRA_STATION_ID,
            'timestamp': today.strftime('%Y-%m-%d %H:%M:%S'),
            'last_available_date': last_available_date.strftime('%Y-%m-%d') if last_available_date else None
        }
        
        logger.info(f"Returning barcelona-rain data: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        error_msg = f"Unexpected error in get_barcelona_rain: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return jsonify({'error': error_msg}), 500

def convert_spanish_decimal(value: str) -> float:
    """Convierte un número en formato español (con coma decimal) a float."""
    try:
        if value is None:
            return 0.0
        # Reemplazar coma por punto y convertir a float
        return float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)