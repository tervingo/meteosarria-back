from flask import Blueprint, jsonify, request
import logging
import os
import pytz
from datetime import datetime, timedelta
from database import get_collection
import statistics
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
historico_bp = Blueprint('historico', __name__)

def get_historico_collection():
    """Obtener colección de datos históricos"""
    # Asumiendo que usarás las nuevas colecciones del script de migración
    # Si decides usar la colección actual, cambiar por get_collection()
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
        
        # Records absolutos
        maxima_masalta_historica = diario_collection.find().sort("temperatura.maxima", -1).limit(1)
        maxima_masbaja_historica = diario_collection.find().sort("temperatura.maxima", 1).limit(1)
        minima_masbaja_historica = diario_collection.find().sort("temperatura.minima", 1).limit(1)
        minima_masalta_historica = diario_collection.find().sort("temperatura.minima", -1).limit(1)
        
        # Records de este año
        año_actual = datetime.now().year
        maxima_año = diario_collection.find({"año": año_actual}).sort("temperatura.maxima", -1).limit(1)
        minima_año = diario_collection.find({"año": año_actual}).sort("temperatura.minima", 1).limit(1)
        
        records = {}
        
        # Procesar records absolutos
        for doc in maxima_masalta_historica:
            records["maxima_masalta_historica"] = {
                "valor": doc['temperatura']['maxima'],
                "fecha": doc['fecha']
            }

        for doc in maxima_masbaja_historica:
            records["maxima_masbaja_historica"] = {
                "valor": doc['temperatura']['maxima'],
                "fecha": doc['fecha']
            }

        for doc in minima_masbaja_historica:
            records["minima_masbaja_historica"] = {
                "valor": doc['temperatura']['minima'],
                "fecha": doc['fecha']
            }

        for doc in minima_masalta_historica:
            records["minima_masalta_historica"] = {
                "valor": doc['temperatura']['minima'],
                "fecha": doc['fecha']
            }
        
        # Procesar records del año
        for doc in maxima_año:
            records["maxima_este_año"] = {
                "valor": doc['temperatura']['maxima'],
                "fecha": doc['fecha']
            }
        
        for doc in minima_año:
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
        
        # Agregación por año
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
        
        datos_anuales = list(diario_collection.aggregate(pipeline))
        
        # Preparar datos para el frontend
        años = []
        temperaturas_medias = []
        temperaturas_maximas = []
        temperaturas_minimas = []
        humedades_medias = []
        
        for doc in datos_anuales:
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
        
        # Datos del año específico
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
        
        # Promedio histórico (excluyendo el año consultado)
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
        
        datos_año = list(diario_collection.aggregate(pipeline_año))
        datos_historico = list(diario_collection.aggregate(pipeline_historico))
        
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
        
        datos_heatmap = list(diario_collection.aggregate(pipeline))
        
        # Formatear para el frontend
        heatmap_formatted = []
        for doc in datos_heatmap:
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
def estadisticas_destacadas():
    """Estadísticas destacadas del mes pasado y rachas actuales"""
    try:
        logging.info("Dashboard estadísticas endpoint called")
        
        intervalos_collection, diario_collection = get_historico_collection()
        
        # Fecha actual
        now = datetime.now(pytz.timezone('Europe/Madrid'))
        
        # Calcular mes pasado
        if now.month == 1:
            mes_pasado = 12
            año_mes_pasado = now.year - 1
        else:
            mes_pasado = now.month - 1
            año_mes_pasado = now.year
        
        # Estadísticas del mes pasado
        pipeline_mes = [
            {
                "$match": {
                    "año": año_mes_pasado,
                    "mes": mes_pasado
                }
            },
            {
                "$group": {
                    "_id": None,
                    "dias_calor_25": {
                        "$sum": {
                            "$cond": [{"$gte": ["$temperatura.maxima", 25]}, 1, 0]
                        }
                    },
                    "dias_calor_30": {
                        "$sum": {
                            "$cond": [{"$gte": ["$temperatura.maxima", 30]}, 1, 0]
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
        
        stats_mes = list(diario_collection.aggregate(pipeline_mes))
        
        # Verificar si hay record mensual histórico
        pipeline_record_mes = [
            {
                "$match": {
                    "mes": mes_pasado,
                    "año": {"$ne": año_mes_pasado}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "record_historico": {"$max": "$temperatura.maxima"}
                }
            }
        ]
        
        record_mes = list(diario_collection.aggregate(pipeline_record_mes))
        
        # Preparar respuesta
        estadisticas = {
            "mes_pasado": {
                "mes": mes_pasado,
                "año": año_mes_pasado,
                "nombre_mes": ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                              "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][mes_pasado],
                "dias_calor_25": 0,
                "dias_calor_30": 0,
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
            estadisticas["mes_pasado"].update({
                "dias_calor_25": mes_data.get('dias_calor_25', 0),
                "dias_calor_30": mes_data.get('dias_calor_30', 0),
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
                estadisticas["mes_pasado"]["record_mes"] = mes_data['temp_maxima_mes'] > record_historico
        
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