## test.py
import requests
 
key = 'd15t0xP0P17bLjSpV7Ecd9snECW0ivtEpWIBpXxf'
url = 'https://api.meteo.cat/referencia/v1/municipis'
 
response = requests.get(url, headers={"Content-Type": "application/json", "X-Api-Key": key})
 
print(response.status_code)  #statusCode
print(response.text) #valors de la resposta
