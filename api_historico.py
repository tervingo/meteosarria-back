from flask import Blueprint, jsonify, request, current_app
import logging
import os
import pytz
from datetime import datetime, timedelta
from database import get_collection
import statistics
from collections import defaultdict
from cache_manager import (
    get_current_date, 
    get_historical_data_with_cache, 
    get_current_data_only,
    cache_historical_data
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
historico_bp = Blueprint('historico', __name__)

def get_historico_collection():
    """Obtener colección de datos históricos"""

    from pymongo import MongoClient
    import os
    
    client = MongoClient(os.getenv('MONGODB_URI'))
    db = client['meteosarria']
    return db['historico_intervalos'], db['historico_diario']


@historico_bp.route('/api/dashboard/test')
def test_endpoint():
    """Endpoint de prueba para verificar que el blueprint funciona"""
    try:
        logging.info("Test endpoint called")
        return jsonify({
            "status": "ok",
            "message": "Historico blueprint is working",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Error in test endpoint: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@historico_bp.route('/api/dashboard/records')
def dashboard_records():
    """Records históricos absolutos"""
    try:
        logging.info("Dashboard records endpoint called")
        
        intervalos_collection, diario_collection = get_historico_collection()
        
        logging.info(f"Collections obtained: intervalos={intervalos_collection}, diario={diario_collection}")
        
        # Verificar si hay datos en las colecciones
        count_intervalos = intervalos_collection.count_documents({})
        count_diario = diario_collection.count_documents({})
        logging.info(f"Document count - intervalos: {count_intervalos}, diario: {count_diario}")
        
        # Records absolutos - usar caché para datos históricos
        pipeline_maxima_historica = [
            {"$sort": {"temperatura.maxima": -1}},
            {"$limit": 1}
        ]
        
        pipeline_maxima_masbaja = [
            {"$sort": {"temperatura.maxima": 1}},
            {"$limit": 1}
        ]
        
        pipeline_minima_masbaja = [
            {"$sort": {"temperatura.minima": 1}},
            {"$limit": 1}
        ]
        
        pipeline_minima_masalta = [
            {"$sort": {"temperatura.minima": -1}},
            {"$limit": 1}
        ]
        
        # Obtener datos históricos con caché
        maxima_masalta_historica = get_historical_data_with_cache(diario_collection, pipeline_maxima_historica)
        maxima_masbaja_historica = get_historical_data_with_cache(diario_collection, pipeline_maxima_masbaja)
        minima_masbaja_historica = get_historical_data_with_cache(diario_collection, pipeline_minima_masbaja)
        minima_masalta_historica = get_historical_data_with_cache(diario_collection, pipeline_minima_masalta)
        
        # Records de este año - incluir datos actuales
        año_actual = datetime.now().year
        pipeline_maxima_año = [
            {"$match": {"año": año_actual}},
            {"$sort": {"temperatura.maxima": -1}},
            {"$limit": 1}
        ]
        
        pipeline_minima_año = [
            {"$match": {"año": año_actual}},
            {"$sort": {"temperatura.minima": 1}},
            {"$limit": 1}
        ]
        
        # Para el año actual, obtener datos históricos + actuales
        maxima_año = list(diario_collection.aggregate(pipeline_maxima_año))
        minima_año = list(diario_collection.aggregate(pipeline_minima_año))
        
        records = {}
        
        # Procesar records absolutos
        if maxima_masalta_historica:
            doc = maxima_masalta_historica[0]
            records["maxima_masalta_historica"] = {
                "valor": doc['temperatura']['maxima'],
                "fecha": doc['fecha']
            }

        if maxima_masbaja_historica:
            doc = maxima_masbaja_historica[0]
            records["maxima_masbaja_historica"] = {
                "valor": doc['temperatura']['maxima'],
                "fecha": doc['fecha']
            }

        if minima_masbaja_historica:
            doc = minima_masbaja_historica[0]
            records["minima_masbaja_historica"] = {
                "valor": doc['temperatura']['minima'],
                "fecha": doc['fecha']
            }

        if minima_masalta_historica:
            doc = minima_masalta_historica[0]
            records["minima_masalta_historica"] = {
                "valor": doc['temperatura']['minima'],
                "fecha": doc['fecha']
            }
        
        # Procesar records del año
        if maxima_año:
            doc = maxima_año[0]
            records["maxima_este_año"] = {
                "valor": doc['temperatura']['maxima'],
                "fecha": doc['fecha']
            }
        
        if minima_año:
            doc = minima_año[0]
            records["minima_este_año"] = {
                "valor": doc['temperatura']['minima'],
                "fecha": doc['fecha']
            }
        
        return jsonify(records)
        
    except Exception as e:
        logging.error(f"Error en dashboard records: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@historico_bp.route('/api/dashboard/tendencia-anual')
def tendencia_anual():
    """Tendencia de temperatura media anual"""
    try:
        logging.info("Dashboard tendencia anual endpoint called")
        
        intervalos_collection, diario_collection = get_historico_collection()
        
        # Agregación por año - usar caché para datos históricos
        pipeline = [
            {
                "$group": {
                    "_id": "$año",
                    "temp_media": {"$avg": "$temperatura.promedio"},
                    "temp_maxima": {"$avg": "$temperatura.maxima"},
                    "temp_minima": {"$avg": "$temperatura.minima"},
                    "hum_media": {"$avg": "$humedad.promedio"}
                }
            },
            {
                "$sort": {"_id": 1}
            }
        ]
        
        # Obtener datos históricos con caché
        datos_anuales = get_historical_data_with_cache(diario_collection, pipeline)
        
        # Obtener datos actuales del año actual
        año_actual = datetime.now().year
        pipeline_actual = [
            {
                "$match": {"año": año_actual}
            },
            {
                "$group": {
                    "_id": "$año",
                    "temp_media": {"$avg": "$temperatura.promedio"},
                    "temp_maxima": {"$avg": "$temperatura.maxima"},
                    "temp_minima": {"$avg": "$temperatura.minima"},
                    "hum_media": {"$avg": "$humedad.promedio"}
                }
            }
        ]
        
        datos_actuales = list(diario_collection.aggregate(pipeline_actual))
        
        # Combinar datos históricos con actuales
        datos_completos = datos_anuales + datos_actuales
        
        # Preparar datos para el frontend
        años = []
        temperaturas_medias = []
        temperaturas_maximas = []
        temperaturas_minimas = []
        humedades_medias = []
        
        for doc in datos_completos:
            años.append(doc['_id'])
            temperaturas_medias.append(round(doc['temp_media'], 1))
            temperaturas_maximas.append(round(doc['temp_maxima'], 1))
            temperaturas_minimas.append(round(doc['temp_minima'], 1))
            humedades_medias.append(round(doc['hum_media'], 1))
        
        # Calcular tendencia (regresión lineal simple)
        tendencia = "estable"
        incremento_decada = 0
        
        if len(temperaturas_medias) >= 3:
            # Cálculo simple de tendencia
            primera_mitad = temperaturas_medias[:len(temperaturas_medias)//2]
            segunda_mitad = temperaturas_medias[len(temperaturas_medias)//2:]
            
            promedio_primera = statistics.mean(primera_mitad)
            promedio_segunda = statistics.mean(segunda_mitad)
            
            diferencia = promedio_segunda - promedio_primera
            años_span = len(temperaturas_medias)
            
            if diferencia > 0.5:
                tendencia = "ascendente"
            elif diferencia < -0.5:
                tendencia = "descendente"
            
            # Estimación de incremento por década
            incremento_decada = round((diferencia / años_span) * 10, 1)
        
        return jsonify({
            "años": años,
            "temperaturas_medias": temperaturas_medias,
            "temperaturas_maximas": temperaturas_maximas,
            "temperaturas_minimas": temperaturas_minimas,
            "humedades_medias": humedades_medias,
            "tendencia": tendencia,
            "incremento_decada": incremento_decada,
            "periodo": f"{min(años)}-{max(años)}" if años else ""
        })
        
    except Exception as e:
        logging.error(f"Error en tendencia anual: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@historico_bp.route('/api/dashboard/comparativa-año')
@historico_bp.route('/api/dashboard/comparativa-año/<int:year>')
def comparativa_año(year=None):
    """Comparativa del año actual vs promedio histórico por mes"""
    try:
        logging.info(f"Dashboard comparativa año endpoint called - year: {year}")
        
        intervalos_collection, diario_collection = get_historico_collection()
        
        if year is None:
            year = datetime.now().year
        
        # Datos del año específico - incluir datos actuales si es el año actual
        pipeline_año = [
            {
                "$match": {"año": year}
            },
            {
                "$group": {
                    "_id": "$mes",
                    "temp_media": {"$avg": "$temperatura.promedio"},
                    "temp_maxima": {"$avg": "$temperatura.maxima"},
                    "temp_minima": {"$avg": "$temperatura.minima"}
                }
            },
            {
                "$sort": {"_id": 1}
            }
        ]
        
        # Si es el año actual, obtener datos completos (sin caché)
        if year == datetime.now().year:
            datos_año = list(diario_collection.aggregate(pipeline_año))
        else:
            # Si es año anterior, usar caché
            datos_año = get_historical_data_with_cache(diario_collection, pipeline_año)
        
        # Promedio histórico (excluyendo el año consultado) - usar caché
        pipeline_historico = [
            {
                "$match": {"año": {"$ne": year}}
            },
            {
                "$group": {
                    "_id": "$mes",
                    "temp_media": {"$avg": "$temperatura.promedio"},
                    "temp_maxima": {"$avg": "$temperatura.maxima"},
                    "temp_minima": {"$avg": "$temperatura.minima"}
                }
            },
            {
                "$sort": {"_id": 1}
            }
        ]
        
        datos_historico = get_historical_data_with_cache(diario_collection, pipeline_historico)
        
        # Crear diccionarios para fácil acceso
        año_dict = {doc['_id']: doc for doc in datos_año}
        hist_dict = {doc['_id']: doc for doc in datos_historico}
        
        # Nombres de meses
        meses_nombres = [
            "Ene", "Feb", "Mar", "Abr", "May", "Jun",
            "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"
        ]
        
        # Preparar datos para cada mes
        año_actual = []
        promedio_historico = []
        diferencias = []
        
        for mes_num in range(1, 13):
            temp_año = año_dict.get(mes_num, {}).get('temp_media', None)
            temp_hist = hist_dict.get(mes_num, {}).get('temp_media', None)
            
            año_actual.append(round(temp_año, 1) if temp_año else None)
            promedio_historico.append(round(temp_hist, 1) if temp_hist else None)
            
            if temp_año and temp_hist:
                diferencias.append(round(temp_año - temp_hist, 1))
            else:
                diferencias.append(None)
        
        return jsonify({
            "año": year,
            "meses": meses_nombres,
            "año_actual": año_actual,
            "promedio_historico": promedio_historico,
            "diferencias": diferencias
        })
        
    except Exception as e:
        logging.error(f"Error en comparativa año: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@historico_bp.route('/api/dashboard/heatmap')
def heatmap_data():
    """Datos para mapa de calor año x mes"""
    try:
        logging.info("Dashboard heatmap endpoint called")
        
        intervalos_collection, diario_collection = get_historico_collection()
        
        # Últimos 6 años para el heatmap
        año_actual = datetime.now().year
        años_heatmap = list(range(año_actual - 5, año_actual + 1))
        
        pipeline = [
            {
                "$match": {"año": {"$in": años_heatmap}}
            },
            {
                "$group": {
                    "_id": {
                        "año": "$año",
                        "mes": "$mes"
                    },
                    "temperatura": {"$avg": "$temperatura.promedio"}
                }
            },
            {
                "$sort": {
                    "_id.año": 1,
                    "_id.mes": 1
                }
            }
        ]
        
        # Para el heatmap, obtener datos históricos con caché
        datos_heatmap = get_historical_data_with_cache(diario_collection, pipeline)
        
        # Obtener datos actuales del año actual
        pipeline_actual = [
            {
                "$match": {"año": año_actual}
            },
            {
                "$group": {
                    "_id": {
                        "año": "$año",
                        "mes": "$mes"
                    },
                    "temperatura": {"$avg": "$temperatura.promedio"}
                }
            },
            {
                "$sort": {
                    "_id.año": 1,
                    "_id.mes": 1
                }
            }
        ]
        
        datos_actuales = list(diario_collection.aggregate(pipeline_actual))
        
        # Combinar datos
        datos_completos = datos_heatmap + datos_actuales
        
        # Formatear para el frontend
        heatmap_formatted = []
        for doc in datos_completos:
            heatmap_formatted.append({
                "año": doc['_id']['año'],
                "mes": doc['_id']['mes'],
                "temperatura": round(doc['temperatura'], 1)
            })
        
        return jsonify({
            "data": heatmap_formatted,
            "años": años_heatmap,
            "rango_temperaturas": {
                "min": min([d['temperatura'] for d in heatmap_formatted]) if heatmap_formatted else 0,
                "max": max([d['temperatura'] for d in heatmap_formatted]) if heatmap_formatted else 30
            }
        })
        
    except Exception as e:
        logging.error(f"Error en heatmap: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@historico_bp.route('/api/dashboard/estadisticas')
@historico_bp.route('/api/dashboard/estadisticas/<int:year>/<int:month>')
def estadisticas_destacadas(year=None, month=None):
    """Estadísticas destacadas del mes especificado y rachas actuales"""
    try:
        logging.info("Dashboard estadísticas endpoint called")
        
        intervalos_collection, diario_collection = get_historico_collection()
        
        # Fecha actual
        now = get_current_date()
        
        # Si no se especifican año y mes, usar el mes actual
        if year is None or month is None:
            año_mes = now.year
            mes = now.month
        else:
            año_mes = year
            mes = month
        
        # Estadísticas del mes especificado
        pipeline_mes = [
            {
                "$match": {
                    "año": año_mes,
                    "mes": mes
                }
            },
            {
                "$group": {
                    "_id": None,
                    "dias_max_gte_35": {
                        "$sum": {
                            "$cond": [{"$gte": ["$temperatura.maxima", 35]}, 1, 0]
                        }
                    },
                    "dias_max_gte_30": {
                        "$sum": {
                            "$cond": [{"$gte": ["$temperatura.maxima", 30]}, 1, 0]
                        }
                    },
                    "dias_max_gte_25": {
                        "$sum": {
                            "$cond": [{"$gte": ["$temperatura.maxima", 25]}, 1, 0]
                        }
                    },
                    "dias_max_gt_20": {
                        "$sum": {
                            "$cond": [{"$gt": ["$temperatura.maxima", 20]}, 1, 0]
                        }
                    },
                    "dias_max_lte_20": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.maxima", 20]}, 1, 0]
                        }
                    },
                    "dias_max_lte_15": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.maxima", 15]}, 1, 0]
                        }
                    },
                    "dias_max_lte_10": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.maxima", 10]}, 1, 0]
                        }
                    },
                    "dias_max_lte_5": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.maxima", 5]}, 1, 0]
                        }
                    },
                    "dias_max_lte_0": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.maxima", 0]}, 1, 0]
                        }
                    },
                    "dias_min_gte_30": {
                        "$sum": {
                            "$cond": [{"$gte": ["$temperatura.minima", 30]}, 1, 0]
                        }
                    },
                    "dias_min_gte_25": {
                        "$sum": {
                            "$cond": [{"$gte": ["$temperatura.minima", 25]}, 1, 0]
                        }
                    },
                    "dias_min_gte_20": {
                        "$sum": {
                            "$cond": [{"$gte": ["$temperatura.minima", 20]}, 1, 0]
                        }
                    },
                    "dias_min_lte_20": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.minima", 20]}, 1, 0]
                        }
                    },
                    "dias_min_lte_15": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.minima", 15]}, 1, 0]
                        }
                    },
                    "dias_min_lte_10": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.minima", 10]}, 1, 0]
                        }
                    },
                    "dias_min_lte_5": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.minima", 5]}, 1, 0]
                        }
                    },
                    "dias_min_lte_0": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.minima", 0]}, 1, 0]
                        }
                    },
                    "temp_media_mes": {"$avg": "$temperatura.promedio"},
                    "temp_maxima_mes": {"$max": "$temperatura.maxima"},
                    "temp_minima_mes": {"$min": "$temperatura.minima"},
                    "dias_helada": {
                        "$sum": {
                            "$cond": [{"$lte": ["$temperatura.minima", 0]}, 1, 0]
                        }
                    },
                    "total_dias": {"$sum": 1}
                }
            }
        ]
        
        # Si es el mes actual, obtener datos completos (sin caché)
        if año_mes == now.year and mes == now.month:
            stats_mes = list(diario_collection.aggregate(pipeline_mes))
        else:
            # Si es mes anterior, usar caché
            stats_mes = get_historical_data_with_cache(diario_collection, pipeline_mes)
        
        # Verificar si hay record mensual histórico
        pipeline_record_mes = [
            {
                "$match": {
                    "mes": mes,
                    "año": {"$ne": año_mes}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "record_historico": {"$max": "$temperatura.maxima"}
                }
            }
        ]
        
        record_mes = get_historical_data_with_cache(diario_collection, pipeline_record_mes)
        
        # Preparar respuesta
        estadisticas = {
            "mes_seleccionado": {
                "mes": mes,
                "año": año_mes,
                "nombre_mes": ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                              "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][mes],
                "dias_max_gte_35": 0,
                "dias_max_gte_30": 0,
                "dias_max_gte_25": 0,
                "dias_max_gt_20": 0,
                "dias_max_lte_20": 0,
                "dias_max_lte_15": 0,
                "dias_max_lte_10": 0,   
                "dias_max_lte_5": 0,
                "dias_max_lte_0": 0,
                "dias_min_gte_30": 0,
                "dias_min_gte_25": 0,
                "dias_min_gte_20": 0,
                "dias_min_lte_20": 0,
                "dias_min_lte_15": 0,
                "dias_min_lte_10": 0,
                "dias_min_lte_5": 0,
                "dias_min_lte_0": 0,
                "temperatura_media": 0,
                "temperatura_maxima": 0,
                "temperatura_minima": 0,
                "dias_helada": 0,
                "record_mes": False,
                "total_dias": 0
            },
            "rachas": {
                "sin_heladas": 0,
                "dias_sobre_20": 0,
                "dias_consecutivos_calor": 0
            }
        }
        
        if stats_mes:
            mes_data = stats_mes[0]
            estadisticas["mes_seleccionado"].update({
                "dias_max_gte_35": mes_data.get('dias_max_gte_35', 0),
                "dias_max_gte_30": mes_data.get('dias_max_gte_30', 0),
                "dias_max_gte_25": mes_data.get('dias_max_gte_25', 0),
                "dias_max_gt_20": mes_data.get('dias_max_gt_20', 0),
                "dias_max_lte_20": mes_data.get('dias_max_lte_20', 0),
                "dias_max_lte_15": mes_data.get('dias_max_lte_15', 0),
                "dias_max_lte_10": mes_data.get('dias_max_lte_10', 0),
                "dias_max_lte_5": mes_data.get('dias_max_lte_5', 0),
                "dias_max_lte_0": mes_data.get('dias_max_lte_0', 0),
                "dias_min_gte_30": mes_data.get('dias_min_gte_30', 0),
                "dias_min_gte_25": mes_data.get('dias_min_gte_25', 0),
                "dias_min_gte_20": mes_data.get('dias_min_gte_20', 0),
                "dias_min_lte_20": mes_data.get('dias_min_lte_20', 0),
                "dias_min_lte_15": mes_data.get('dias_min_lte_15', 0),
                "dias_min_lte_10": mes_data.get('dias_min_lte_10', 0),
                "dias_min_lte_5": mes_data.get('dias_min_lte_5', 0),
                "dias_min_lte_0": mes_data.get('dias_min_lte_0', 0),
                "temperatura_media": round(mes_data.get('temp_media_mes', 0), 1),
                "temperatura_maxima": mes_data.get('temp_maxima_mes', 0),
                "temperatura_minima": mes_data.get('temp_minima_mes', 0),
                "dias_helada": mes_data.get('dias_helada', 0),
                "total_dias": mes_data.get('total_dias', 0),
                "record_mes": False
            })
            
            # Verificar record mensual
            if record_mes and mes_data.get('temp_maxima_mes'):
                record_historico = record_mes[0].get('record_historico', 0)
                estadisticas["mes_seleccionado"]["record_mes"] = mes_data['temp_maxima_mes'] > record_historico
        
        # Calcular rachas (simplificado - últimos 30 días)
        fecha_inicio_racha = now - timedelta(days=30)
        
        pipeline_rachas = [
            {
                "$match": {
                    "timestamp": {"$gte": fecha_inicio_racha}
                }
            },
            {
                "$sort": {"timestamp": 1}
            }
        ]
        
        # Para rachas, obtener datos completos (sin caché) ya que incluyen datos actuales
        datos_rachas = list(diario_collection.aggregate(pipeline_rachas))
        
        # Calcular rachas consecutivas
        sin_heladas = 0
        sobre_20 = 0
        
        for doc in reversed(datos_rachas):  # Desde el más reciente
            if doc['temperatura']['minima'] > 0:
                sin_heladas += 1
            else:
                break
        
        for doc in reversed(datos_rachas):  # Desde el más reciente
            if doc['temperatura']['maxima'] > 20:
                sobre_20 += 1
            else:
                break
        
        estadisticas["rachas"]["sin_heladas"] = sin_heladas
        estadisticas["rachas"]["dias_sobre_20"] = sobre_20
        
        return jsonify(estadisticas)
        
    except Exception as e:
        logging.error(f"Error en estadísticas destacadas: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@historico_bp.route('/api/dashboard/estadisticas-datos-diarios')
@historico_bp.route('/api/dashboard/estadisticas-datos-diarios/<int:year>/<int:month>')
def estadisticas_datos_diarios(year=None, month=None):
    """Datos diarios del mes especificado para gráficas"""
    try:
        logging.info(f"Dashboard datos diarios endpoint called - year: {year}, month: {month}")
        
        intervalos_collection, diario_collection = get_historico_collection()
        
        # Fecha actual
        now = get_current_date()
        
        # Si no se especifican año y mes, usar el mes actual
        if year is None or month is None:
            año_mes = now.year
            mes = now.month
        else:
            año_mes = year
            mes = month
        
        # Pipeline para obtener datos diarios del mes
        pipeline_datos_diarios = [
            {
                "$match": {
                    "año": año_mes,
                    "mes": mes
                }
            },
            {
                "$project": {
                    "fecha": 1,
                    "dia": 1,
                    "temperatura": 1,
                    "humedad": 1
                }
            },
            {
                "$sort": {"dia": 1}
            }
        ]
        
        # Si es el mes actual, obtener datos completos (sin caché)
        if año_mes == now.year and mes == now.month:
            datos_diarios = list(diario_collection.aggregate(pipeline_datos_diarios))
        else:
            # Si es mes anterior, usar caché
            datos_diarios = get_historical_data_with_cache(diario_collection, pipeline_datos_diarios)
        
        # Formatear datos para el frontend
        datos_formateados = []
        for doc in datos_diarios or []:
            datos_formateados.append({
                "dia": doc['dia'],
                "fecha": doc['fecha'],
                "maxima": doc['temperatura']['maxima'],
                "minima": doc['temperatura']['minima'],
                "media": doc['temperatura']['promedio'],
                "humedad_media": doc['humedad']['promedio']
            })
        
        return jsonify({
            "mes": mes,
            "año": año_mes,
            "nombre_mes": ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                          "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][mes],
            "datos_diarios": datos_formateados  # <-- SIEMPRE array, nunca None
        })
        
    except Exception as e:
        logging.error(f"Error en datos diarios: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@historico_bp.route('/api/dashboard/cache/status')
def cache_status():
    """Estado del caché histórico"""
    try:
        from cache_manager import invalidate_historical_cache
        cache = current_app.extensions['cache']
        
        # Obtener información del caché
        cache_info = {
            "cache_type": "simple",
            "cache_timeout": 86400,  # 24 horas
            "cache_prefix": "meteosarria_",
            "current_date": get_current_date().isoformat(),
            "cache_enabled": True
        }
        
        return jsonify(cache_info)
        
    except Exception as e:
        logging.error(f"Error en cache status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@historico_bp.route('/api/dashboard/cache/clear', methods=['POST'])
def clear_cache():
    """Limpiar caché histórico"""
    try:
        from cache_manager import invalidate_historical_cache
        invalidate_historical_cache()
        
        return jsonify({
            "status": "success",
            "message": "Cache histórico limpiado correctamente",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error limpiando cache: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500