"""
Gerenciador de consultas SQL para CSData Studio
Construção dinâmica de SQL a partir de metadados JSON
"""

import json
import pyodbc
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass


@dataclass
class TableInfo:
    schema: str
    name: str
    type: str

    @property
    def full_name(self) -> str:
        return f"[{self.schema}].{self.name}"


@dataclass
class ColumnInfo:
    table_schema: str
    table_name: str
    column_name: str
    data_type: str
    is_nullable: bool

    @property
    def full_name(self) -> str:
        return f"{self.table_name}.{self.column_name}"


@dataclass
class ForeignKey:
    constraint_name: str
    fk_schema: str
    fk_table: str
    fk_column: str
    pk_schema: str
    pk_table: str
    pk_column: str


class JoinType(Enum):
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"


class QueryBuilder:
    def __init__(self, conn: pyodbc.Connection, pasta_metadados: str = "metadados"):
        self.conn = conn
        self.pasta_metadados = Path(pasta_metadados)

    # ==========================================================
    # Leitura de Metadados
    # ==========================================================
    def _carregar_json(self, nome: str) -> Dict:
        caminho = self.pasta_metadados / nome
        if not caminho.exists():
            raise FileNotFoundError(f"Arquivo de metadados não encontrado: {nome}")
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)

    def carregar_modulo(self, modulo: str) -> Dict:
        return self._carregar_json(f"{modulo}.json")

    def carregar_agrupamentos(self, modulo: str) -> Dict:
        return self._carregar_json(f"{modulo}_agrupamentos.json")

    # ==========================================================
    # Geração de SQL
    # ==========================================================
    def gerar_sql_por_agrupamento(
        self,
        modulo: str,
        agrupamento_id: str,
        filtros: Optional[List] = None,
        aliases: Optional[Dict[tuple, str]] = None
    ) -> tuple:

        modulo_meta = self.carregar_modulo(modulo)
        agrup_meta = self.carregar_agrupamentos(modulo)

        agrupamento = next(
            (a for a in agrup_meta["agrupamentos"] if a["id"] == agrupamento_id),
            None
        )
        if not agrupamento:
            raise ValueError(f"Agrupamento '{agrupamento_id}' não encontrado.")

        tabela_principal = agrupamento["tabela"]
        select_parts = []
        group_by_parts = []
        join_parts = []
        where_params = []

        # helper: normalize table identifier and optionally add alias
        def parse_table_ident(t: str):
            # aceita formas: [schema].Table, schema.table, table
            parts = re.split(r"\.|\[|\]", t)
            parts = [p for p in parts if p]
            if len(parts) == 1:
                return ('dbo', parts[0])
            elif len(parts) == 2:
                return (parts[0], parts[1])
            else:
                return (parts[-2], parts[-1])

        def apply_alias_to_table(t: str):
            schema, tbl = parse_table_ident(t)
            # always return a normalized qualified name; add alias if present
            qualified = f"[{schema}].[{tbl}]"
            if aliases and (schema, tbl) in aliases:
                return f"{qualified} {aliases[(schema, tbl)]}"
            return qualified

        # helper: qualify a field name using available aliases
        def qualify_field(field: str):
            """Se o campo for simples (ex: 'CodVendedor'), prefixa com o alias da tabela principal
            quando disponível. Se já estiver qualificado (schema.table.col ou table.col), tenta
            substituir o table pelo alias correspondente quando houver um mapeamento em aliases.
            """
            if not field:
                return field
            s = str(field).strip()
            # se já tem ponto (qualificado), tentaremos substituir por alias quando possível
            if '.' in s:
                # captura a porção final (coluna) e a porção da esquerda (possível esquema/tabela)
                # exemplos de formatos: [dbo].[Tabela].Col, dbo.Tabela.Col, Tabela.Col
                m = re.match(r"^\[?(?P<left>[^\]]+?)\]?\.?\[?(?P<table>[^\]]+?)\]?\.(?P<col>\w+)$", s)
                if m:
                    left = m.group('left')
                    table = m.group('table')
                    col = m.group('col')
                    # tente achar alias primeiro por (schema,table)
                    try_keys = []
                    # left pode ser schema or schema.table depending on match; prefer (left,table)
                    try_keys.append((left, table))
                    try_keys.append((None, table))
                    for k in try_keys:
                        if aliases and k in aliases:
                            return f"{aliases[k]}.{col}"
                # se não conseguimos mapear, return original string limpa
                return s
            else:
                # campo sem qualificação: prefixar com alias da tabela principal quando houver
                try:
                    p_schema, p_table = parse_table_ident(tabela_principal)
                    if aliases and (p_schema, p_table) in aliases:
                        return f"{aliases[(p_schema, p_table)]}.{s}"
                except Exception:
                    pass
                return s

        # Dimensões
        for dim in agrupamento.get("dimensoes", []):
            if isinstance(dim, dict) and dim.get("tipo") == "mes_ano":
                campo = dim["campo"]
                qcampo = qualify_field(campo)
                expr = f"FORMAT({qcampo}, 'yyyy-MM')"
                select_parts.append(f"{expr} AS MesAno")
                group_by_parts.append(expr)
            else:
                # dim pode ser string simples ou já qualificado
                q = qualify_field(dim) if isinstance(dim, str) else dim
                select_parts.append(q)
                group_by_parts.append(q)

        # Métricas
        for met in agrupamento.get("metricas", []):
            campo = met["campo"]
            func = met["funcao"]
            label = met["label"]
            qcampo = qualify_field(campo)
            select_parts.append(f"{func}({qcampo}) AS [{label}]")

        # JOINs
        for join in agrupamento.get("joins", []):
            join_parts.append(
                f"INNER JOIN {join['tabela']} ON {join['on']}"
            )

        # SQL base
        sql = f"""
        SELECT
            {", ".join(select_parts)}
        FROM {apply_alias_to_table(tabela_principal)}
        """

        if join_parts:
            # if aliases provided, attempt to rewrite join table names and ON expressions
            rewritten_joins = []
            # helper: reescreve a expressão ON substituindo referências table.col ou schema.table.col por alias.col
            def rewrite_on_expr(on_expr: str) -> str:
                if not aliases:
                    return on_expr
                # encontra tokens do tipo [schema].[table].col ou schema.table.col ou table.col ou [table].col
                token_re = re.compile(r"(?P<tok>(?:\[[^\]]+\]|[A-Za-z0-9_]+)(?:\.(?:\[[^\]]+\]|[A-Za-z0-9_]+)){1,2})")
                out = []
                last = 0
                for m in token_re.finditer(on_expr):
                    start, end = m.span('tok')
                    out.append(on_expr[last:start])
                    tok = m.group('tok')
                    # split parts and strip brackets
                    parts = [p.strip('[]') for p in tok.split('.')]
                    alias_repl = None
                    if len(parts) == 3:
                        schema, table, col = parts
                        # try exact (schema,table)
                        if (schema, table) in aliases:
                            alias_repl = f"{aliases[(schema, table)]}.{col}"
                        else:
                            # try match by table name only
                            for (s2, t2), a2 in aliases.items():
                                if t2.lower() == table.lower():
                                    alias_repl = f"{a2}.{col}"
                                    break
                    elif len(parts) == 2:
                        table, col = parts
                        # try match by table name
                        for (s2, t2), a2 in aliases.items():
                            if t2.lower() == table.lower():
                                alias_repl = f"{a2}.{col}"
                                break
                    # if found replacement, use it, else keep original token (but normalized without extra brackets)
                    if alias_repl:
                        out.append(alias_repl)
                    else:
                        out.append(tok)
                    last = end
                out.append(on_expr[last:])
                return ''.join(out)

            for j in join_parts:
                # expected original format: 'INNER JOIN {join_table} ON {on_expr}'
                m = re.match(r"(\w+\s+JOIN)\s+(.+)\s+ON\s+(.+)", j, re.IGNORECASE)
                if m:
                    join_kw = m.group(1)
                    join_table = m.group(2).strip()
                    on_expr = m.group(3).strip()
                    jt_schema, jt_table = parse_table_ident(join_table)
                    if aliases and (jt_schema, jt_table) in aliases:
                        alias = aliases[(jt_schema, jt_table)]
                        join_table_repr = f"[{jt_schema}].[{jt_table}] {alias}"
                        on_expr = rewrite_on_expr(on_expr)
                        rewritten_joins.append(f"{join_kw} {join_table_repr} ON {on_expr}")
                    else:
                        rewritten_joins.append(j)
                else:
                    rewritten_joins.append(j)
            sql += "\n" + "\n".join(rewritten_joins)

        if filtros:
            # filtros pode ser lista de strings (compatibilidade) ou lista de tuples (expr, params)
            exprs = []
            for f in filtros:
                if isinstance(f, (list, tuple)) and len(f) >= 1:
                    exprs.append(f[0])
                    if len(f) > 1 and f[1]:
                        if isinstance(f[1], (list, tuple)):
                            where_params.extend(list(f[1]))
                        else:
                            where_params.append(f[1])
                else:
                    exprs.append(str(f))
            sql += "\nWHERE " + " AND ".join(exprs)

        if group_by_parts:
            sql += "\nGROUP BY " + ", ".join(group_by_parts)

        return sql.strip(), where_params

    # ==========================================================
    # Execução
    # ==========================================================
    def executar_sql(self, sql: str, params: Optional[List] = None) -> Tuple[List[str], List[tuple]]:
        cursor = self.conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        colunas = [c[0] for c in cursor.description] if cursor.description else []
        dados = cursor.fetchall()

        cursor.close()
        return colunas, dados

    def execute_query(self, sql: str, params: Optional[List] = None) -> Tuple[List[str], List[tuple]]:
        """Wrapper compatível com chamadas existentes (inglês) que aceita parâmetros."""
        return self.executar_sql(sql, params)

    # ==========================================================
    # Métodos de utilitários/metadata (compatibilidade com Main)
    # ==========================================================
    def get_tables_and_views(self) -> List[TableInfo]:
        """Retorna uma lista de TableInfo com tabelas e views do banco."""
        sql = """
        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        cur = self.conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
        result = []
        for r in rows:
            schema, name, ttype = r[0], r[1], r[2]
            # normalize type to 'TABLE' or 'VIEW'
            t = 'VIEW' if 'VIEW' in (ttype or '').upper() else 'TABLE'
            result.append(TableInfo(schema=schema, name=name, type=t))
        return result

    def get_table_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        """Retorna ColumnInfo para a tabela informada."""
        sql = """
        SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """
        cur = self.conn.cursor()
        cur.execute(sql, (schema, table))
        rows = cur.fetchall()
        cur.close()
        cols = []
        for r in rows:
            is_nullable = True if (r[4] or '').upper() == 'YES' else False
            cols.append(ColumnInfo(table_schema=r[0], table_name=r[1], column_name=r[2], data_type=r[3], is_nullable=is_nullable))
        return cols

    def get_foreign_keys(self, schema: str, table: str) -> List[ForeignKey]:
        """Retorna lista de ForeignKey envolvendo a tabela (como fk ou pk).

        Usa INFORMATION_SCHEMA para ser mais portátil.
        """
        sql = """
        SELECT
            kcu.CONSTRAINT_NAME,
            kcu.TABLE_SCHEMA AS FK_SCHEMA,
            kcu.TABLE_NAME AS FK_TABLE,
            kcu.COLUMN_NAME AS FK_COLUMN,
            ccu.TABLE_SCHEMA AS PK_SCHEMA,
            ccu.TABLE_NAME AS PK_TABLE,
            ccu.COLUMN_NAME AS PK_COLUMN
        FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
        JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
        WHERE kcu.TABLE_SCHEMA = ? AND kcu.TABLE_NAME = ?
        """
        cur = self.conn.cursor()
        cur.execute(sql, (schema, table))
        rows = cur.fetchall()
        fks = []
        for r in rows:
            # (constraint, fk_schema, fk_table, fk_col, pk_schema, pk_table, pk_col)
            fks.append(ForeignKey(constraint_name=r[0], fk_schema=r[1], fk_table=r[2], fk_column=r[3], pk_schema=r[4], pk_table=r[5], pk_column=r[6]))
        cur.close()
        return fks

    def get_table_dependencies(self, schema: str, table: str) -> Dict[str, List[Tuple]]:
        """Retorna um dicionário com chaves 'references' (esta tabela -> outra)
        e 'referenced_by' (outras -> esta), cada qual é uma lista de tuplas
        com informações compatíveis com o consumo em `main.py`.
        """
        # referências onde esta tabela possui FK para outra (esta -> outra)
        refs = []
        for fk in self.get_foreign_keys(schema, table):
            refs.append((fk.constraint_name, fk.fk_schema, fk.fk_table, fk.fk_column, fk.pk_schema, fk.pk_table, fk.pk_column))

        # referências onde outras tabelas possuem FK apontando para esta (outras -> esta)
        sql = """
        SELECT
            kcu.CONSTRAINT_NAME,
            kcu.TABLE_SCHEMA AS FK_SCHEMA,
            kcu.TABLE_NAME AS FK_TABLE,
            kcu.COLUMN_NAME AS FK_COLUMN,
            ccu.TABLE_SCHEMA AS PK_SCHEMA,
            ccu.TABLE_NAME AS PK_TABLE,
            ccu.COLUMN_NAME AS PK_COLUMN
        FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
        JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
        WHERE ccu.TABLE_SCHEMA = ? AND ccu.TABLE_NAME = ?
        """
        cur = self.conn.cursor()
        cur.execute(sql, (schema, table))
        rows = cur.fetchall()
        referenced_by = []
        for r in rows:
            referenced_by.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6]))
        cur.close()

        return {'references': refs, 'referenced_by': referenced_by}

    def get_primary_keys(self, schema: str, table: str) -> List[str]:
        """Retorna lista de nomes de colunas que compõem a PK da tabela."""
        sql = """
        SELECT kcu.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
        WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' AND kcu.TABLE_SCHEMA = ? AND kcu.TABLE_NAME = ?
        ORDER BY kcu.ORDINAL_POSITION
        """
        cur = self.conn.cursor()
        cur.execute(sql, (schema, table))
        rows = cur.fetchall()
        cur.close()
        return [r[0] for r in rows]
