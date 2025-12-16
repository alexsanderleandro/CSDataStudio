"""Script de debug para testar comportamento das opções A/B de conexão.

Uso:
    python debug_conn_mode.py --mode A|B --server HOST --db DBNAME --type SQLSERVER|MSDE --user USER --pwd PWD

Explicação rápida:
- Mode A: MSSQL_CONN_MODE=A -> conecta apenas usando credenciais administrativas (MSSQL_ADMIN_* ou Trusted se MSDE).
- Mode B: MSSQL_CONN_MODE=B -> tenta conectar com as credenciais fornecidas pelo usuário; se falhar, tenta credenciais administrativas.

O script tenta (1) get_db_connection passando username/password e (2) verify_user para demonstrar o fluxo.
"""
import os
import sys
import argparse
import traceback

from authentication import get_db_connection, verify_user


class SimpleCfg:
    def __init__(self, server_name, db_name, db_type):
        self.server_name = server_name
        self.db_name = db_name
        self.db_type = db_type


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['A','B'], default='A')
    p.add_argument('--server', required=True)
    p.add_argument('--db', required=True)
    p.add_argument('--type', choices=['SQLSERVER','MSDE'], default='SQLSERVER')
    p.add_argument('--user', required=False)
    p.add_argument('--pwd', required=False)
    args = p.parse_args()

    os.environ['MSSQL_CONN_MODE'] = args.mode
    print(f"MSSQL_CONN_MODE={os.environ['MSSQL_CONN_MODE']}")
    cfg = SimpleCfg(args.server, args.db, args.type)

    print('\n--- TENTATIVA get_db_connection (passando username/password) ---')
    try:
        conn = get_db_connection(cfg, args.user, args.pwd)
        print('Conexão bem-sucedida:', conn)
        try:
            conn.close()
        except Exception:
            pass
    except Exception as e:
        print('Falha em get_db_connection:')
        traceback.print_exc()

    print('\n--- TENTATIVA verify_user (validação de módulo/usuario) ---')
    try:
        res = verify_user(args.user or '', args.pwd or '', cfg)
        print('verify_user retornou:', res)
    except Exception:
        print('Falha em verify_user:')
        traceback.print_exc()


if __name__ == '__main__':
    main()
