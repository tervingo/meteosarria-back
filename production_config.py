"""
Configuración específica para producción
Optimiza el sistema de caché para Render
"""

import os

# Configuración de caché para producción
PRODUCTION_CACHE_CONFIG = {
    'CACHE_TYPE': 'simple',  # Mantener simple para Render
    'CACHE_DEFAULT_TIMEOUT': 86400,  # 24 horas
    'CACHE_KEY_PREFIX': 'meteosarria_prod_',
    'CACHE_THRESHOLD': 1000,  # Máximo número de elementos en caché
}

# Configuración de logging para producción
PRODUCTION_LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': True
        },
        'cache_manager': {
            'level': 'INFO',
        },
        'api_historico': {
            'level': 'INFO',
        }
    }
}

# Configuración de Gunicorn para producción
GUNICORN_CONFIG = {
    'bind': '0.0.0.0:8080',
    'workers': 2,  # Ajustar según recursos de Render
    'worker_class': 'sync',
    'worker_connections': 1000,
    'max_requests': 1000,
    'max_requests_jitter': 100,
    'timeout': 30,
    'keepalive': 2,
    'preload_app': True,  # Importante para caché compartido
}

def get_production_cache_config():
    """Obtiene configuración de caché para producción"""
    return PRODUCTION_CACHE_CONFIG

def get_production_logging_config():
    """Obtiene configuración de logging para producción"""
    return PRODUCTION_LOGGING_CONFIG

def get_gunicorn_config():
    """Obtiene configuración de Gunicorn para producción"""
    return GUNICORN_CONFIG

def is_production():
    """Determina si estamos en producción"""
    return os.getenv('FLASK_ENV') == 'production' or os.getenv('RENDER') == 'true'

def get_cache_timeout():
    """Obtiene timeout de caché según el entorno"""
    if is_production():
        return 86400  # 24 horas en producción
    else:
        return 3600   # 1 hora en desarrollo 