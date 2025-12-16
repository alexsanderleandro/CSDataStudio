#!/usr/bin/env python3
"""Executa dbo.csspValidaSenha e consulta dbo.Usuarios para um usuário fornecido.
Usage: python debug_check_user_proc.py --user ceosoftware --pwd 1
"""
import argparse, traceback, sys
from config_manager import ConfigManager
try:
    import pyodbc
except Exception as e:
    print('pyodbc não disponível:', e); sys.exit(2)

parser = argparse.ArgumentParser()
parser.add_argument('--user', required=True)
parser.add_argument('--pwd', required=True)
args = parser.parse_args()

cfg = ConfigManager.read_config()
if not cfg:
    print('Nenhuma configuração encontrada.'); sys.exit(1)

driver = 'ODBC Driver 17 for SQL Server'
sa_conn = f"DRIVER={{{driver}}};SERVER={cfg.server_name};DATABASE={cfg.db_name};UID=sa;PWD=csloginciasoft"
print('Conectando com SA...')
try:
    conn = pyodbc.connect(sa_conn, autocommit=True)
    cur = conn.cursor()
    try:
        print('Chamando dbo.csspValidaSenha', args.user, args.pwd)
    except Exception:
        pass
    try:
        cur.execute('EXEC dbo.csspValidaSenha ?, ?', (args.user, args.pwd))
        r = cur.fetchone()
        print('Resultado do csspValidaSenha:', r)
    except Exception as e:
        print('Erro ao executar csspValidaSenha:', e)
        print('Traceback:')
        print(''.join(traceback.format_exception(None, e, e.__traceback__)))

    try:
        # Consulta usuario na tabela
        print('\nConsulta dbo.Usuarios for user:')
        cur.execute("SELECT * FROM dbo.Usuarios WHERE NomeUsuario = ?", (args.user,))
        row = cur.fetchone()
        if not row:
            print('Usuario não encontrado na tabela dbo.Usuarios (filtro NomeUsuario).')
            # tentar por outras colunas comuns
            cur.execute("SELECT * FROM dbo.Usuarios WHERE Login = ?", (args.user,))
            row2 = cur.fetchone()
            if row2:
                print('Encontrado por Login:', row2)
            else:
                print('Não encontrado por Login.')
        else:
            print('Registro encontrado:', row)
    except Exception as e:
        print('Erro ao consultar dbo.Usuarios:', e)
        print('Traceback:')
        print(''.join(traceback.format_exception(None, e, e.__traceback__)))

    cur.close()
    conn.close()
except Exception as e:
    print('Falha ao conectar com SA:', e)
    print('Traceback:')
    print(''.join(traceback.format_exception(None, e, e.__traceback__)))
    sys.exit(2)
