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
        port_match = re.search(r'Port=([^;]+)', conn_str, re.IGNORECASE)
        
        server = unquote(server_match.group(1)) if server_match else None
        database = unquote(database_match.group(1)) if database_match else None
        user = unquote(user_match.group(1) or user_match.group(2)) if user_match else None
        password = unquote(password_match.group(1) or password_match.group(2)) if password_match else None
        port = int(port_match.group(1)) if port_match else None
        
        # Remove protocolo tcp:// se presente
        if server and server.startswith('tcp:'):
            server = server.replace('tcp:', '')
        if server and server.startswith('//'):
            server = server.replace('//', '')
        
        # Se a porta está no servidor (formato server,port), separa
        if server and ',' in server:
            server, port_str = server.split(',', 1)
            try:
                port = int(port_str)
            except ValueError:
                pass
        
        if not all([server, database, user, password]):
            raise ValueError("Connection string incompleta. Faltam parâmetros obrigatórios (Server, Database, UID/User ID, PWD/Password)")
        
        logging.info(f'Conectando ao servidor: {server}, database: {database}, porta: {port or "padrão (1433)"}')
        
        # Configura parâmetros de conexão
        connect_params = {
            'server': server,
            'database': database,
            'user': user,
            'password': password,
            'timeout': 30
        }
        
        if port:
            connect_params['port'] = port
        
        conn = pymssql.connect(**connect_params)
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
    except pymssql.Error as e:
        error_msg = f'Erro de conexão com SQL Server: {str(e)}'
        logging.error(error_msg)
        logging.error('Verifique: 1) Firewall do Azure SQL permite conexões do Azure Functions, 2) Connection string está correta, 3) Servidor está acessível')
        raise
    except Exception as e:
        logging.error(f'Erro ao extrair informações de criptomoedas: {str(e)}')
        raise
    finally:
        if 'conn' in locals():
            conn.close()
