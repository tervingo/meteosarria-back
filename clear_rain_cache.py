import requests
import os
from dotenv import load_dotenv

def clear_rain_cache():
    # Cargar variables de entorno
    load_dotenv()
    
    # Obtener la URL del backend desde la variable de entorno o usar localhost por defecto
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:5000')
    
    try:
        # Hacer la petición POST para borrar la caché
        response = requests.post(f'{backend_url}/api/barcelona-rain/clear-cache')
        response.raise_for_status()  # Lanzará una excepción si hay error
        
        print("Caché borrada exitosamente")
        print(f"Respuesta: {response.json()}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error al borrar la caché: {e}")

if __name__ == "__main__":
    clear_rain_cache()