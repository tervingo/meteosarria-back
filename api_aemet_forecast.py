"""
Previsión diaria de AEMET (predicción específica por municipio) para
Burgos y Barcelona, en el mismo formato de tabla que api_ai_forecast.py.
"""

from flask import Blueprint, jsonify
import logging
import os
from datetime import datetime, timedelta
import requests
import pytz
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

aemet_forecast_bp = Blueprint('aemet_forecast', __name__)

# Códigos de municipio (INE) usados por la API de predicción de AEMET
MUNICIPIOS = {
    'burgos': {'code': '09059', 'label': 'Burgos'},
    'barcelona': {'code': '08019', 'label': 'Barcelona'},
}

CACHE_HOURS = float(os.getenv('AEMET_FORECAST_CACHE_HOURS', 6))
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

_cache = {}


def _get_cached(city):
    entry = _cache.get(city)
    if not entry:
        return None
    if datetime.now(pytz.timezone('Europe/Madrid')) - entry['updated_at'] > timedelta(hours=CACHE_HOURS):
        return None
    return entry['payload']


def _set_cached(city, payload):
    _cache[city] = {
        'payload': payload,
        'updated_at': datetime.now(pytz.timezone('Europe/Madrid')),
    }


def _fetch_aemet_dias(municipio_code):
    """Obtiene la lista de días de la predicción diaria de AEMET para un municipio."""
    api_key = os.getenv('AEMET_API_KEY')
    if not api_key:
        raise RuntimeError('AEMET_API_KEY no configurada')

    url = f"https://opendata.aemet.es/opendata/api/prediccion/especifica/municipio/diaria/{municipio_code}"
    meta_response = requests.get(url, params={'api_key': api_key}, timeout=15)
    meta_response.raise_for_status()
    meta = meta_response.json()

    if 'datos' not in meta:
        raise RuntimeError(f"Respuesta inesperada de AEMET: {meta}")

    data_response = requests.get(meta['datos'], timeout=15)
    data_response.raise_for_status()
    data = data_response.json()
    return data[0]['prediccion']['dia']


def _build_rows(dias):
    rows = []
    for dia in dias:
        fecha_str = dia.get('fecha', '')[:10]
        if not fecha_str:
            continue
        date_obj = datetime.strptime(fecha_str, '%Y-%m-%d')

        temperatura = dia.get('temperatura', {})
        probs = dia.get('probPrecipitacion', [])
        prob_values = [
            int(p['value']) for p in probs
            if str(p.get('value', '')).strip().isdigit()
        ]

        rows.append({
            'day': DIAS_SEMANA[date_obj.weekday()],
            'date': date_obj.strftime('%d/%m'),
            'tmax': temperatura.get('maxima'),
            'tmin': temperatura.get('minima'),
            'precip_prob': max(prob_values) if prob_values else 0,
        })
    return rows


@aemet_forecast_bp.route('/api/aemet-forecast/<city>')
def get_aemet_forecast(city):
    city = city.lower()
    if city not in MUNICIPIOS:
        return jsonify({'error': f"Ciudad desconocida: {city}"}), 404

    cached = _get_cached(city)
    if cached:
        return jsonify(cached)

    try:
        info = MUNICIPIOS[city]
        dias = _fetch_aemet_dias(info['code'])
        rows = _build_rows(dias)

        payload = {
            'city': city,
            'label': info['label'],
            'updated_at': datetime.now(pytz.timezone('Europe/Madrid')).isoformat(),
            'rows': rows,
        }
        _set_cached(city, payload)
        return jsonify(payload)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error obteniendo predicción AEMET para {city}: {e}")
        return jsonify({'error': 'No se pudo obtener la previsión de AEMET', 'detail': str(e)}), 502
    except Exception as e:
        logger.error(f"Error inesperado en aemet-forecast/{city}: {e}")
        return jsonify({'error': 'Error interno', 'detail': str(e)}), 500


@aemet_forecast_bp.route('/api/aemet-forecast/<city>/clear-cache', methods=['POST'])
def clear_aemet_forecast_cache(city):
    city = city.lower()
    _cache.pop(city, None)
    return jsonify({'status': 'success', 'message': f'Caché AEMET de {city} borrada'})
