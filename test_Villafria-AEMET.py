#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para obtener datos meteorológicos de la estación de Burgos Villafría
a través de la API de AEMET OpenData - VERSIÓN ACTUALIZADA

Usa el endpoint específico de la estación para mayor eficiencia

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
            'User-Agent': 'Python-AEMET-Client/2.0'
        })
        
        # ID de la estación de Burgos Villafría
        self.estacion_villafria = "2331"
        
    def test_api_key(self):
        """
        Prueba si la API key es válida haciendo una petición de test
        """
        print("🔑 Verificando API key...")
        
        # Probamos con el endpoint específico de Villafría
        url = f"{self.base_url}/observacion/convencional/datos/estacion/{self.estacion_villafria}"
        
        try:
            response = self.session.get(url, timeout=15)
            print(f"Status Code: {response.status_code}")
            print(f"Headers de respuesta: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("✅ API key válida y endpoint accesible")
                return True
            elif response.status_code == 401:
                print("❌ API key inválida o expirada")
                print("Verifica que tu API key sea correcta y esté activa")
                return False
            elif response.status_code == 404:
                print("❌ Estación no encontrada")
                print("Verifica que el código de estación sea correcto")
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
    
    def obtener_datos_estacion_villafria(self):
        """
        Obtiene los datos meteorológicos de la estación de Villafría
        
        Returns:
            dict: Datos meteorológicos más recientes o None si hay error
        """
        print(f"🌡️  Obteniendo datos de Villafría (estación {self.estacion_villafria})...")
        
        # Usar endpoint específico de la estación
        url_estacion = f"{self.base_url}/observacion/convencional/datos/estacion/{self.estacion_villafria}"
        
        try:
            # Primera petición para obtener la URL de los datos
            print(f"📡 Solicitando metadata: {url_estacion}")
            response = self.session.get(url_estacion, timeout=15)
            
            if response.status_code != 200:
                print(f"❌ Error en petición inicial: {response.status_code}")
                print(f"Respuesta: {response.text}")
                return None
            
            # Parsear respuesta JSON
            data = response.json()
            print(f"📄 Respuesta de metadata: {data}")
            
            if 'datos' not in data:
                print("❌ Respuesta no contiene campo 'datos'")
                print(f"Respuesta completa: {data}")
                return None
            
            # Segunda petición para obtener los datos reales
            url_datos = data['datos']
            print(f"📡 Obteniendo datos desde: {url_datos}")
            
            response_datos = self.session.get(url_datos, timeout=30)
            
            if response_datos.status_code != 200:
                print(f"❌ Error obteniendo datos reales: {response_datos.status_code}")
                return None
            
            # Parsear datos meteorológicos
            observaciones = response_datos.json()
            print(f"📋 Registros recibidos: {len(observaciones)}")
            
            if len(observaciones) == 0:
                print("❌ No se recibieron datos de la estación")
                return None
            
            # Tomar el registro más reciente (último en la lista)
            observacion_actual = observaciones[-1] if isinstance(observaciones, list) else observaciones
            
            # Verificar que sea de Villafría
            station_id = observacion_actual.get('idema')
            station_name = observacion_actual.get('ubi', 'Sin nombre')
            
            print(f"✅ Datos de: {station_id} - {station_name}")
            print(f"🕐 Hora observación: {observacion_actual.get('fint', 'N/A')}")
            
            return observacion_actual
            
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
            'vis': 'Visibilidad (km)',
            'inso': 'Insolación (W/m²)',
            'tpr': 'Punto de Rocío (°C)',
            'ts': 'Temperatura Suelo (°C)',
            'tss5cm': 'Temp. Suelo 5cm (°C)',
            'tss20cm': 'Temp. Suelo 20cm (°C)'
        }
        
        resultado = []
        resultado.append("🌟 DATOS METEOROLÓGICOS - BURGOS VILLAFRÍA")
        resultado.append("=" * 55)
        
        # Mostrar campos principales
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
                
                # Formateo especial para dirección del viento
                elif clave == 'dv' and isinstance(valor, (int, float)):
                    direcciones = [
                        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
                    ]
                    index = round(float(valor) / 22.5) % 16
                    direccion_texto = direcciones[index]
                    valor = f"{valor}° ({direccion_texto})"
                
                # Formateo especial para velocidad del viento (convertir a km/h)
                elif clave == 'vv' and isinstance(valor, (int, float)):
                    kmh = round(float(valor) * 3.6, 1)
                    valor = f"{valor} ({kmh} km/h)"
                
                resultado.append(f"{descripcion:.<30}: {valor}")
        
        # Mostrar campos adicionales disponibles
        resultado.append("\n🔍 OTROS CAMPOS DISPONIBLES:")
        resultado.append("-" * 35)
        for clave, valor in datos.items():
            if clave not in campos and valor is not None and valor != "":
                resultado.append(f"{clave:.<30}: {valor}")
        
        return "\n".join(resultado)

def main():
    """
    Función principal del script
    """
    print("🌤️  Script de datos meteorológicos - Estación Burgos Villafría v2.0")
    print("=" * 70)
    
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
    
    print("\n" + "="*70)
    
    # Obtener datos de Villafría
    datos = api.obtener_datos_estacion_villafria()
    
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