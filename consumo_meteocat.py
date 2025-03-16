import requests
 
key = 'd15t0xP0P17bLjSpV7Ecd9snECW0ivtEpWIBpXxf'

url = 'https://api.meteo.cat/quotes/v1/consum-actual'

response = requests.get(url, headers={"Content-Type": "application/json", "X-Api-Key": key})

print(response.status_code)  #statusCode
print(response.text) #valors de la resposta

