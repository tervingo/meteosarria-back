#!/usr/bin/env bash
set -o errexit

# Actualizar sistema e instalar dependencias necesarias
apt-get update
apt-get install -y wget unzip

# Instalar Google Chrome
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list'
apt-get update
apt-get install -y google-chrome-stable

# Verificar la instalación de Chrome e imprimir la versión
echo "Chrome version:"
google-chrome --version

# Instalar las dependencias de Python
pip install -r requirements.txt