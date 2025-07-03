#!/usr/bin/env python3
"""
Script para migrar datos_meteohub.csv a MongoDB con limpieza de datos erróneos
Corrige temperaturas imposibles (como 70°C) usando el último valor válido
"""

import csv
import pymongo
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from collections import defaultdict
import statistics

load_dotenv()

class DataCleaner:
    def __init__(self, temp_min=-20, temp_max=50, hum_min=0, hum_max=100):
        """
        Inicializar limpiador de datos
        temp_min/max: Rango válido de temperaturas (°C)
        hum_min/max: Rango válido de humedad (%)
        """
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.hum_min = hum_min
        self.hum_max = hum_max
        self.last_valid_temp = None
        self.last_valid_hum = None
        self.corrections_made = 0
        
    def is_valid_temperature(self, temp):
        """Verificar si la temperatura está en rango válido"""
        return self.temp_min <= temp <= self.temp_max
    
    def is_valid_humidity(self, hum):
        """Verificar si la humedad está en rango válido"""
        return self.hum_min <= hum <= self.hum_max
    
    def clean_temperature(self, temp):
        """Limpiar temperatura, usar último valor válido si es errónea"""
        if self.is_valid_temperature(temp):
            self.last_valid_temp = temp
            return temp, False  # temp, fue_corregida
        else:
            self.corrections_made += 1
            if self.last_valid_temp is not None:
                print(f"⚠️  Temperatura corregida: {temp}°C → {self.last_valid_temp}°C")
                return self.last_valid_temp, True
            else:
                # Si no hay valor previo válido, usar un valor por defecto
                default_temp = 20.0
                self.last_valid_temp = default_temp
                print(f"⚠️  Temperatura corregida (sin valor previo): {temp}°C → {default_temp}°C")
                return default_temp, True
    
    def clean_humidity(self, hum):
        """Limpiar humedad, usar último valor válido si es errónea"""
        if self.is_valid_humidity(hum):
            self.last_valid_hum = hum
            return hum, False  # hum, fue_corregida
        else:
            self.corrections_made += 1
            if self.last_valid_hum is not None:
                print(f"⚠️  Humedad corregida: {hum}% → {self.last_valid_hum}%")
                return self.last_valid_hum, True
            else:
                # Si no hay valor previo válido, usar un valor por defecto
                default_hum = 50.0
                self.last_valid_hum = default_hum
                print(f"⚠️  Humedad corregida (sin valor previo): {hum}% → {default_hum}%")
                return default_hum, True

class DataAggregator:
    def __init__(self, interval_minutes=30):
        self.interval_minutes = interval_minutes
        self.data_buckets = defaultdict(list)
        self.cleaner = DataCleaner()
    
    def add_reading(self, timestamp, temp, hum):
        """Añadir lectura con limpieza de datos"""
        # Limpiar datos antes de agregar
        clean_temp, temp_corregida = self.cleaner.clean_temperature(temp)
        clean_hum, hum_corregida = self.cleaner.clean_humidity(hum)
        
        # Redondear timestamp al intervalo más cercano
        bucket_time = self.round_to_interval(timestamp)
        
        self.data_buckets[bucket_time].append({
            'temp': clean_temp,
            'hum': clean_hum,
            'original_time': timestamp,
            'temp_corregida': temp_corregida,
            'hum_corregida': hum_corregida,
            'temp_original': temp if temp_corregida else None,
            'hum_original': hum if hum_corregida else None
        })
    
    def round_to_interval(self, dt):
        """Redondear datetime al intervalo especificado"""
        minutes = (dt.minute // self.interval_minutes) * self.interval_minutes
        return dt.replace(minute=minutes, second=0, microsecond=0)
    
    def get_aggregated_data(self):
        """Obtener datos agregados con información de correcciones"""
        aggregated = []
        
        for bucket_time, readings in self.data_buckets.items():
            if not readings:
                continue
                
            temps = [r['temp'] for r in readings]
            hums = [r['hum'] for r in readings]
            
            # Contar correcciones en este intervalo
            temp_corrections = sum(1 for r in readings if r['temp_corregida'])
            hum_corrections = sum(1 for r in readings if r['hum_corregida'])
            
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
                "datos_corregidos": {
                    "temp_corrections": temp_corrections,
                    "hum_corrections": hum_corrections,
                    "total_corrections": temp_corrections + hum_corrections
                },
                "created_at": datetime.utcnow()
            }
            
            aggregated.append(doc)
        
        return sorted(aggregated, key=lambda x: x['timestamp'])
    
    def get_cleaning_stats(self):
        """Obtener estadísticas de limpieza"""
        return {
            "total_corrections": self.cleaner.corrections_made,
            "last_valid_temp": self.cleaner.last_valid_temp,
            "last_valid_hum": self.cleaner.last_valid_hum
        }

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

