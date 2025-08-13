from flask import Blueprint, jsonify, request
from pymongo import MongoClient
import os
from datetime import datetime
from collections import defaultdict

burgos_stats_bp = Blueprint('burgos_stats', __name__)

# MongoDB connection
MONGODB_URI = "mongodb+srv://tervingo:mig.langar.inn@gagnagunnur.okrh1.mongodb.net/meteosarria"
client = MongoClient(MONGODB_URI)
db = client['meteosarria']
burgos_collection = db['burgos_historico_temps']


@burgos_stats_bp.route('/api/burgos-estadisticas/records-absolutos', methods=['GET'])
def get_records_absolutos():
    """Obtener temperaturas máxima y mínima absolutas de toda la serie histórica"""
    try:
        # Buscar temperatura máxima absoluta
        max_temp = burgos_collection.find({"temp_maxima": {"$ne": None}}).sort("temp_maxima", -1).limit(1)
        max_temp_doc = list(max_temp)[0] if max_temp else None
        
        # Buscar temperatura mínima absoluta
        min_temp = burgos_collection.find({"temp_minima": {"$ne": None}}).sort("temp_minima", 1).limit(1)
        min_temp_doc = list(min_temp)[0] if min_temp else None
        
        # Buscar temperatura mínima más alta de la serie
        min_temp_max = burgos_collection.find({"temp_minima": {"$ne": None}}).sort("temp_minima", -1).limit(1)
        min_temp_max_doc = list(min_temp_max)[0] if min_temp_max else None
        
        # Buscar temperatura máxima más baja de la serie
        max_temp_min = burgos_collection.find({"temp_maxima": {"$ne": None}}).sort("temp_maxima", 1).limit(1)
        max_temp_min_doc = list(max_temp_min)[0] if max_temp_min else None
        
        result = {
            'temp_max_absoluta': {
                'valor': max_temp_doc['temp_maxima'] if max_temp_doc else None,
                'fecha': max_temp_doc['fecha'] if max_temp_doc and max_temp_doc.get('fecha') else None
            },
            'temp_min_absoluta': {
                'valor': min_temp_doc['temp_minima'] if min_temp_doc else None,
                'fecha': min_temp_doc['fecha'] if min_temp_doc and min_temp_doc.get('fecha') else None
            },
            'temp_min_mas_alta': {
                'valor': min_temp_max_doc['temp_minima'] if min_temp_max_doc else None,
                'fecha': min_temp_max_doc['fecha'] if min_temp_max_doc and min_temp_max_doc.get('fecha') else None
            },
            'temp_max_mas_baja': {
                'valor': max_temp_min_doc['temp_maxima'] if max_temp_min_doc else None,
                'fecha': max_temp_min_doc['fecha'] if max_temp_min_doc and max_temp_min_doc.get('fecha') else None
            }
        }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@burgos_stats_bp.route('/api/burgos-estadisticas/records-por-decada', methods=['GET'])
def get_records_por_decada():
    """Obtener temperaturas máxima y mínima absolutas por década"""
    try:
        pipeline = [
            {
                '$addFields': {
                    'año': {'$year': '$fecha_datetime'},
                    'decada': {
                        '$multiply': [
                            {'$floor': {'$divide': [{'$year': '$fecha_datetime'}, 10]}},
                            10
                        ]
                    }
                }
            },
            {
                '$match': {
                    'temp_maxima': {'$ne': None},
                    'temp_minima': {'$ne': None},
                    'año': {'$gte': 1970}
                }
            },
            {
                '$group': {
                    '_id': '$decada',
                    'temp_max': {'$max': '$temp_maxima'},
                    'temp_min': {'$min': '$temp_minima'},
                    'docs_max': {'$push': {'temp': '$temp_maxima', 'fecha': '$fecha'}},
                    'docs_min': {'$push': {'temp': '$temp_minima', 'fecha': '$fecha'}}
                }
            },
            {'$sort': {'_id': 1}}
        ]
        
        results = list(burgos_collection.aggregate(pipeline))
        
        records_por_decada = []
        for result in results:
            decada = result['_id']
            temp_max = result['temp_max']
            temp_min = result['temp_min']
            
            # Encontrar las fechas correspondientes a los valores máximos y mínimos
            fecha_max = None
            fecha_min = None
            
            for doc in result['docs_max']:
                if doc['temp'] == temp_max:
                    fecha_max = doc['fecha']
                    break
            
            for doc in result['docs_min']:
                if doc['temp'] == temp_min:
                    fecha_min = doc['fecha']
                    break
            
            records_por_decada.append({
                'decada': decada,
                'temp_max': temp_max,
                'fecha_max': fecha_max,
                'temp_min': temp_min,
                'fecha_min': fecha_min
            })
        
        return jsonify(records_por_decada)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@burgos_stats_bp.route('/api/burgos-estadisticas/temperatura-media-decada', methods=['GET'])
