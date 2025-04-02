## test.py
import requests
import json
 
key = 'd15t0xP0P17bLjSpV7Ecd9snECW0ivtEpWIBpXxf'
url_fabra = 'https://api.meteo.cat/xema/v1/estacions/mesurades/D5/2025/03/20'
url_fabra_prec = 'https://api.meteo.cat/xema/v1/variables/mesurades/35/2025/04/02?codiEstacio=D5'
 
url_meses = 'https://api.meteo.cat/xema/v1/estacions/mesures/D5/35/20250101/20250131'
url_vbles = 'https://api.meteo.cat/xema/v1/representatives/metadades/variables'

url_owm = 'https://api.openweathermap.org/data/2.5/weather?lat=41.3874&lon=2.1686&units=metric&appid=79ee2029b909eee75c80d8ee9371e8e3&lang=es'

url_owm_day = 'https://api.openweathermap.org/data/3.0/onecall/day_summary?lat=41.3874&lon=2.1686&date=2025-03-15&appid=79ee2029b909eee75c80d8ee9371e8e3'

url_owm_cur = 'https://api.openweathermap.org/data/3.0/onecall?lat=41.3874&lon=2.1686&appid=79ee2029b909eee75c80d8ee9371e8e3'

url_owm_resumen = 'https://api.openweathermap.org/data/3.0/onecall/overview?lon=2.1686&lat=41.3874&units=metric&appid=79ee2029b909eee75c80d8ee9371e8e3'

url_consum = 'https://api.meteo.cat/quotes/v1/consum-actual'

# response = requests.get(url_fabra)

url_update_17mar25 = 'https://api.meteo.cat/xema/v1/variables/mesurades/35/2025/03/17?codiEstacio=D5'

response = requests.get(url_fabra_prec, headers={"Content-Type": "application/json", "X-Api-Key": key})
#response = requests.get(url_owm_resumen)

print(response.status_code)  #statusCode
print(response.text) #valors de la resposta


print(json.dumps(response.json(), indent=2))
