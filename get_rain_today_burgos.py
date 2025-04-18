import requests
import time
from datetime import datetime

def get_precipitation_for_burgos():
    # Coordenadas de Burgos, España
    lat = 42.3439
    lon = -3.6969
    
    # Reemplaza con tu API key de OpenWeatherMap
    api_key = "79ee2029b909eee75c80d8ee9371e8e3"
    
    # Timestamp actual
    now = int(time.time())
    
    # Para datos de hoy, usamos el endpoint correcto
    url = f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&exclude=minutely,daily,alerts&appid={api_key}&units=metric"
    
    try:
        response = requests.get(url)
        data = response.json()
        print(data)  # Imprime los datos completos para verificar la estructura
        
        # Procesar los datos para obtener la precipitación total
        total_precipitation = 0
        
        # La hora actual en timestamp UNIX
        current_time = datetime.now()
        start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Recorrer datos por hora
        for hour_data in data.get('hourly', []):
            hour_time = datetime.fromtimestamp(hour_data.get('dt', 0))
            
            # Solo contamos precipitación desde la medianoche hasta ahora
            if start_of_day <= hour_time <= current_time:
                # OpenWeatherMap guarda la precipitación en 'rain.1h' si está disponible
                rain_data = hour_data.get('rain', {})
                precipitation = rain_data.get('1h', 0) if isinstance(rain_data, dict) else 0
                total_precipitation += precipitation
        
        return f"Precipitación total en Burgos hoy (desde 00:00 hasta ahora): {total_precipitation} mm"
        
    except Exception as e:
        return f"Error al obtener datos: {str(e)}"

# Ejecutar la función
print(get_precipitation_for_burgos())