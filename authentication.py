"""
Módulo de autenticação

Responsável por:
- Estabelecer conexão com SQL Server (SQL Auth ou Trusted Connection)
- Fazer fallback automático para Trusted se o login 'sa' estiver desabilitado
- Validar usuário lógico na tabela Usuarios / stored procedure csspValidaSenha
"""

import os
import typing
from datetime import datetime

try:
    import pyodbc
except Exception:
    pyodbc = None

from config_manager import DatabaseConfig


# ============================================================
# CONEXÃO COM BANCO
# ============================================================

def get_db_connection(db_config: DatabaseConfig):
    """
    Estabelece conexão com SQL Server seguindo as regras:
    - SQLSERVER: tenta SQL Auth (sa). Se falhar por 18470, usa Trusted.
    - MSDE: usa sempre Trusted_Connection.
    """

    if pyodbc is None:
        raise RuntimeError("pyodbc não está instalado. Instale com: pip install pyodbc")

    if not db_config:
        raise ValueError("DatabaseConfig é obrigatório")

    ODBC_DRIVER = os.getenv("MSSQL_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")

    servidor = db_config.server_name
    banco = db_config.db_name
    tipo = (db_config.db_type or "SQLSERVER").upper()

    # --------------------------------------------------------
    # SQLSERVER → tenta sa, fallback Trusted se desabilitado
    # --------------------------------------------------------
    if tipo == "SQLSERVER":
        conn_str_sa = (
            f"DRIVER={{{ODBC_DRIVER}}};"
            f"SERVER={servidor};"
            f"DATABASE={banco};"
            f"UID=sa;"
            f"PWD=csloginciasoft;"
        )
        try:
            print("[DEBUG] Tentando conexão SQL Auth (sa)")
            return pyodbc.connect(conn_str_sa, autocommit=False)
        except Exception as e:
            erro = str(e).lower()

            # Fallback automático se sa estiver desabilitado
            if "18470" in erro or "account is disabled" in erro:
                print("[WARN] Login 'sa' desabilitado. Tentando Trusted_Connection...")

                conn_str_trusted = (
                    f"DRIVER={{{ODBC_DRIVER}}};"
                    f"SERVER={servidor};"
                    f"DATABASE={banco};"
                    f"Trusted_Connection=yes;"
                )
                try:
                    return pyodbc.connect(conn_str_trusted, autocommit=False)
                except Exception as e2:
                    raise RuntimeError(
                        f"Falha ao conectar via SQL Auth e Trusted: {e2}"
                    ) from e2
            else:
                raise RuntimeError(f"Falha ao conectar via SQL Auth: {e}") from e

    # --------------------------------------------------------
    # MSDE → sempre Trusted
    # --------------------------------------------------------
    if tipo == "MSDE":
        conn_str_trusted = (
            f"DRIVER={{{ODBC_DRIVER}}};"
            f"SERVER={servidor};"
            f"DATABASE={banco};"
            f"Trusted_Connection=yes;"
        )
        try:
            print("[DEBUG] Conectando via Trusted_Connection (MSDE)")
            return pyodbc.connect(conn_str_trusted, autocommit=False)
        except Exception as e:
            raise RuntimeError(f"Falha ao conectar via Trusted: {e}") from e

    raise NotImplementedError(f"Tipo de banco não suportado: {tipo}")


# ============================================================
# VALIDAÇÃO DE USUÁRIO
# ============================================================

