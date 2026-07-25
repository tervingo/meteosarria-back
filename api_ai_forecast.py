"""
Previsión de 8 días (Burgos / Barcelona-Sarrià) con tabla calculada a partir de
Open-Meteo (modelos numéricos) y un comentario breve generado por Claude.

La tabla (día, fecha, máx, mín, prob. precipitación) se calcula siempre en
Python a partir de datos reales del modelo -- Claude nunca genera ni transcribe
esas cifras, solo redacta el comentario de contexto (olas de calor, bajones, etc).
"""

from flask import Blueprint, jsonify
import logging
import os
import json
from datetime import datetime, timedelta
import requests
import pytz
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

ai_forecast_bp = Blueprint('ai_forecast', __name__)

CITIES = {
    'burgos': {'label': 'Burgos', 'lat': 42.343926001, 'lon': -3.696977},
    'barcelona': {'label': 'Barcelona (Sarrià)', 'lat': 41.3950387, 'lon': 2.1225328},
}

FORECAST_DAYS = 8
CACHE_HOURS = float(os.getenv('AI_FORECAST_CACHE_HOURS', 6))

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


def _fetch_open_meteo(lat, lon):
    """Obtiene la previsión diaria (máx/mín/prob. precipitación) de Open-Meteo."""
    url = 'https://api.open-meteo.com/v1/forecast'
    params = {
        'latitude': lat,
        'longitude': lon,
        'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max',
        'timezone': 'Europe/Madrid',
        'forecast_days': FORECAST_DAYS,
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response.json()['daily']


def _build_rows(daily):
    rows = []
    for i, date_str in enumerate(daily['time']):
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        rows.append({
            'day': DIAS_SEMANA[date_obj.weekday()],
            'date': date_obj.strftime('%d/%m'),
            'tmax': round(daily['temperature_2m_max'][i], 1),
            'tmin': round(daily['temperature_2m_min'][i], 1),
            'precip_prob': daily['precipitation_probability_max'][i],
        })
    return rows


def _generate_comment(city_label, rows):
    """Pide a Claude un comentario de 1-2 frases sobre la tabla ya calculada.
    Claude nunca genera las cifras, solo detecta y describe cambios bruscos.
    """
    try:
        import anthropic
    except ImportError:
        logger.warning("Paquete 'anthropic' no instalado; se omite el comentario")
        return None, "paquete 'anthropic' no instalado"

    if not os.getenv('ANTHROPIC_API_KEY'):
        logger.info("ANTHROPIC_API_KEY no configurada; se omite el comentario")
        return None, "ANTHROPIC_API_KEY no configurada"

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=300,
            output_config={
                "effort": "low",
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "comment": {"type": "string"}
                        },
                        "required": ["comment"],
                        "additionalProperties": False
                    }
                }
            },
            system=(
                "Eres un asistente meteorológico conciso. Se te da una tabla de previsión "
                "(día, fecha, temperatura máxima, mínima y probabilidad de precipitación) "
                f"para los próximos {FORECAST_DAYS} días en {city_label}, calculada a partir de "
                "modelos numéricos. Escribe SOLO un comentario de contexto de 1 a 2 frases en "
                "español: menciona brevemente cualquier cambio brusco de temperatura (ola de "
                "calor, entrada fría, bajón notable) que detectes en la tabla. Sé directo y "
                "conciso, sin rodeos ni repetir las cifras exactas de la tabla. No inventes "
                "datos que no estén en la tabla; si no hay ningún cambio destacable, dilo en "
                "una frase corta."
            ),
            messages=[{"role": "user", "content": json.dumps(rows, ensure_ascii=False)}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)["comment"], None
    except Exception as e:
        logger.error(f"Error generando comentario con Claude: {e}")
        return None, str(e)


@ai_forecast_bp.route('/api/ai-forecast/<city>')
def get_ai_forecast(city):
    city = city.lower()
    if city not in CITIES:
        return jsonify({'error': f"Ciudad desconocida: {city}"}), 404

    cached = _get_cached(city)
    if cached:
        return jsonify(cached)

    try:
        info = CITIES[city]
        daily = _fetch_open_meteo(info['lat'], info['lon'])
        rows = _build_rows(daily)
        comment, comment_error = _generate_comment(info['label'], rows)

        payload = {
            'city': city,
            'label': info['label'],
            'updated_at': datetime.now(pytz.timezone('Europe/Madrid')).isoformat(),
            'rows': rows,
            'comment': comment,
        }
        if comment_error:
            payload['comment_error'] = comment_error
        _set_cached(city, payload)
        return jsonify(payload)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error obteniendo datos de Open-Meteo para {city}: {e}")
        stale = _cache.get(city)
        if stale:
            logger.warning(f"Sirviendo previsión cacheada (caducada) de {city} por fallo de Open-Meteo")
            stale_payload = dict(stale['payload'])
            stale_payload['stale'] = True
            stale_payload['stale_reason'] = str(e)
            return jsonify(stale_payload)
        return jsonify({'error': 'No se pudo obtener la previsión', 'detail': str(e)}), 502
    except Exception as e:
        logger.error(f"Error inesperado en ai-forecast/{city}: {e}")
        return jsonify({'error': 'Error interno', 'detail': str(e)}), 500


@ai_forecast_bp.route('/api/ai-forecast/<city>/clear-cache', methods=['POST'])
def clear_ai_forecast_cache(city):
    city = city.lower()
    _cache.pop(city, None)
    return jsonify({'status': 'success', 'message': f'Caché de {city} borrada'})
