#!/usr/bin/env python3
"""
Script optimizado para migrar datos_meteohub.csv a MongoDB
Con agregación temporal para reducir volumen de datos
"""

import csv
import pymongo
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from collections import defaultdict
import statistics

# Cargar variables de entorno
load_dotenv()

class DataAggregator:
    def __init__(self, interval_minutes=30):
        self.interval_minutes = interval_minutes
        self.data_buckets = defaultdict(list)
    
    def add_reading(self, timestamp, temp, hum):
        """Añadir lectura a bucket temporal"""
        # Redondear timestamp al intervalo más cercano
        bucket_time = self.round_to_interval(timestamp)
        self.data_buckets[bucket_time].append({
            'temp': temp,
            'hum': hum,
            'original_time': timestamp
        })
    
    def round_to_interval(self, dt):
        """Redondear datetime al intervalo especificado"""
        minutes = (dt.minute // self.interval_minutes) * self.interval_minutes
        return dt.replace(minute=minutes, second=0, microsecond=0)
    
    def get_aggregated_data(self):
        """Obtener datos agregados"""
        aggregated = []
        
        for bucket_time, readings in self.data_buckets.items():
            if not readings:
                continue
                
            temps = [r['temp'] for r in readings]
            hums = [r['hum'] for r in readings]
            
            # Calcular estadísticas
            temp_stats = {
                'promedio': round(statistics.mean(temps), 1),
                'minima': min(temps),
                'maxima': max(temps)
            }
            
            hum_stats = {
                'promedio': round(statistics.mean(hums), 1),
                'minima': min(hums),
                'maxima': max(hums)
            }
            
            doc = {
                "timestamp": bucket_time,
                "fecha": bucket_time.strftime("%Y-%m-%d"),
                "hora": bucket_time.strftime("%H:%M:%S"),
                "año": bucket_time.year,
                "mes": bucket_time.month,
                "dia": bucket_time.day,
                "temperatura": temp_stats,
                "humedad": hum_stats,
                "num_lecturas": len(readings),
                "intervalo_minutos": self.interval_minutes,
                "created_at": datetime.utcnow()
            }
            
            aggregated.append(doc)
        
        return sorted(aggregated, key=lambda x: x['timestamp'])

def parse_csv_line(row):
    """Parsear línea CSV"""
    try:
        fecha_str = row[0]
        temp_value = float(row[2])
        hum_value = float(row[4])
        
        fecha_dt = datetime.strptime(fecha_str, "%d-%m-%YT%H:%M:%S")
        
        return fecha_dt, temp_value, hum_value
    except (ValueError, IndexError) as e:
        return None, None, None

def create_daily_summaries(aggregated_data):
    """Crear resúmenes diarios adicionales"""
    daily_data = defaultdict(list)
    
    # Agrupar por día
    for doc in aggregated_data:
        date_key = doc['fecha']
        daily_data[date_key].append(doc)
    
    daily_summaries = []
    
    for date_str, day_docs in daily_data.items():
        if not day_docs:
            continue
            
        # Extraer todas las temperaturas y humedades del día
        all_temps = []
        all_hums = []
        
        for doc in day_docs:
            all_temps.extend([doc['temperatura']['minima'], 
                            doc['temperatura']['maxima']])
            all_hums.extend([doc['humedad']['minima'], 
                           doc['humedad']['maxima']])
        
        if all_temps and all_hums:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            
            summary = {
                "timestamp": date_obj,
                "fecha": date_str,
                "año": date_obj.year,
                "mes": date_obj.month,
                "dia": date_obj.day,
                "tipo": "resumen_diario",
                "temperatura": {
                    "minima": min(all_temps),
                    "maxima": max(all_temps),
                    "promedio": round(statistics.mean(all_temps), 1)
                },
                "humedad": {
                    "minima": min(all_hums),
                    "maxima": max(all_hums),
                    "promedio": round(statistics.mean(all_hums), 1)
                },
                "num_intervalos": len(day_docs),
                "created_at": datetime.utcnow()
            }
            
            daily_summaries.append(summary)
    
    return daily_summaries

def migrate_with_aggregation(csv_file_path, mongodb_uri, interval_minutes=30):
    """Migrar con agregación temporal"""
    try:
        # Conectar a MongoDB
        client = pymongo.MongoClient(mongodb_uri)
        db = client["meteosarria"]
        
        # Dos colecciones: intervalos y resúmenes diarios
        collection_intervals = db["historico_intervalos"]
        collection_daily = db["historico_diario"]
        
        print(f"Procesando CSV con intervalos de {interval_minutes} minutos...")
        
        # Procesar CSV
        aggregator = DataAggregator(interval_minutes)
        lineas_procesadas = 0
        lineas_error = 0
        
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            
            for row in csv_reader:
                if len(row) >= 5:
                    timestamp, temp, hum = parse_csv_line(row)
                    if timestamp and temp is not None and hum is not None:
                        aggregator.add_reading(timestamp, temp, hum)
                        lineas_procesadas += 1
                    else:
                        lineas_error += 1
                else:
                    lineas_error += 1
        
        print(f"Líneas procesadas: {lineas_procesadas}")
        print(f"Líneas con error: {lineas_error}")
        
        # Obtener datos agregados
        aggregated_data = aggregator.get_aggregated_data()
        print(f"Intervalos creados: {len(aggregated_data)}")
        
        # Limpiar colecciones existentes
        collection_intervals.delete_many({})
        collection_daily.delete_many({})
        
        # Insertar datos por intervalos
        if aggregated_data:
            collection_intervals.insert_many(aggregated_data)
            print(f"Insertados {len(aggregated_data)} intervalos")
        
        # Crear resúmenes diarios
        daily_summaries = create_daily_summaries(aggregated_data)
        if daily_summaries:
            collection_daily.insert_many(daily_summaries)
            print(f"Insertados {len(daily_summaries)} resúmenes diarios")
        
        # Crear índices
        print("Creando índices...")
        collection_intervals.create_index([("timestamp", 1)])
        collection_intervals.create_index([("año", 1), ("mes", 1)])
        collection_intervals.create_index([("fecha", 1)])
        
        collection_daily.create_index([("timestamp", 1)])
        collection_daily.create_index([("año", 1), ("mes", 1)])
        collection_daily.create_index([("fecha", 1)])
        
        # Estadísticas finales
        print(f"\n=== MIGRACIÓN COMPLETADA ===")
        print(f"Colección intervalos: {collection_intervals.count_documents({})} docs")
        print(f"Colección diaria: {collection_daily.count_documents({})} docs")
        
        # Mostrar rango de fechas
        primer_intervalo = collection_intervals.find().sort("timestamp", 1).limit(1)
        ultimo_intervalo = collection_intervals.find().sort("timestamp", -1).limit(1)
        
        for doc in primer_intervalo:
            print(f"Fecha más antigua: {doc['timestamp']}")
        for doc in ultimo_intervalo:
            print(f"Fecha más reciente: {doc['timestamp']}")
        
        # Calcular reducción de espacio
        total_lecturas = sum(doc['num_lecturas'] for doc in aggregated_data)
        reduccion = ((total_lecturas - len(aggregated_data)) / total_lecturas) * 100
        print(f"Reducción de datos: {reduccion:.1f}% ({total_lecturas} → {len(aggregated_data)})")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"Error durante la migración: {e}")
        return False

