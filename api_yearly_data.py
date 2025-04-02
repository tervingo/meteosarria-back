from flask import Blueprint, jsonify
import logging
import os
import pytz
from datetime import datetime, timedelta
from database import collection

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
yearly_bp = Blueprint('yearly', __name__)

@yearly_bp.route('/api/yearly-data')
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