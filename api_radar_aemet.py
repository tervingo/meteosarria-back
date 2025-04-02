from flask import Blueprint, jsonify
import logging
import os
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Blueprint
radar_bp = Blueprint('radar', __name__)

# URL de ejemplo para pruebas (imagen de radar peninsular de muestra)
SAMPLE_RADAR_URL = "https://www.aemet.es/imagenes_d/eltiempo/observacion/radar/r8pen_202403310100.jpg"

DEVELOPMENT_MODE = True

@radar_bp.route('/api/radar/peninsula', methods=['GET'])
def obtener_radar_peninsula():
    """
    Obtiene datos del radar meteorológico de la Península de AEMET.
    
    :return: JSON con la URL de la imagen del radar y metadatos
    """
    # En modo desarrollo sin API key, devolver una URL de muestra
    if DEVELOPMENT_MODE and not AEMET_API_KEY:
        logger.info("Usando URL de radar de muestra para desarrollo")
        return jsonify({
            'tipo': 'imagen',
            'formato': 'image/jpeg',
            'url': SAMPLE_RADAR_URL,
            'timestamp': datetime.now().isoformat(),
            'mode': 'development_sample'
        })
    
    # Utilizamos el radar regional para la península
    endpoint = f"{AEMET_BASE_URL}/red/radar/nacional"
    
    try:
        # Realizar petición a la API de AEMET
        params = {'api_key': AEMET_API_KEY}
        response = requests.get(endpoint, params=params)
        
        # Comprobar si la petición fue exitosa
        if response.status_code != 200:
            logger.error(f"Error en la petición a AEMET: {response.status_code}, {response.text}")
            return jsonify({
                'error': 'Error al obtener datos del radar',
                'status': response.status_code
            }), response.status_code
        
        # La API de AEMET devuelve una URL donde se encuentran los datos reales
        data = response.json()
        
        # Verificar si AEMET devolvió un error interno (puede devolver 200 pero con error)
        if 'estado' in data and data['estado'] != 200:
            error_msg = data.get('descripcion', 'Error desconocido en la API de AEMET')
            logger.error(f"Error interno de AEMET: {error_msg}")
            
            # Si estamos en modo desarrollo, usar la imagen de muestra
            if DEVELOPMENT_MODE:
                logger.info("Usando URL de radar de muestra debido a error de AEMET")
                return jsonify({
                    'tipo': 'imagen',
                    'formato': 'image/jpeg',
                    'url': SAMPLE_RADAR_URL,
                    'timestamp': datetime.now().isoformat(),
                    'mode': 'development_sample_fallback',
                    'aemet_error': error_msg
                })
            
            return jsonify({
                'error': f'Error de AEMET: {error_msg}',
                'status': data.get('estado', 500)
            }), 500
        
        if 'datos' not in data:
            logger.error(f"Respuesta inesperada de AEMET: {data}")
            
            # Si estamos en modo desarrollo, usar la imagen de muestra
            if DEVELOPMENT_MODE:
                logger.info("Usando URL de radar de muestra debido a formato inesperado")
                return jsonify({
                    'tipo': 'imagen',
                    'formato': 'image/jpeg',
                    'url': SAMPLE_RADAR_URL,
                    'timestamp': datetime.now().isoformat(),
                    'mode': 'development_sample_fallback'
                })
                
            return jsonify({'error': 'Formato de respuesta inesperado'}), 500
        
        # Obtener los datos reales (normalmente una imagen o un JSON con la URL de la imagen)
        try:
            datos_response = requests.get(data['datos'], timeout=10)  # Añadir timeout
            
            if datos_response.status_code != 200:
                logger.error(f"Error al obtener datos de la URL proporcionada: {datos_response.status_code}")
                
                # Si estamos en modo desarrollo, usar la imagen de muestra
                if DEVELOPMENT_MODE:
                    logger.info("Usando URL de radar de muestra debido a error en datos")
                    return jsonify({
                        'tipo': 'imagen',
                        'formato': 'image/jpeg',
                        'url': SAMPLE_RADAR_URL,
                        'timestamp': datetime.now().isoformat(),
                        'mode': 'development_sample_fallback'
                    })
                    
                return jsonify({'error': 'Error al obtener la imagen del radar'}), datos_response.status_code
            
            # Si la respuesta es una imagen directamente
            if 'image' in datos_response.headers.get('Content-Type', ''):
                # En una implementación real, podrías almacenar esta imagen temporalmente
                # y devolver su URL, o convertirla a base64
                return jsonify({
                    'tipo': 'imagen',
                    'formato': datos_response.headers.get('Content-Type'),
                    'url': data['datos'],  # URL directa para que el frontend la use
                    'timestamp': datetime.now().isoformat()
                })
            
            # Si la respuesta es JSON con metadatos
            try:
                metadatos = datos_response.json()
                return jsonify({
                    'tipo': 'json',
                    'datos': metadatos,
                    'timestamp': datetime.now().isoformat()
                })
            except:
                # Si no es JSON ni una imagen reconocible, devolvemos la URL directa
                return jsonify({
                    'tipo': 'desconocido',
                    'url': data['datos'],
                    'timestamp': datetime.now().isoformat()
                })
                
        except requests.RequestException as e:
            logger.exception(f"Error al obtener datos de la URL {data.get('datos')}: {str(e)}")
            
            # Si estamos en modo desarrollo, usar la imagen de muestra
            if DEVELOPMENT_MODE:
                logger.info("Usando URL de radar de muestra debido a error de conexión")
                return jsonify({
                    'tipo': 'imagen',
                    'formato': 'image/jpeg',
                    'url': SAMPLE_RADAR_URL,
                    'timestamp': datetime.now().isoformat(),
                    'mode': 'development_sample_fallback'
                })
                
            return jsonify({'error': f'Error al acceder a los datos: {str(e)}'}), 500
            
    except requests.RequestException as e:
        logger.exception("Error en la conexión con la API de AEMET")
        return jsonify({'error': f'Error de conexión: {str(e)}'}), 500
    except Exception as e:
        logger.exception("Error inesperado")
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500

@radar_bp.route('/api/radar/estado', methods=['GET'])
def verificar_estado():
    """
    Verifica la conectividad con la API de AEMET
    """
    try:
        response = requests.get(f"{AEMET_BASE_URL}/red/radar/nacional", 
                               params={'api_key': AEMET_API_KEY})
        
        if response.status_code == 200:
            return jsonify({
                'estado': 'OK',
                'mensaje': 'Conexión con AEMET establecida correctamente',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'estado': 'ERROR',
                'mensaje': f'Error de conexión con AEMET: {response.status_code}',
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        return jsonify({
            'estado': 'ERROR',
            'mensaje': f'Error al verificar estado: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500 