"""
Tabla única de previsión por día que compara, columna a columna, varias
fuentes para Burgos y Barcelona: Open-Meteo (+ comentario de Claude),
AEMET, y los modelos individuales ECMWF / GFS / ICON (también vía
Open-Meteo, pidiendo cada modelo por separado en vez del blend por defecto).

Reutiliza las funciones ya existentes de api_ai_forecast.py y
api_aemet_forecast.py en vez de duplicar la lógica de fetch/caché.
"""

from flask import Blueprint, jsonify
import logging
import os
from datetime import datetime, timedelta
import requests
import pytz
from dotenv import load_dotenv

import api_ai_forecast as ai_forecast
import api_aemet_forecast as aemet_forecast
from forecast_common import day_and_date

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

forecast_comparison_bp = Blueprint('forecast_comparison', __name__)

FORECAST_DAYS = 8
CACHE_HOURS = float(os.getenv('FORECAST_COMPARISON_CACHE_HOURS', 3))

# Modelos individuales pedidos a Open-Meteo (en vez del blend "best_match")
MODELS = {
    'ecmwf': 'ecmwf_ifs025',
    'gfs': 'gfs_seamless',
    'icon': 'icon_seamless',
}

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


def _fetch_models_daily(lat, lon):
    """Pide a Open-Meteo los mismos días pero para 3 modelos individuales."""
    url = 'https://api.open-meteo.com/v1/forecast'
    params = {
        'latitude': lat,
        'longitude': lon,
        'daily': 'temperature_2m_max,temperature_2m_min',
        'timezone': 'Europe/Madrid',
        'forecast_days': FORECAST_DAYS,
        'models': ','.join(MODELS.values()),
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response.json()['daily']


def _build_models_by_date(daily):
    """date_iso -> {'ecmwf': {tmax,tmin}, 'gfs': {...}, 'icon': {...}}"""
    dates = daily.get('time', [])
    by_date = {}
    for key, suffix in MODELS.items():
        tmax_list = daily.get(f'temperature_2m_max_{suffix}', [])
        tmin_list = daily.get(f'temperature_2m_min_{suffix}', [])
        for i, date_str in enumerate(dates):
            tmax = tmax_list[i] if i < len(tmax_list) else None
            tmin = tmin_list[i] if i < len(tmin_list) else None
            by_date.setdefault(date_str, {})[key] = {
                'tmax': round(tmax, 1) if tmax is not None else None,
                'tmin': round(tmin, 1) if tmin is not None else None,
            }
    return by_date


@forecast_comparison_bp.route('/api/forecast-comparison/<city>')
def get_forecast_comparison(city):
    city = city.lower()
    if city not in ai_forecast.CITIES or city not in aemet_forecast.MUNICIPIOS:
        return jsonify({'error': f"Ciudad desconocida: {city}"}), 404

    cached = _get_cached(city)
    if cached:
        return jsonify(cached)

    try:
        om_info = ai_forecast.CITIES[city]
        aemet_info = aemet_forecast.MUNICIPIOS[city]

        daily_om = ai_forecast._fetch_open_meteo(om_info['lat'], om_info['lon'])
        om_rows = ai_forecast._build_rows(daily_om)
        comment, comment_error = ai_forecast._generate_comment(om_info['label'], om_rows)

        aemet_dias = aemet_forecast._fetch_aemet_dias(aemet_info['code'])
        aemet_rows = aemet_forecast._build_rows(aemet_dias)
        aemet_by_date = {r['date']: r for r in aemet_rows}

        daily_models = _fetch_models_daily(om_info['lat'], om_info['lon'])
        models_by_date = _build_models_by_date(daily_models)

        rows = []
        for i, om_row in enumerate(om_rows):
            date_iso = daily_om['time'][i]
            model_data = models_by_date.get(date_iso, {})
            aemet_row = aemet_by_date.get(om_row['date'])

            rows.append({
                'day': om_row['day'],
                'date': om_row['date'],
                'open_meteo': {
                    'tmax': om_row['tmax'], 'tmin': om_row['tmin'], 'precip_prob': om_row['precip_prob'],
                },
                'aemet': {
                    'tmax': aemet_row['tmax'], 'tmin': aemet_row['tmin'], 'precip_prob': aemet_row['precip_prob'],
                } if aemet_row else None,
                'ecmwf': model_data.get('ecmwf'),
                'gfs': model_data.get('gfs'),
                'icon': model_data.get('icon'),
            })

        payload = {
            'city': city,
            'label': om_info['label'],
            'updated_at': datetime.now(pytz.timezone('Europe/Madrid')).isoformat(),
            'rows': rows,
            'comment': comment,
        }
        if comment_error:
            payload['comment_error'] = comment_error

        _set_cached(city, payload)
        return jsonify(payload)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error obteniendo comparación de previsión para {city}: {e}")
        stale = _cache.get(city)
        if stale:
            logger.warning(f"Sirviendo comparación cacheada (caducada) de {city} por fallo de una fuente")
            stale_payload = dict(stale['payload'])
            stale_payload['stale'] = True
            stale_payload['stale_reason'] = str(e)
            return jsonify(stale_payload)
        return jsonify({'error': 'No se pudo obtener la comparación de previsión', 'detail': str(e)}), 502
    except Exception as e:
        logger.error(f"Error inesperado en forecast-comparison/{city}: {e}")
        return jsonify({'error': 'Error interno', 'detail': str(e)}), 500


@forecast_comparison_bp.route('/api/forecast-comparison/<city>/clear-cache', methods=['POST'])
def clear_forecast_comparison_cache(city):
    city = city.lower()
    _cache.pop(city, None)
    return jsonify({'status': 'success', 'message': f'Caché de comparación de {city} borrada'})
