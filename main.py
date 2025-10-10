# -*- coding: utf-8 -*-"""

from dotenv import load_dotenv
import os
import sys
from signals.analyzer import analyze_signals_from_db_with_symbol

env_local = '.env.local'
if os.path.exists(env_local):
    load_dotenv(env_local, override=True)
else:
    load_dotenv()

server = os.getenv('MSSQL_SERVER')
database = os.getenv('MSSQL_DATABASE')
table = os.getenv('MSSQL_TABLE')
user = os.getenv('MSSQL_USER')
password = os.getenv('MSSQL_PASSWORD')
output_csv = os.getenv('OUTPUT_CSV', '')

default_symbol = '2317'
if len(sys.argv) > 1:
    symbol = sys.argv[1]
    print(f"使用命令列參數 symbol: {symbol}")
else:
    symbol = default_symbol
    print(f"未指定 symbol，使用預設值: {symbol}")

analyze_signals_from_db_with_symbol(
    server, database, table, user, password, output_csv, symbol
)