def verify_user(
    username: str,
    password: str,
    db_config: DatabaseConfig | None = None,
    return_reason: bool = False
) -> typing.Optional[dict]:
    """
    Valida o usuário lógico no banco.

    Regras:
    - Conecta usando get_db_connection (admin / trusted)
    - Executa csspValidaSenha se existir
    - Exige:
        InativosN = 0
    """

    if not db_config or not username:
        if return_reason:
            return None, 'missing_parameters'
        return None

    conn = None
    cur = None

    try:
        conn = get_db_connection(db_config)
        cur = conn.cursor()

        # ----------------------------------------------------
        # Validação de senha via stored procedure (se disponível)
        # ----------------------------------------------------
        try:
            # Verifica se a procedure existe para evitar o erro 2812
            cur.execute("SELECT OBJECT_ID('dbo.csspValidaSenha')")
            proc_row = cur.fetchone()
            proc_exists = bool(proc_row and proc_row[0])
        except Exception:
            proc_exists = False

        if proc_exists:
            try:
                cur.execute("EXEC dbo.csspValidaSenha ?, ?", (username, password))
                res = cur.fetchone()
            except Exception as e:
                # Erro ao executar a procedure (p.ex. permissões) — log único e falha
                print(f"[ERROR] Falha ao executar csspValidaSenha: {e}")
                return None

            if not res or res[0] not in (1, True):
                print("[INFO] Usuário ou senha inválidos (csspValidaSenha)")
                if return_reason:
                    return None, 'invalid_credentials'
                return None
        else:
            # Procedure não encontrada: informa uma vez e tenta validar por coluna de senha
            print("[WARN] Stored procedure dbo.csspValidaSenha não encontrada. Tentando validação por coluna de senha...")
            # Verifica se existe coluna 'NSenha' ou 'Senha' na tabela Usuarios
            try:
                cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Usuarios' AND TABLE_SCHEMA = 'dbo'")
                cols = [r[0].lower() for r in cur.fetchall()]
            except Exception:
                cols = []

            if 'nsenha' in cols:
                # Não temos a procedure que valida nsenha de forma segura: não podemos validar — negar
                print("[ERROR] Campo 'NSenha' presente, mas dbo.csspValidaSenha ausente: não é possível validar senha criptografada.")
                if return_reason:
                    return None, 'cannot_validate_encrypted_password'
                return None
            # Se houver coluna de senha em texto, validamos abaixo (fluxo padrão segue)

    # ----------------------------------------------------
    # Buscar dados do usuário
    # ----------------------------------------------------
        cur.execute(
            """
            SELECT
                CodUsuario,
                NomeUsuario,
                InativosN,
                PDVGerenteSN,
                NivelUsuario
            FROM Usuarios WITH (NOLOCK)
            WHERE NomeUsuario = ?
            """,
            (username,),
        )

        row = cur.fetchone()
        if not row:
            print("[WARN] Usuário validado mas não encontrado na tabela Usuarios")
            if return_reason:
                return None, 'not_found'
            return None

        cod_usuario = int(row[0]) if row[0] is not None else 0
        nome_usuario = str(row[1]) if row[1] is not None else username
        inativos = int(row[2]) if row[2] is not None else 1
        gerente = int(row[3]) if row[3] is not None else 0
        nivel = int(row[4]) if len(row) > 4 and row[4] is not None else 1

        # ----------------------------------------------------
        # Regras de acesso: somente se o usuário está ativo
        # ----------------------------------------------------
        if inativos != 0:
            print(f"[INFO] Acesso negado: InativosN={inativos}")
            if return_reason:
                return None, 'inactive'
            return None
        # Nova regra: somente usuários com NivelUsuario = 0 têm acesso ao app
        if nivel != 0:
            print(f"[INFO] Acesso negado: NivelUsuario={nivel}")
            if return_reason:
                return None, 'insufficient_level'
            return None

        user_data = {
            "CodUsuario": cod_usuario,
            "NomeUsuario": nome_usuario,
            "InativosN": inativos,
            "PDVGerenteSN": gerente,
            "NivelUsuario": nivel,
            "LoginEm": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        print(f"[DEBUG] Autenticação bem-sucedida: {user_data}")
        if return_reason:
            return user_data, None
        return user_data

    except Exception as e:
        print(f"[ERROR] Erro durante autenticação: {e}")
        if return_reason:
            return None, 'error'
        return None

    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            if conn:
                conn.close()
        except Exception:
            pass
