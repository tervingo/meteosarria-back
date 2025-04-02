from flask import Blueprint, jsonify, request
import logging
import os
import pytz
from datetime import datetime, timedelta
from database import collection

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
meteo_bp = Blueprint('meteo', __name__)

@meteo_bp.route('/api/meteo-data')
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