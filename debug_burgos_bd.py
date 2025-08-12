#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para debuggar los datos de Burgos en la BD
"""

from pymongo import MongoClient
from datetime import datetime

def debug_bd():
    """Debug de los datos en la BD"""
    
    print("DEBUG: DATOS DE BURGOS EN BD")
    print("=" * 40)
    
    try:
        MONGODB_URI = "mongodb+srv://tervingo:mig.langar.inn@gagnagunnur.okrh1.mongodb.net/meteosarria"
        client = MongoClient(MONGODB_URI)
        db = client.meteosarria
        collection = db.burgos_historico_temps
        
        # 1. Obtener los 10 registros más recientes por fecha_datetime
        print("\n1. Ultimos 10 registros por fecha_datetime:")
        registros_datetime = collection.find().sort("fecha_datetime", -1).limit(10)
        
        for i, registro in enumerate(registros_datetime, 1):
            fecha = registro.get('fecha', 'N/A')
            fecha_dt = registro.get('fecha_datetime', 'N/A')
            temp_max = registro.get('temp_maxima', 'N/A')
            temp_min = registro.get('temp_minima', 'N/A')
            source = registro.get('source', 'N/A')
            
            print(f"  {i}. {fecha} ({fecha_dt}) | Max: {temp_max}C | Min: {temp_min}C | {source}")
        
        # 2. Obtener los 10 registros más recientes por fecha (string)
        print("\n2. Ultimos 10 registros por fecha string:")
        registros_fecha = collection.find().sort("fecha", -1).limit(10)
        
        for i, registro in enumerate(registros_fecha, 1):
            fecha = registro.get('fecha', 'N/A')
            fecha_dt = registro.get('fecha_datetime', 'N/A')
            temp_max = registro.get('temp_maxima', 'N/A')
            temp_min = registro.get('temp_minima', 'N/A')
            source = registro.get('source', 'N/A')
            
            print(f"  {i}. {fecha} ({fecha_dt}) | Max: {temp_max}C | Min: {temp_min}C | {source}")
        
        # 3. Verificar el documento más reciente por fecha_datetime
        ultimo_por_datetime = collection.find().sort("fecha_datetime", -1).limit(1)
        ultimo_doc = list(ultimo_por_datetime)[0] if ultimo_por_datetime else None
        
        if ultimo_doc:
            print(f"\n3. Documento mas reciente por fecha_datetime:")
            print(f"   Fecha: {ultimo_doc.get('fecha')}")
            print(f"   Fecha datetime: {ultimo_doc.get('fecha_datetime')}")
            print(f"   Temp max: {ultimo_doc.get('temp_maxima')}")
            print(f"   Temp min: {ultimo_doc.get('temp_minima')}")
            print(f"   Source: {ultimo_doc.get('source')}")
            print(f"   ID: {ultimo_doc.get('_id')}")
        
        # 4. Contar registros totales
        total_registros = collection.count_documents({})
        print(f"\n4. Total de registros en BD: {total_registros}")
        
        # 5. Buscar específicamente el rango 2025-08-04 a 2025-08-10
        print(f"\n5. Registros entre 2025-08-04 y 2025-08-10:")
        registros_rango = collection.find({
            "fecha": {"$gte": "2025-08-04", "$lte": "2025-08-10"}
        }).sort("fecha", 1)
        
        count = 0
        for registro in registros_rango:
            count += 1
            fecha = registro.get('fecha', 'N/A')
            temp_max = registro.get('temp_maxima', 'N/A')
            temp_min = registro.get('temp_minima', 'N/A')
            source = registro.get('source', 'N/A')
            
            print(f"   {fecha} | Max: {temp_max}C | Min: {temp_min}C | {source}")
        
        if count == 0:
            print("   No se encontraron registros en este rango")
        
        client.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_bd()