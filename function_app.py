import azure.functions as func
import logging
import requests
import pyodbc
import os
from datetime import datetime

app = func.FunctionApp()

@app.schedule(schedule="0 */10 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False)
def timer_coleta_cripto(myTimer: func.TimerRequest) -> None:
    logging.info('Extração de informações de criptomoedas iniciada')

    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd"

    try:
        response = requests.get(url)
        data = response.json()

        conn_str = os.environ.get["SqlConnectionString"]
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        timestamp = datetime.now()

        cursor.execute("INSERT INTO PrecosCripto (nome_ativo, simbolo, preco_usd, data_hora) VALUES (?, ?, ?, ?)",
                      ("Bitcoin", "BTC", data['bitcoin']['usd'], timestamp))

        cursor.execute("INSERT INTO PrecosCripto (nome_ativo, simbolo, preco_usd, data_hora) VALUES (?, ?, ?, ?)",
                      ("Ethereum", "ETH", data['ethereum']['usd'], timestamp))

        cursor.execute("INSERT INTO PrecosCripto (nome_ativo, simbolo, preco_usd, data_hora) VALUES (?, ?, ?, ?)",
                      ("Solana", "SOL", data['solana']['usd'], timestamp))

        conn.commit()
        logging.info('Extração de informações de criptomoedas concluída com sucesso')
    except Exception as e:
        logging.error(f'Erro ao extrair informações de criptomoedas: {str(e)}')
        raise
    finally:
        if 'conn' in locals():
            conn.close()
