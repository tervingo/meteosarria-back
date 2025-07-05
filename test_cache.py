#!/usr/bin/env python3
"""
Script de prueba para el sistema de caché inteligente
"""

import requests
import time
import json
from datetime import datetime

# URL base del API
BASE_URL = "http://localhost:5000"

def test_cache_performance():
    """Prueba el rendimiento del caché"""
    
    print("=== PRUEBA DE RENDIMIENTO DEL CACHÉ ===")
    print(f"Fecha de prueba: {datetime.now()}")
    print()
    
    # Endpoints a probar
    endpoints = [
        "/api/dashboard/records",
        "/api/dashboard/tendencia-anual", 
        "/api/dashboard/comparativa-año",
        "/api/dashboard/heatmap",
        "/api/dashboard/estadisticas"
    ]
    
    for endpoint in endpoints:
        print(f"Probando endpoint: {endpoint}")
        
        # Primera llamada (cache miss)
        start_time = time.time()
        response1 = requests.get(f"{BASE_URL}{endpoint}")
        time1 = time.time() - start_time
        
        # Segunda llamada (cache hit)
        start_time = time.time()
        response2 = requests.get(f"{BASE_URL}{endpoint}")
        time2 = time.time() - start_time
        
        # Tercera llamada (cache hit)
        start_time = time.time()
        response3 = requests.get(f"{BASE_URL}{endpoint}")
        time3 = time.time() - start_time
        
        print(f"  Primera llamada (cache miss): {time1:.3f}s")
        print(f"  Segunda llamada (cache hit):  {time2:.3f}s")
        print(f"  Tercera llamada (cache hit):  {time3:.3f}s")
        
        if time1 > 0:
            improvement = ((time1 - time2) / time1) * 100
            print(f"  Mejora: {improvement:.1f}%")
        
        print(f"  Status: {response1.status_code}")
        print()

def test_cache_status():
    """Prueba el endpoint de estado del caché"""
    
    print("=== ESTADO DEL CACHÉ ===")
    
    try:
        response = requests.get(f"{BASE_URL}/api/dashboard/cache/status")
        if response.status_code == 200:
            cache_info = response.json()
            print(f"Tipo de caché: {cache_info.get('cache_type')}")
            print(f"Timeout: {cache_info.get('cache_timeout')}s")
            print(f"Prefijo: {cache_info.get('cache_prefix')}")
            print(f"Fecha actual: {cache_info.get('current_date')}")
            print(f"Caché habilitado: {cache_info.get('cache_enabled')}")
        else:
            print(f"Error: {response.status_code}")
    except Exception as e:
        print(f"Error conectando al servidor: {e}")
    
    print()

def test_cache_clear():
    """Prueba la limpieza del caché"""
    
    print("=== LIMPIEZA DEL CACHÉ ===")
    
    try:
        response = requests.post(f"{BASE_URL}/api/dashboard/cache/clear")
        if response.status_code == 200:
            result = response.json()
            print(f"Status: {result.get('status')}")
            print(f"Mensaje: {result.get('message')}")
            print(f"Timestamp: {result.get('timestamp')}")
        else:
            print(f"Error: {response.status_code}")
    except Exception as e:
        print(f"Error conectando al servidor: {e}")
    
    print()

def test_data_freshness():
    """Prueba que los datos actuales no están cacheados"""
    
    print("=== PRUEBA DE FRESCURA DE DATOS ===")
    
    # Probar endpoint que incluye datos actuales
    endpoints_with_current = [
        "/api/dashboard/records",  # Incluye records del año actual
        "/api/dashboard/tendencia-anual",  # Incluye datos del año actual
        "/api/dashboard/estadisticas"  # Incluye datos del mes actual
    ]
    
    for endpoint in endpoints_with_current:
        print(f"Probando: {endpoint}")
        
        # Hacer múltiples llamadas para verificar que los datos actuales se actualizan
        responses = []
        for i in range(3):
            response = requests.get(f"{BASE_URL}{endpoint}")
            if response.status_code == 200:
                data = response.json()
                responses.append(data)
                print(f"  Llamada {i+1}: Status {response.status_code}")
            else:
                print(f"  Llamada {i+1}: Error {response.status_code}")
        
        # Verificar que las respuestas son consistentes
        if len(responses) >= 2:
            if responses[0] == responses[1]:
                print("  ✓ Respuestas consistentes (caché funcionando)")
            else:
                print("  ⚠ Respuestas diferentes (datos actuales se actualizan)")
        
        print()

if __name__ == "__main__":
    print("Iniciando pruebas del sistema de caché...")
    print("Asegúrate de que el servidor Flask esté ejecutándose en localhost:5000")
    print()
    
    try:
        # Probar estado del caché
        test_cache_status()
        
        # Probar rendimiento
        test_cache_performance()
        
        # Probar frescura de datos
        test_data_freshness()
        
        # Probar limpieza
        test_cache_clear()
        
        print("=== PRUEBAS COMPLETADAS ===")
        
    except KeyboardInterrupt:
        print("\nPruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"Error durante las pruebas: {e}") 