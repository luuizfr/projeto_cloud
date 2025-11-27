import azure.functions as func
import logging
import requests
import pymssql
import os
import re
import time
from datetime import datetime
from urllib.parse import unquote

app = func.FunctionApp()

def connect_with_retry(connect_params, max_retries=3, retry_delay=5):
    """Tenta conectar ao SQL Server com retry para erros transitórios"""
    for attempt in range(max_retries):
        try:
            logging.info(f'Tentativa de conexão {attempt + 1}/{max_retries}')
            conn = pymssql.connect(**connect_params)
            logging.info('Conexão estabelecida com sucesso')
            return conn
        except pymssql.Error as e:
            error_code = e.args[0] if e.args else None
            
            # Erro 40613: Database is not currently available (pode estar pausado ou escalando)
            # Erro 20009: Unable to connect (erro de conexão transitório)
            if error_code in (40613, 20009) and attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)  # Backoff exponencial
                logging.warning(f'Erro transitório {error_code}. Aguardando {wait_time}s antes de tentar novamente...')
                time.sleep(wait_time)
                continue
            else:
                raise
    raise Exception(f'Falha ao conectar após {max_retries} tentativas')

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
        
        # Conecta com retry para erros transitórios
        conn = connect_with_retry(connect_params, max_retries=3, retry_delay=5)
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
        error_code = e.args[0] if e.args else None
        error_msg = f'Erro de conexão com SQL Server: {str(e)}'
        logging.error(error_msg)
        
        if error_code == 40613:
            logging.error('Erro 40613: O banco de dados pode estar pausado ou temporariamente indisponível.')
            logging.error('Soluções: 1) Verifique no portal do Azure se o banco está pausado e retome-o, 2) Aguarde alguns segundos e tente novamente (o banco pode estar sendo retomado automaticamente)')
        elif error_code == 20009:
            logging.error('Erro 20009: Não foi possível conectar ao servidor.')
            logging.error('Verifique: 1) Firewall do Azure SQL permite conexões do Azure Services, 2) Connection string está correta, 3) Servidor está acessível')
        else:
            logging.error('Verifique: 1) Firewall do Azure SQL permite conexões do Azure Functions, 2) Connection string está correta, 3) Servidor está acessível')
        raise
    except Exception as e:
        logging.error(f'Erro ao extrair informações de criptomoedas: {str(e)}')
        raise
    finally:
        if 'conn' in locals():
            conn.close()
