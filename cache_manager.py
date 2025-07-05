"""
Cache Manager para MeteoSarria
Gestiona el caché inteligente que excluye datos actuales del año/mes/día actual
"""

import logging
from datetime import datetime, timedelta
import pytz
from functools import wraps
from flask import current_app

logger = logging.getLogger(__name__)

def get_current_date():
    """Obtiene la fecha actual en zona horaria de Madrid"""
    return datetime.now(pytz.timezone('Europe/Madrid'))

def is_current_data(date_obj):
    """
    Determina si una fecha corresponde a datos actuales (año/mes/día actual)
    que NO deben ser cacheados
    """
    current = get_current_date()
    
    # Si es del año actual
    if date_obj.year == current.year:
        # Si es del mes actual
        if date_obj.month == current.month:
            # Si es del día actual
            if date_obj.day == current.day:
                return True
    return False

def get_cache_key_for_historical_data(collection_name, query_type, **kwargs):
    """
    Genera una clave de caché para datos históricos
    """
    # Incluir fecha para invalidar caché diariamente
    current_date = get_current_date().strftime('%Y-%m-%d')
    
    # Crear clave única basada en el tipo de consulta
    key_parts = [collection_name, query_type, current_date]
    
    # Añadir parámetros adicionales si existen
    for key, value in sorted(kwargs.items()):
        key_parts.append(f"{key}_{value}")
    
    return "_".join(key_parts)

def cache_historical_data(timeout=86400):  # 24 horas por defecto
    """
    Decorador para cachear solo datos históricos
    Excluye automáticamente datos del año/mes/día actual
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from api_historico import get_historico_collection
            
            # Obtener colecciones
            intervalos_collection, diario_collection = get_historico_collection()
            
            # Determinar si necesitamos datos actuales
            current = get_current_date()
            need_current_data = kwargs.get('include_current', False)
            
            # Generar clave de caché
            cache_key = get_cache_key_for_historical_data(
                'historico', 
                func.__name__,
                include_current=need_current_data
            )
            
            # Intentar obtener del caché
            cache = current_app.extensions['cache']
            cached_result = cache.get(cache_key)
            
            if cached_result is not None:
                logger.info(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Si no está en caché, ejecutar función original
            logger.info(f"Cache miss for {func.__name__}, executing query")
            result = func(*args, **kwargs)
            
            # Cachear resultado
            cache.set(cache_key, result, timeout=timeout)
            logger.info(f"Cached result for {func.__name__}")
            
            return result
        return wrapper
    return decorator

def invalidate_historical_cache():
    """
    Invalida todo el caché histórico
    Útil cuando se añaden nuevos datos históricos
    """
    cache = current_app.extensions['cache']
    cache.clear()
    logger.info("Historical cache invalidated")

def get_historical_data_with_cache(collection, pipeline, exclude_current=True):
    """
    Función helper para obtener datos históricos con caché inteligente
    
    Args:
        collection: Colección de MongoDB
        pipeline: Pipeline de agregación
        exclude_current: Si excluir datos del año/mes/día actual
    """
    current = get_current_date()
    
    if exclude_current:
        # Modificar pipeline para excluir datos actuales
        match_stage = {
            "$match": {
                "$or": [
                    {"año": {"$lt": current.year}},
                    {
                        "$and": [
                            {"año": current.year},
                            {"mes": {"$lt": current.month}}
                        ]
                    },
                    {
                        "$and": [
                            {"año": current.year},
                            {"mes": current.month},
                            {"dia": {"$lt": current.day}}
                        ]
                    }
                ]
            }
        }
        
        # Insertar al inicio del pipeline
        pipeline.insert(0, match_stage)
    
    return list(collection.aggregate(pipeline))

def get_current_data_only(collection, pipeline):
    """
    Obtiene solo datos del año/mes/día actual (sin caché)
    """
    current = get_current_date()
    
    match_stage = {
        "$match": {
            "$and": [
                {"año": current.year},
                {"mes": current.month},
                {"dia": current.day}
            ]
        }
    }
    
    pipeline.insert(0, match_stage)
    return list(collection.aggregate(pipeline)) 