def get_temperatura_media_decada():
    """Obtener temperatura media por década"""
    try:
        pipeline = [
            {
                '$addFields': {
                    'año': {'$year': '$fecha_datetime'}
                }
            },
            {
                '$match': {
                    'temp_maxima': {'$ne': None},
                    'temp_minima': {'$ne': None},
                    'año': {'$gte': 1970}
                }
            },
            {
                '$addFields': {
                    'decada': {
                        '$multiply': [
                            {'$floor': {'$divide': [{'$year': '$fecha_datetime'}, 10]}},
                            10
                        ]
                    },
                    'temp_media': {'$divide': [{'$add': ['$temp_maxima', '$temp_minima']}, 2]}
                }
            },
            {
                '$group': {
                    '_id': '$decada',
                    'temp_media': {'$avg': '$temp_media'}
                }
            },
            {'$sort': {'_id': 1}}
        ]
        
        results = list(burgos_collection.aggregate(pipeline))
        
        temp_media_decada = []
        for result in results:
            temp_media_decada.append({
                'decada': f"{result['_id']}s",
                'temp_media': round(result['temp_media'], 1) if result['temp_media'] else None
            })
        
        return jsonify(temp_media_decada)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@burgos_stats_bp.route('/api/burgos-estadisticas/dias-calurosos-anual', methods=['GET'])