def migrate_with_cleaning(csv_file_path, mongodb_uri, interval_minutes=30):
    """Migrar con limpieza y agregación temporal"""
    try:
        # Conectar a MongoDB
        client = pymongo.MongoClient(mongodb_uri)
        db = client["meteosarria"]
        
        collection_intervals = db["historico_intervalos"]
        collection_daily = db["historico_diario"]
        
        print(f"🧹 Iniciando migración con limpieza de datos...")
        print(f"📊 Intervalos de {interval_minutes} minutos")
        print(f"🌡️  Rango válido temperaturas: -20°C a 50°C")
        print(f"💧 Rango válido humedad: 0% a 100%")
        
        # Procesar CSV con limpieza
        aggregator = DataAggregator(interval_minutes)
        lineas_procesadas = 0
        lineas_error = 0
        
        print("\n📖 Leyendo y limpiando datos del CSV...")
        
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            
            for row_num, row in enumerate(csv_reader, 1):
                if len(row) >= 5:
                    timestamp, temp, hum = parse_csv_line(row)
                    if timestamp and temp is not None and hum is not None:
                        aggregator.add_reading(timestamp, temp, hum)
                        lineas_procesadas += 1
                        
                        # Mostrar progreso cada 10000 líneas
                        if lineas_procesadas % 10000 == 0:
                            print(f"   Procesadas {lineas_procesadas} líneas...")
                    else:
                        lineas_error += 1
                else:
                    lineas_error += 1
        
        # Estadísticas de limpieza
        cleaning_stats = aggregator.get_cleaning_stats()
        
        print(f"\n📊 Datos procesados:")
        print(f"   ✅ Líneas procesadas: {lineas_procesadas:,}")
        print(f"   ❌ Líneas con error: {lineas_error:,}")
        print(f"   🧹 Correcciones realizadas: {cleaning_stats['total_corrections']:,}")
        
        # Obtener datos agregados
        aggregated_data = aggregator.get_aggregated_data()
        print(f"   📈 Intervalos creados: {len(aggregated_data):,}")
        
        # Crear resúmenes diarios
        print("\n📅 Creando resúmenes diarios...")
        daily_summaries = create_daily_summaries(aggregated_data)
        
        # Limpiar colecciones existentes
        print("\n🗑️  Limpiando colecciones existentes...")
        collection_intervals.delete_many({})
        collection_daily.delete_many({})
        
        # Insertar datos por intervalos
        if aggregated_data:
            print("💾 Insertando datos por intervalos...")
            collection_intervals.insert_many(aggregated_data)
            print(f"   ✅ Insertados {len(aggregated_data):,} intervalos")
        
        # Insertar resúmenes diarios
        if daily_summaries:
            print("💾 Insertando resúmenes diarios...")
            collection_daily.insert_many(daily_summaries)
            print(f"   ✅ Insertados {len(daily_summaries):,} resúmenes diarios")
        
        # Crear índices
        print("🔍 Creando índices...")
        collection_intervals.create_index([("timestamp", 1)])
        collection_intervals.create_index([("año", 1), ("mes", 1)])
        collection_intervals.create_index([("fecha", 1)])
        
        collection_daily.create_index([("timestamp", 1)])
        collection_daily.create_index([("año", 1), ("mes", 1)])
        collection_daily.create_index([("fecha", 1)])
        
        # Estadísticas finales
        print(f"\n🎉 MIGRACIÓN COMPLETADA")
        print(f"📊 Colección intervalos: {collection_intervals.count_documents({}):,} documentos")
        print(f"📊 Colección diaria: {collection_daily.count_documents({}):,} documentos")
        
        # Mostrar rango de fechas
        primer_intervalo = collection_intervals.find().sort("timestamp", 1).limit(1)
        ultimo_intervalo = collection_intervals.find().sort("timestamp", -1).limit(1)
        
        for doc in primer_intervalo:
            print(f"📅 Fecha más antigua: {doc['timestamp']}")
        for doc in ultimo_intervalo:
            print(f"📅 Fecha más reciente: {doc['timestamp']}")
        
        # Calcular reducción de espacio
        total_lecturas = sum(doc['num_lecturas'] for doc in aggregated_data)
        reduccion = ((total_lecturas - len(aggregated_data)) / total_lecturas) * 100
        print(f"📉 Reducción de datos: {reduccion:.1f}% ({total_lecturas:,} → {len(aggregated_data):,})")
        
        # Estadísticas de calidad de datos
        total_corrections_in_db = sum(doc['datos_corregidos']['total_corrections'] for doc in aggregated_data)
        correction_percentage = (total_corrections_in_db / total_lecturas) * 100
        print(f"🧹 Calidad de datos: {correction_percentage:.2f}% de lecturas corregidas")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        return False

