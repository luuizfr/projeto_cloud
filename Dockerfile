FROM mcr.microsoft.com/azure-functions/python:4-python3.9

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

RUN apt-get update && apt-get install -y unixodbc-dev

COPY requirements.txt \
RUN pip install -r ./

COPY . /home/site/wwwroot