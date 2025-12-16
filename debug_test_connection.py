#!/usr/bin/env python3
"""Script de debug para testar conexões ODBC ao SQL Server usando as
configurações lidas por ConfigManager. Imprime connection strings e traceback
completo para análise.

Usage:
  python debug_test_connection.py [--user USER] [--pwd PWD]

Se --user/--pwd forem fornecidos, uma tentativa adicional será feita com essas
credenciais.
"""
import sys
import traceback
from config_manager import ConfigManager

try:
    import pyodbc
except Exception as e:
    print("pyodbc não disponível:", e)
    sys.exit(2)

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--user', help='Usuário para testar (opcional)')
parser.add_argument('--pwd', help='Senha do usuário para testar (opcional)')
args = parser.parse_args()

cfg = ConfigManager.read_config()
if not cfg:
    print('Nenhuma configuração encontrada.')
    sys.exit(1)

print('Config encontrada:')
print('  TipoBanco:', cfg.db_type)
print('  Servidor :', cfg.server_name)
print('  Banco    :', cfg.db_name)
print('')

# Construir connection strings
driver = 'ODBC Driver 17 for SQL Server'
sa_conn = f"DRIVER={{{driver}}};SERVER={cfg.server_name};DATABASE={cfg.db_name};UID=sa;PWD=csloginciasoft"
trusted_conn = f"DRIVER={{{driver}}};SERVER={cfg.server_name};DATABASE={cfg.db_name};Trusted_Connection=yes"
print('Tentativas que serão executadas:')
print('  1) SA   ->', sa_conn)
print('  2) Trusted ->', trusted_conn)
if args.user and args.pwd:
    user_conn = f"DRIVER={{{driver}}};SERVER={cfg.server_name};DATABASE={cfg.db_name};UID={args.user};PWD={args.pwd}"
    print('  3) Credenciais fornecidas ->', user_conn)
print('')

def try_connect(conn_str, label):
    print(f'--> Tentando {label}...')
    try:
        conn = pyodbc.connect(conn_str, autocommit=True, timeout=5)
        try:
            cur = conn.cursor()
            cur.execute("SELECT DB_NAME()")
            row = cur.fetchone()
            print(f"    SUCESSO ({label}) - DB_NAME() = {row[0] if row else '(none)'}")
            cur.close()
        finally:
            conn.close()
    except Exception as e:
        print(f"    FALHOU ({label}): {e}")
        print('    Traceback:')
        print(''.join(traceback.format_exception(None, e, e.__traceback__)))

# 1) SA
try_connect(sa_conn, 'SA')
# 2) Trusted
try_connect(trusted_conn, 'Trusted')
# 3) Credenciais do módulo (se fornecidas)
if args.user and args.pwd:
    try_connect(user_conn, f'User {args.user}')

print('\nConcluído.')
