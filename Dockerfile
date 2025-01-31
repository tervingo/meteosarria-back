# Usar una imagen que ya tiene Python y Chrome
FROM python:3.9-slim

# Instalar Chrome y sus dependencias
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update \
    && apt-get install -y \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar requirements.txt primero para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copiar el resto de los archivos
COPY . .

# Si existe un archivo .env, copiarlo
COPY .env* ./ 

# Puerto por defecto
EXPOSE 8080

# Comando para ejecutar la aplicación
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]