#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para probar qué datos están disponibles en AEMET
"""

import requests
import json
from datetime import datetime, date, timedelta

def test_aemet_data():
    """Prueba qué datos están disponibles en AEMET"""
    
    print("TEST: DATOS DISPONIBLES EN AEMET")
    print("=" * 40)
    
    API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqNGFsb25zb0BnbWFpbC5jb20iLCJqdGkiOiI2NWE3MWZmOS1jMjgzLTRmOTMtYjE5NS05YzQ1ZjBmNzI1YTgiLCJpc3MiOiJBRU1FVCIsImlhdCI6MTczOTUyNTYxOSwidXNlcklkIjoiNjVhNzFmZjktYzI4My00ZjkzLWIxOTUtOWM0NWYwZjcyNWE4Iiwicm9sZSI6IiJ9.6cauQ28EPJdrTPc5YIRl0UrIh_76uUP6WYYvIgJKU88"
    base_url = "https://opendata.aemet.es/opendata/api"
    estacion_villafria = "2331"
    
    session = requests.Session()
    session.headers.update({
        'api_key': API_KEY,
        'Accept': 'application/json',
        'User-Agent': 'Python-AEMET-Test/1.0'
    })
    
    # Probar diferentes endpoints y fechas
    fechas_test = [
        date.today() - timedelta(days=1),  # Ayer
        date.today() - timedelta(days=2),  # Antesdeayer
        date.today() - timedelta(days=3),  # Hace 3 días
    ]
    
    for fecha in fechas_test:
        print(f"\nProbando datos para: {fecha}")
        
        try:
            # 1. Endpoint de observación convencional por estación
            fecha_str = fecha.strftime("%Y-%m-%d")
            url = f"{base_url}/observacion/convencional/datos/estacion/{estacion_villafria}/fechaini/{fecha_str}T00:00:00UTC/fechafin/{fecha_str}T23:59:59UTC"
            
            print(f"  URL: {url}")
            
            response = session.get(url, timeout=15)
            print(f"  Status code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if 'datos' in data:
                    # Obtener datos reales
                    response_datos = session.get(data['datos'], timeout=15)
                    if response_datos.status_code == 200:
                        observaciones = response_datos.json()
                        print(f"  Observaciones encontradas: {len(observaciones)}")
                        
                        if observaciones:
                            # Mostrar una muestra
                            obs = observaciones[0] if isinstance(observaciones, list) else observaciones
                            print(f"  Ejemplo - Fecha: {obs.get('fint', 'N/A')}")
                            print(f"  Ejemplo - Temp max: {obs.get('tamax', 'N/A')}C")
                            print(f"  Ejemplo - Temp min: {obs.get('tamin', 'N/A')}C")
                            print(f"  Ejemplo - Temp actual: {obs.get('ta', 'N/A')}C")
                        else:
                            print("  Sin observaciones")
                    else:
                        print(f"  Error obteniendo datos: {response_datos.status_code}")
                else:
                    print("  Respuesta sin campo 'datos'")
            elif response.status_code == 404:
                print("  No hay datos disponibles (404)")
            else:
                print(f"  Error: {response.status_code} - {response.text[:100]}")
                
        except Exception as e:
            print(f"  Error: {e}")
    
    # 2. Probar endpoint de datos más recientes sin fecha específica
    print(f"\nProbando datos más recientes de la estación (sin fecha específica):")
    try:
        url = f"{base_url}/observacion/convencional/datos/estacion/{estacion_villafria}"
        response = session.get(url, timeout=15)
        print(f"  Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'datos' in data:
                response_datos = session.get(data['datos'], timeout=15)
                if response_datos.status_code == 200:
                    observaciones = response_datos.json()
                    print(f"  Observaciones encontradas: {len(observaciones)}")
                    
                    if observaciones:
                        # Mostrar las más recientes
                        obs_recientes = observaciones[-3:] if len(observaciones) >= 3 else observaciones
                        print("  Observaciones más recientes:")
                        for i, obs in enumerate(obs_recientes):
                            print(f"    {i+1}. {obs.get('fint', 'N/A')} | Temp: {obs.get('ta', 'N/A')}C | Max: {obs.get('tamax', 'N/A')}C | Min: {obs.get('tamin', 'N/A')}C")
                
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    test_aemet_data()