def create_daily_summaries(aggregated_data):
    """Crear resúmenes diarios (sin cambios, ya funcionaba bien)"""
    daily_data = defaultdict(list)
    
    for doc in aggregated_data:
        date_key = doc['fecha']
        daily_data[date_key].append(doc)
    
    daily_summaries = []
    
    for date_str, day_docs in daily_data.items():
        if not day_docs:
            continue
            
        all_temps = []
        all_hums = []
        total_corrections = 0
        
        for doc in day_docs:
            all_temps.extend([doc['temperatura']['minima'], 
                            doc['temperatura']['maxima']])
            all_hums.extend([doc['humedad']['minima'], 
                           doc['humedad']['maxima']])
            total_corrections += doc['datos_corregidos']['total_corrections']
        
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
                "datos_corregidos": {
                    "total_corrections": total_corrections
                },
                "created_at": datetime.utcnow()
            }
            
            daily_summaries.append(summary)
    
    return daily_summaries

def main():
    """Función principal"""
    CSV_FILE = "C:\\Users\\j4alo\\OneDrive\\Documentos\\Meteohub_data\\datos_meteohub.csv"
    MONGODB_URI = os.getenv("MONGODB_URI")
    
    if not MONGODB_URI:
        print("❌ Error: MONGODB_URI no encontrado en variables de entorno")
        return
    
    if not os.path.exists(CSV_FILE):
        print(f"❌ Error: Archivo {CSV_FILE} no encontrado")
        return
    
    print("🧹 MIGRACIÓN CON LIMPIEZA DE DATOS")
    print("=" * 50)
    print("Esta migración corregirá:")
    print("• Temperaturas imposibles (>50°C, <-20°C)")
    print("• Humedades fuera de rango (>100%, <0%)")
    print("• Usará el último valor válido como reemplazo")
    print("=" * 50)
    
    respuesta = input("¿Continuar con la migración? (s/n): ")
    
    if respuesta.lower() != 's':
        print("🚫 Migración cancelada")
        return
    
    success = migrate_with_cleaning(CSV_FILE, MONGODB_URI, 30)
    
    if success:
        print("\n🎉 ¡Migración completada exitosamente!")
        print("✨ Los datos están ahora limpios y listos para usar")
    else:
        print("\n❌ Error en la migración")

if __name__ == "__main__":
    main()