#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para actualizar datos históricos de Burgos
Versión simplificada para testing antes de automatizar

Autor: Generado para meteosarria.com
Fecha: 2025-08-10
"""

import sys
import os

# Añadir el directorio actual al path para importar el módulo
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from update_burgos_historico import BurgosHistoricoUpdater
import logging
from datetime import date

# Configurar logging para testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def test_actualizacion():
    """Función de prueba para la actualización"""
    
    print("SCRIPT DE PRUEBA - ACTUALIZACION DATOS BURGOS")
    print("=" * 60)
    
    # Configuración
    API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqNGFsb25zb0BnbWFpbC5jb20iLCJqdGkiOiI2NWE3MWZmOS1jMjgzLTRmOTMtYjE5NS05YzQ1ZjBmNzI1YTgiLCJpc3MiOiJBRU1FVCIsImlhdCI6MTczOTUyNTYxOSwidXNlcklkIjoiNjVhNzFmZjktYzI4My00ZjkzLWIxOTUtOWM0NWYwZjcyNWE4Iiwicm9sZSI6IiJ9.6cauQ28EPJdrTPc5YIRl0UrIh_76uUP6WYYvIgJKU88"
    MONGODB_URI = "mongodb+srv://tervingo:mig.langar.inn@gagnagunnur.okrh1.mongodb.net/meteosarria"
    
    try:
        # Crear updater
        updater = BurgosHistoricoUpdater(API_KEY, MONGODB_URI)
        
        # Mostrar información inicial
        ultima_fecha = updater.get_ultima_fecha_bd()
        print(f"Ultima fecha en BD: {ultima_fecha}")
        print(f"Fecha de hoy: {date.today()}")
        
        if ultima_fecha:
            dias_diferencia = (date.today() - ultima_fecha).days
            print(f"Dias faltantes: {dias_diferencia}")
            
            if dias_diferencia == 0:
                print("La base de datos ya esta actualizada")
                return True
            elif dias_diferencia < 0:
                print("La ultima fecha en BD es posterior a hoy (problema de fechas)")
                return False
        
        # Ejecutar actualización
        print("\nIniciando actualizacion...")
        success = updater.actualizar_datos()
        
        if success:
            print("Actualizacion completada exitosamente")
            return True
        else:
            print("Actualizacion fallo")
            return False
            
    except Exception as e:
        print(f"Error durante la prueba: {e}")
        return False

def verificar_datos_recientes():
    """Verifica los datos más recientes en la BD"""
    
    print("\nVERIFICANDO DATOS RECIENTES EN BD")
    print("-" * 40)
    
    try:
        from pymongo import MongoClient
        
        MONGODB_URI = "mongodb+srv://tervingo:mig.langar.inn@gagnagunnur.okrh1.mongodb.net/meteosarria"
        client = MongoClient(MONGODB_URI)
        db = client.meteosarria
        collection = db.burgos_historico_temps
        
        # Obtener los 5 registros más recientes
        registros_recientes = collection.find().sort("fecha_datetime", -1).limit(5)
        
        print("Ultimos 5 registros en BD:")
        for i, registro in enumerate(registros_recientes, 1):
            fecha = registro.get('fecha', 'N/A')
            temp_max = registro.get('temp_maxima', 'N/A')
            temp_min = registro.get('temp_minima', 'N/A')
            source = registro.get('source', 'N/A')
            
            print(f"  {i}. {fecha} | Max: {temp_max}C | Min: {temp_min}C | Fuente: {source}")
        
        # Contar total de registros
        total_registros = collection.count_documents({})
        print(f"\nTotal de registros en BD: {total_registros}")
        
        client.close()
        
    except Exception as e:
        print(f"Error verificando datos: {e}")

if __name__ == "__main__":
    print("BURGOS HISTORICO - SCRIPT DE PRUEBA")
    print("=" * 50)
    
    # Verificar datos actuales
    verificar_datos_recientes()
    
    # Ejecutar actualización de prueba
    success = test_actualizacion()
    
    # Verificar datos después de actualización
    if success:
        verificar_datos_recientes()
    
    print("\n" + "=" * 50)
    print("Prueba completada" if success else "Prueba fallo")