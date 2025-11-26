import azure.functions as func
import logging
import requests
import pymssql
import os
import re
from datetime import datetime
from urllib.parse import unquote

app = func.FunctionApp()

@app.schedule(schedule="0 */10 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False)
def timer_coleta_cripto(myTimer: func.TimerRequest) -> None:
    logging.info('Extração de informações de criptomoedas iniciada')

    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd"

    try:
        response = requests.get(url)
        data = response.json()

        conn_str = os.environ.get("SqlConnectionString")
        if not conn_str:
            raise ValueError("SqlConnectionString não encontrada nas variáveis de ambiente")
        
        # Parse da connection string ODBC para parâmetros do pymssql
        server_match = re.search(r'Server=([^;]+)', conn_str, re.IGNORECASE)
        database_match = re.search(r'Database=([^;]+)', conn_str, re.IGNORECASE)
        user_match = re.search(r'UID=([^;]+)|User ID=([^;]+)', conn_str, re.IGNORECASE)
        password_match = re.search(r'PWD=([^;]+)|Password=([^;]+)', conn_str, re.IGNORECASE)
        
        server = unquote(server_match.group(1)) if server_match else None
        database = unquote(database_match.group(1)) if database_match else None
        user = unquote(user_match.group(1) or user_match.group(2)) if user_match else None
        password = unquote(password_match.group(1) or password_match.group(2)) if password_match else None
        
        if not all([server, database, user, password]):
            raise ValueError("Connection string incompleta. Faltam parâmetros obrigatórios (Server, Database, UID/User ID, PWD/Password)")
        
        conn = pymssql.connect(
            server=server,
            database=database,
            user=user,
            password=password
        )
        cursor = conn.cursor()

        timestamp = datetime.now()

        cursor.execute("INSERT INTO PrecosCripto (nome_ativo, simbolo, preco_usd, data_hora) VALUES (%s, %s, %s, %s)",
                      ("Bitcoin", "BTC", data['bitcoin']['usd'], timestamp))

        cursor.execute("INSERT INTO PrecosCripto (nome_ativo, simbolo, preco_usd, data_hora) VALUES (%s, %s, %s, %s)",
                      ("Ethereum", "ETH", data['ethereum']['usd'], timestamp))

        cursor.execute("INSERT INTO PrecosCripto (nome_ativo, simbolo, preco_usd, data_hora) VALUES (%s, %s, %s, %s)",
                      ("Solana", "SOL", data['solana']['usd'], timestamp))

        conn.commit()
        logging.info('Extração de informações de criptomoedas concluída com sucesso')
    except Exception as e:
        logging.error(f'Erro ao extrair informações de criptomoedas: {str(e)}')
        raise
    finally:
        if 'conn' in locals():
            conn.close()
