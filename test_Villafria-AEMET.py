#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para obtener datos meteorológicos de la estación de Burgos Villafría
a través de la API de AEMET OpenData

Autor: Script generado para acceso a datos AEMET
Fecha: 2025
"""

import requests
import json
import time
from datetime import datetime

class AEMETWeatherAPI:
    def __init__(self, api_key):
        """
        Inicializa la clase con la API key de AEMET
        
        Args:
            api_key (str): Clave de acceso a la API de AEMET
        """
        self.api_key = api_key
        self.base_url = "https://opendata.aemet.es/opendata/api"
        self.session = requests.Session()
        # Configurar headers por defecto
        self.session.headers.update({
            'api_key': self.api_key,
            'Accept': 'application/json',
            'User-Agent': 'Python-AEMET-Client/1.0'
        })
        
        # ID de la estación de Burgos Villafría
        self.estacion_villafria = "2331"
        
    def test_api_key(self):
        """
        Prueba si la API key es válida haciendo una petición de test
        """
        print("🔑 Verificando API key...")
        
        # Probamos con un endpoint simple
        url = f"{self.base_url}/observacion/convencional/todas"
        
        try:
            response = self.session.get(url, timeout=10)
            print(f"Status Code: {response.status_code}")
            print(f"Headers de respuesta: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("✅ API key válida")
                return True
            elif response.status_code == 401:
                print("❌ API key inválida o expirada")
                print("Verifica que tu API key sea correcta y esté activa")
                return False
            elif response.status_code == 429:
                print("⏳ Límite de peticiones alcanzado")
                return False
            else:
                print(f"❌ Error desconocido: {response.status_code}")
                print(f"Respuesta: {response.text[:200]}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión: {e}")
            return False
    
    def obtener_datos_estacion(self, codigo_estacion=None):
        """
        Obtiene los datos meteorológicos de una estación específica
        
        Args:
            codigo_estacion (str): Código de la estación (por defecto Villafría)
        
        Returns:
            dict: Datos meteorológicos o None si hay error
        """
        if codigo_estacion is None:
            codigo_estacion = self.estacion_villafria
            
        print(f"🌡️  Obteniendo datos de la estación {codigo_estacion}...")
        
        # Paso 1: Obtener todas las observaciones
        url_observaciones = f"{self.base_url}/observacion/convencional/todas"
        
        try:
            # Primera petición para obtener la URL de los datos
            response = self.session.get(url_observaciones, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Error en petición inicial: {response.status_code}")
                print(f"Respuesta: {response.text}")
                return None
            
            # Parsear respuesta JSON
            data = response.json()
            
            if 'datos' not in data:
                print("❌ Respuesta no contiene campo 'datos'")
                print(f"Respuesta completa: {data}")
                return None
            
            # Paso 2: Obtener los datos reales
            url_datos = data['datos']
            print(f"📡 Obteniendo datos desde: {url_datos}")
            
            response_datos = self.session.get(url_datos, timeout=10)
            
            if response_datos.status_code != 200:
                print(f"❌ Error obteniendo datos reales: {response_datos.status_code}")
                return None
            
            # Parsear datos meteorológicos
            observaciones = response_datos.json()
            
            # Buscar la estación específica
            for observacion in observaciones:
                if observacion.get('idema') == codigo_estacion:
                    return observacion
            
            print(f"❌ No se encontró la estación {codigo_estacion}")
            print("Estaciones disponibles:")
            for obs in observaciones[:5]:  # Mostrar solo las primeras 5
                print(f"  - {obs.get('idema', 'N/A')}: {obs.get('ubi', 'Sin nombre')}")
            
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Error parseando JSON: {e}")
            return None
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return None
    
    def formatear_datos(self, datos):
        """
        Formatea los datos meteorológicos para mostrar de forma legible
        
        Args:
            datos (dict): Datos de la estación
        
        Returns:
            str: Datos formateados
        """
        if not datos:
            return "❌ No hay datos disponibles"
        
        # Mapeo de campos comunes
        campos = {
            'idema': 'Código Estación',
            'ubi': 'Ubicación',
            'fint': 'Fecha/Hora Observación',
            'ta': 'Temperatura (°C)',
            'tamin': 'Temp. Mínima (°C)',
            'tamax': 'Temp. Máxima (°C)',
            'hr': 'Humedad Relativa (%)',
            'prec': 'Precipitación (mm)',
            'vv': 'Velocidad Viento (m/s)',
            'dv': 'Dirección Viento (°)',
            'vmax': 'Racha Máxima (m/s)',
            'pres': 'Presión (hPa)',
            'vis': 'Visibilidad (km)'
        }
        
        resultado = []
        resultado.append("🌟 DATOS METEOROLÓGICOS - BURGOS VILLAFRÍA")
        resultado.append("=" * 50)
        
        for clave, descripcion in campos.items():
            valor = datos.get(clave)
            if valor is not None and valor != "":
                # Formateo especial para fecha
                if clave == 'fint':
                    try:
                        # Convertir timestamp a fecha legible
                        if 'T' in str(valor):
                            fecha = datetime.fromisoformat(valor.replace('Z', '+00:00'))
                            valor = fecha.strftime("%d/%m/%Y %H:%M UTC")
                    except:
                        pass
                
                resultado.append(f"{descripcion:.<25}: {valor}")
        
        # Mostrar todos los campos disponibles (debug)
        resultado.append("\n🔍 TODOS LOS CAMPOS DISPONIBLES:")
        resultado.append("-" * 30)
        for clave, valor in datos.items():
            if clave not in campos and valor is not None and valor != "":
                resultado.append(f"{clave:.<25}: {valor}")
        
        return "\n".join(resultado)

def main():
    """
    Función principal del script
    """
    print("🌤️  Script de datos meteorológicos - Estación Burgos Villafría")
    print("=" * 60)
    
    # CONFIGURACIÓN: Reemplaza 'TU_API_KEY_AQUI' con tu clave real
    API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqNGFsb25zb0BnbWFpbC5jb20iLCJqdGkiOiI2NWE3MWZmOS1jMjgzLTRmOTMtYjE5NS05YzQ1ZjBmNzI1YTgiLCJpc3MiOiJBRU1FVCIsImlhdCI6MTczOTUyNTYxOSwidXNlcklkIjoiNjVhNzFmZjktYzI4My00ZjkzLWIxOTUtOWM0NWYwZjcyNWE4Iiwicm9sZSI6IiJ9.6cauQ28EPJdrTPc5YIRl0UrIh_76uUP6WYYvIgJKU88"
    
    if API_KEY == "TU_API_KEY_AQUI":
        print("❌ ERROR: Debes configurar tu API key en la variable API_KEY")
        print("Edita el script y reemplaza 'TU_API_KEY_AQUI' con tu clave de AEMET")
        return
    
    # Crear instancia de la API
    api = AEMETWeatherAPI(API_KEY)
    
    # Verificar API key
    if not api.test_api_key():
        print("\n❌ No se puede continuar sin una API key válida")
        print("\nPasos para obtener/verificar tu API key:")
        print("1. Ve a: https://opendata.aemet.es/centrodedescargas/obtencionAPIKey")
        print("2. Solicita una nueva API key con tu email")
        print("3. Revisa tu email para activar la clave")
        print("4. Verifica que la clave esté activa en tu perfil de AEMET")
        return
    
    print("\n" + "="*60)
    
    # Obtener datos de Villafría
    datos = api.obtener_datos_estacion()
    
    if datos:
        print(api.formatear_datos(datos))
        
        # Guardar datos en archivo JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"villafria_datos_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Datos guardados en: {filename}")
        except Exception as e:
            print(f"\n❌ Error guardando archivo: {e}")
    
    else:
        print("❌ No se pudieron obtener los datos de la estación")
        print("\nPosibles soluciones:")
        print("1. Verifica tu conexión a internet")
        print("2. Comprueba que tu API key esté activa")
        print("3. La estación podría estar temporalmente sin datos")
        print("4. Revisa los logs anteriores para más detalles")

if __name__ == "__main__":
    main()