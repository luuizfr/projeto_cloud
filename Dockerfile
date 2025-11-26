FROM mcr.microsoft.com/azure-functions/python:4-python3.10

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

# Instala drivers para SQL Server (Correto)
RUN apt-get update && apt-get install -y unixodbc-dev

# CORREÇÃO 1: Copia o arquivo para a raiz do container
COPY requirements.txt /

# CORREÇÃO 2: Aponta para o arquivo que acabamos de copiar
RUN pip install -r /requirements.txt

COPY . /home/site/wwwroot