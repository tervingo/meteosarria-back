import requests
from datetime import datetime, timedelta
import time

# Tu API key de OpenWeatherMap
api_key = "79ee2029b909eee75c80d8ee9371e8e3"

# Coordenadas de Barcelona
lat = 41.3874
lon = 2.1686

# Coordenadas de Burgos
burgos_lat = 42.3439
burgos_lon = -3.6970

# Fechas para el cálculo
start_date = datetime(2025, 1, 1)
today = datetime(2025, 3, 14)  # Fecha actual
yesterday = today - timedelta(days=1)

# Función para obtener datos históricos diarios
def get_daily_precipitation(date):
    date_str = date.strftime('%Y-%m-%d')
    url = f'https://api.openweathermap.org/data/3.0/onecall/day_summary?lat={lat}&lon={lon}&date={date_str}&appid={api_key}'
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            # La precipitación puede estar en diferentes unidades, asumimos mm
            precipitation = data.get('precipitation', {}).get('total', 0)
            return precipitation
        else:
            print(f"Error en la solicitud para {date_str}: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return 0
    
    except Exception as e:
        print(f"Error al procesar {date_str}: {e}")
        return 0

# Función para obtener datos actuales
def get_current_precipitation():
    url = f'https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=hourly,daily&appid={api_key}'
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            # En datos actuales, la precipitación puede estar en current.rain
            # Si no ha llovido hoy, puede que no exista este campo
            current_data = data.get('current', {})
            precipitation = current_data.get('rain', {}).get('1h', 0)
            return precipitation
        else:
            print(f"Error al obtener datos actuales: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return 0
    
    except Exception as e:
        print(f"Error al procesar datos actuales: {e}")
        return 0

def get_burgos_data(date_str):
    unix_time = int(datetime.strptime(date_str, '%Y-%m-%d').timestamp())

#    url = f'https://api.openweathermap.org/data/3.0/onecall/day_summary?lat={burgos_lat}&lon={burgos_lon}&date={date_str}&units=metric&appid={api_key}'
    url = f'https://api.openweathermap.org/data/2.5/weather?lat={burgos_lat}&lon={burgos_lon}&units=metric&appid={api_key}'
#    url = f'https://api.openweathermap.org/data/3.0/onecall/timemachine?lat={burgos_lat}&lon={burgos_lon}&dt={unix_time}&appid={api_key}'
#    url = f'https://api.openweathermap.org/data/3.0/onecall/day_summary?lat={burgos_lat}&lon={burgos_lon}&date={date_str}&units=metric&appid={api_key}'    
#    url = f'https://api.openweathermap.org/data/3.0/onecall?lat={burgos_lat}&lon={burgos_lon}&appid={api_key}'
    hourly_url = f"https://api.openweathermap.org/data/2.5/onecall?lat={burgos_lat}&lon={burgos_lon}&exclude=minutely,daily,alerts&units=metric&appid={api_key}"
    response = requests.get(url)
    return response.json()

# Calcular precipitación acumulada histórica
total_precipitation = 0
current_date = start_date

""" print("Obteniendo datos de precipitación históricos...")
while current_date <= yesterday:
    daily_precipitation = get_daily_precipitation(current_date)
    print(f"Fecha: {current_date.strftime('%Y-%m-%d')}, Precipitación: {daily_precipitation:.2f} mm")
    
    total_precipitation += daily_precipitation
    
    # Avanzar al siguiente día
    current_date += timedelta(days=1)
    
    # Pequeña pausa para no exceder límites de la API
    time.sleep(0.01)

# Obtener datos de precipitación de hoy
print("\nObteniendo datos de precipitación de hoy...")
today_precipitation = get_current_precipitation()
print(f"Precipitación de hoy ({today.strftime('%Y-%m-%d')}): {today_precipitation:.2f} mm")

# Sumar la precipitación de hoy al total
total_precipitation += today_precipitation

print(f"\nPrecipitación total acumulada en Barcelona desde el 1 de enero hasta el {today.strftime('%Y-%m-%d')} de 2025: {total_precipitation:.2f} mm")
"""

# Obtener datos de Burgos
burgos_data = get_burgos_data('2025-04-18')
print(f"{burgos_data}")