def main():
    """Función principal con opciones de configuración"""
    CSV_FILE = "C:\\Users\\j4alo\\OneDrive\\Documentos\\Meteohub_data\\datos_meteohub.csv"
    MONGODB_URI = os.getenv("MONGODB_URI")
    
    if not MONGODB_URI:
        print("Error: MONGODB_URI no encontrado en variables de entorno")
        return
    
    if not os.path.exists(CSV_FILE):
        print(f"Error: Archivo {CSV_FILE} no encontrado")
        return
    
    print("=== MIGRACIÓN OPTIMIZADA CSV → MongoDB ===")
    print("Opciones de agregación:")
    print("1. Intervalos de 30 minutos (recomendado)")
    print("2. Intervalos de 1 hora")
    print("3. Solo resúmenes diarios")
    
    opcion = input("Selecciona opción (1-3): ").strip()
    
    if opcion == "1":
        interval_minutes = 30
    elif opcion == "2":
        interval_minutes = 60
    elif opcion == "3":
        interval_minutes = 1440  # 24 horas
    else:
        print("Opción no válida, usando 30 minutos por defecto")
        interval_minutes = 30
    
    print(f"Procesando con intervalos de {interval_minutes} minutos")
    respuesta = input("¿Continuar? (s/n): ")
    
    if respuesta.lower() != 's':
        print("Migración cancelada")
        return
    
    success = migrate_with_aggregation(CSV_FILE, MONGODB_URI, interval_minutes)
    
    if success:
        print("🎉 Migración completada exitosamente")
    else:
        print("❌ Error en la migración")

if __name__ == "__main__":
    main()