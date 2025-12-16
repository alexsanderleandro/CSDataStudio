#!/usr/bin/env python3
"""Inspeciona a tabela dbo.Usuarios: colunas e primeiros registros (usando SA)."""
from config_manager import ConfigManager
import traceback, sys
try:
    import pyodbc
except Exception as e:
    print('pyodbc não disponível:', e); sys.exit(2)

cfg = ConfigManager.read_config()
if not cfg:
    print('Nenhuma config'); sys.exit(1)

driver = 'ODBC Driver 17 for SQL Server'
sa_conn = f"DRIVER={{{driver}}};SERVER={cfg.server_name};DATABASE={cfg.db_name};UID=sa;PWD=csloginciasoft"
print('Conectando com SA...')
try:
    conn = pyodbc.connect(sa_conn, autocommit=True)
    cur = conn.cursor()
    try:
        # Colunas
        print('Colunas de dbo.Usuarios:')
        cur.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='Usuarios'")
        cols = cur.fetchall()
        if not cols:
            print('  (nenhuma coluna retornada)')
        else:
            for c in cols:
                print(' ', c[0], '(', c[1], ')')
        # Top 5 rows
        print('\nTop 5 rows (SELECT TOP 5 * FROM dbo.Usuarios):')
        try:
            cur.execute('SELECT TOP 5 * FROM dbo.Usuarios')
            rows = cur.fetchall()
            for r in rows:
                print(' ', r)
        except Exception as e:
            print('  Falha ao selecionar rows:', e)
            print('  Traceback:')
            print(''.join(traceback.format_exception(None, e, e.__traceback__)))
    finally:
        cur.close()
        conn.close()
except Exception as e:
    print('Falha ao conectar com SA:', e)
    print('Traceback:')
    print(''.join(traceback.format_exception(None, e, e.__traceback__)))
    sys.exit(2)