def get_dias_calurosos_anual():
    """Obtener número de días con temperatura máxima > 30°C por año"""
    try:
        pipeline = [
            {
                '$match': {
                    'temp_maxima': {'$gt': 30}
                }
            },
            {
                '$addFields': {
                    'año': {'$year': '$fecha_datetime'}
                }
            },
            {
                '$group': {
                    '_id': '$año',
                    'dias_max_gt_30': {'$sum': 1}
                }
            },
            {'$sort': {'_id': 1}}
        ]
        
        results = list(burgos_collection.aggregate(pipeline))
        
        # Crear lista completa de años con 0 días si no hay datos
        años_completos = {}
        año_inicial = 1970
        año_actual = datetime.now().year
        
        for año in range(año_inicial, año_actual + 1):
            años_completos[año] = 0
        
        for result in results:
            años_completos[result['_id']] = result['dias_max_gt_30']
        
        dias_calurosos = []
        for año, dias in años_completos.items():
            dias_calurosos.append({
                'año': año,
                'dias_max_gt_30': dias
            })
        
        return jsonify(dias_calurosos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@burgos_stats_bp.route('/api/burgos-estadisticas/dias-torridos-anual', methods=['GET'])
def get_dias_torridos_anual():
    """Obtener número de días con temperatura máxima > 35°C por año"""
    try:
        pipeline = [
            {
                '$match': {
                    'temp_maxima': {'$gt': 35}
                }
            },
            {
                '$addFields': {
                    'año': {'$year': '$fecha_datetime'}
                }
            },
            {
                '$group': {
                    '_id': '$año',
                    'dias_max_gt_35': {'$sum': 1}
                }
            },
            {'$sort': {'_id': 1}}
        ]
        
        results = list(burgos_collection.aggregate(pipeline))
        
        # Crear lista completa de años con 0 días si no hay datos
        años_completos = {}
        año_inicial = 1970
        año_actual = datetime.now().year
        
        for año in range(año_inicial, año_actual + 1):
            años_completos[año] = 0
        
        for result in results:
            años_completos[result['_id']] = result['dias_max_gt_35']
        
        dias_torridos = []
        for año, dias in años_completos.items():
            dias_torridos.append({
                'año': año,
                'dias_max_gt_35': dias
            })
        
        return jsonify(dias_torridos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@burgos_stats_bp.route('/api/burgos-estadisticas/rachas-calurosas-anual', methods=['GET'])
def get_rachas_calurosas_anual():
    """Obtener número máximo de días consecutivos con temperatura máxima > 30°C por año"""
    try:
        # Obtener todos los datos ordenados por fecha
        cursor = burgos_collection.find({}, {'fecha_datetime': 1, 'temp_maxima': 1}).sort('fecha_datetime', 1)
        datos = list(cursor)
        
        rachas_por_año = defaultdict(int)
        
        # Agrupar por año
        datos_por_año = defaultdict(list)
        for dato in datos:
            if dato.get('fecha_datetime') and dato.get('temp_maxima') is not None:
                año = dato['fecha_datetime'].year
                datos_por_año[año].append(dato)
        
        # Calcular rachas para cada año
        for año, datos_año in datos_por_año.items():
            datos_año.sort(key=lambda x: x['fecha_datetime'])
            
            racha_actual = 0
            racha_maxima = 0
            
            for dato in datos_año:
                if dato['temp_maxima'] > 30:
                    racha_actual += 1
                    racha_maxima = max(racha_maxima, racha_actual)
                else:
                    racha_actual = 0
            
            rachas_por_año[año] = racha_maxima
        
        # Crear lista completa de años
        año_inicial = 1970
        año_actual = datetime.now().year
        
        rachas_calurosas = []
        for año in range(año_inicial, año_actual + 1):
            rachas_calurosas.append({
                'año': año,
                'racha_max_gt_30': rachas_por_año.get(año, 0)
            })
        
        return jsonify(rachas_calurosas)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@burgos_stats_bp.route('/api/burgos-estadisticas/rachas-torridas-anual', methods=['GET'])
def get_rachas_torridas_anual():
    """Obtener número máximo de días consecutivos con temperatura máxima > 35°C por año"""
    try:
        # Obtener todos los datos ordenados por fecha
        cursor = burgos_collection.find({}, {'fecha_datetime': 1, 'temp_maxima': 1}).sort('fecha_datetime', 1)
        datos = list(cursor)
        
        rachas_por_año = defaultdict(int)
        
        # Agrupar por año
        datos_por_año = defaultdict(list)
        for dato in datos:
            if dato.get('fecha_datetime') and dato.get('temp_maxima') is not None:
                año = dato['fecha_datetime'].year
                datos_por_año[año].append(dato)
        
        # Calcular rachas para cada año
        for año, datos_año in datos_por_año.items():
            datos_año.sort(key=lambda x: x['fecha_datetime'])
            
            racha_actual = 0
            racha_maxima = 0
            
            for dato in datos_año:
                if dato['temp_maxima'] > 35:
                    racha_actual += 1
                    racha_maxima = max(racha_maxima, racha_actual)
                else:
                    racha_actual = 0
            
            rachas_por_año[año] = racha_maxima
        
        # Crear lista completa de años
        año_inicial = 1970
        año_actual = datetime.now().year
        
        rachas_torridas = []
        for año in range(año_inicial, año_actual + 1):
            rachas_torridas.append({
                'año': año,
                'racha_max_gt_35': rachas_por_año.get(año, 0)
            })
        
        return jsonify(rachas_torridas)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@burgos_stats_bp.route('/api/burgos-estadisticas/noches-tropicales-anual', methods=['GET'])
def get_noches_tropicales_anual():
    """Obtener número de noches con temperatura mínima > 20°C por año"""
    try:
        pipeline = [
            {
                '$match': {
                    'temp_minima': {'$gt': 20}
                }
            },
            {
                '$addFields': {
                    'año': {'$year': '$fecha_datetime'}
                }
            },
            {
                '$group': {
                    '_id': '$año',
                    'noches_min_gt_20': {'$sum': 1}
                }
            },
            {'$sort': {'_id': 1}}
        ]
        
        results = list(burgos_collection.aggregate(pipeline))
        
        # Crear lista completa de años con 0 noches si no hay datos
        años_completos = {}
        año_inicial = 1970
        año_actual = datetime.now().year
        
        for año in range(año_inicial, año_actual + 1):
            años_completos[año] = 0
        
        for result in results:
            años_completos[result['_id']] = result['noches_min_gt_20']
        
        noches_tropicales = []
        for año, noches in años_completos.items():
            noches_tropicales.append({
                'año': año,
                'noches_min_gt_20': noches
            })
        
        return jsonify(noches_tropicales)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@burgos_stats_bp.route('/api/burgos-estadisticas/ultimo-registro', methods=['GET'])
def get_ultimo_registro():
    """Obtener la fecha del último registro en la base de datos"""
    try:
        # Buscar el documento con la fecha más reciente usando ambos campos de fecha
        ultimo_doc_datetime = burgos_collection.find({"fecha_datetime": {"$ne": None}}).sort("fecha_datetime", -1).limit(1)
        ultimo_doc_fecha = burgos_collection.find({"fecha": {"$ne": None}}).sort("fecha", -1).limit(1)
        
        doc_datetime = list(ultimo_doc_datetime)
        doc_fecha = list(ultimo_doc_fecha)
        
        # Comparar ambas fechas y usar la más reciente
        if doc_datetime and doc_fecha:
            fecha_datetime_val = doc_datetime[0]['fecha_datetime']
            fecha_val = doc_fecha[0]['fecha']
            
            # Convertir fecha string a datetime para comparar si es necesario
            if isinstance(fecha_val, str):
                from datetime import datetime as dt
                fecha_val_dt = dt.strptime(fecha_val, '%Y-%m-%d')
            else:
                fecha_val_dt = fecha_val
            
            # Usar la fecha más reciente
            if fecha_datetime_val.date() >= fecha_val_dt.date():
                ultima_fecha = fecha_datetime_val.strftime('%Y-%m-%d')
            else:
                ultima_fecha = fecha_val_dt.strftime('%Y-%m-%d')
                
            return jsonify({'ultimaFecha': ultima_fecha})
        elif doc_datetime:
            fecha_datetime = doc_datetime[0]['fecha_datetime']
            ultima_fecha = fecha_datetime.strftime('%Y-%m-%d')
            return jsonify({'ultimaFecha': ultima_fecha})
        elif doc_fecha:
            if isinstance(doc_fecha[0]['fecha'], str):
                return jsonify({'ultimaFecha': doc_fecha[0]['fecha']})
            else:
                ultima_fecha = doc_fecha[0]['fecha'].strftime('%Y-%m-%d')
                return jsonify({'ultimaFecha': ultima_fecha})
        else:
            return jsonify({'ultimaFecha': None})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500