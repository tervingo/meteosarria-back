## test.py
import requests
 
key = 'd15t0xP0P17bLjSpV7Ecd9snECW0ivtEpWIBpXxf'
url_fabra = 'https://api.meteo.cat/xema/v1/estacions/mesurades/X4/2025/03/02'

 
response = requests.get(url_fabra, headers={"Content-Type": "application/json", "X-Api-Key": key})
 
print(response.status_code)  #statusCode
print(response.text) #valors de la resposta
