"""
Gerenciador de consultas SQL para CSData Studio
Responsável por construir queries, detectar relacionamentos e executar consultas
"""
import pyodbc
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

class JoinType(Enum):
    """Tipos de JOIN suportados"""
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"

@dataclass
class TableInfo:
    """Informações sobre uma tabela"""
    schema: str
    name: str
    type: str  # 'TABLE' ou 'VIEW'
    
    @property
    def full_name(self) -> str:
        return f"[{self.schema}].[{self.name}]"

@dataclass
class ColumnInfo:
    """Informações sobre uma coluna"""
    table_schema: str
    table_name: str
    column_name: str
    data_type: str
    is_nullable: bool
    
    @property
    def full_name(self) -> str:
        return f"[{self.table_schema}].[{self.table_name}].[{self.column_name}]"

@dataclass
class ForeignKey:
    """Informações sobre chave estrangeira"""
    fk_table: str
    fk_column: str
    pk_table: str
    pk_column: str
    constraint_name: str

class QueryBuilder:
    """Construtor de queries SQL"""
    
    def __init__(self, connection: pyodbc.Connection):
        self.conn = connection
        self._relationships: Dict[str, List[ForeignKey]] = {}
    
    def get_tables_and_views(self) -> List[TableInfo]:
        """Retorna todas as tabelas e views do banco"""
        query = """
        SELECT 
            TABLE_SCHEMA,
            TABLE_NAME,
            TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        cursor = self.conn.cursor()
        cursor.execute(query)
        
        tables = []
        for row in cursor.fetchall():
            tables.append(TableInfo(
                schema=row.TABLE_SCHEMA,
                name=row.TABLE_NAME,
                type='TABLE' if row.TABLE_TYPE == 'BASE TABLE' else 'VIEW'
            ))
        
        cursor.close()
        return tables
    
    def get_table_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        """Retorna todas as colunas de uma tabela"""
        query = """
        SELECT 
            TABLE_SCHEMA,
            TABLE_NAME,
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """
        cursor = self.conn.cursor()
        cursor.execute(query, (schema, table))
        
        columns = []
        for row in cursor.fetchall():
            columns.append(ColumnInfo(
                table_schema=row.TABLE_SCHEMA,
                table_name=row.TABLE_NAME,
                column_name=row.COLUMN_NAME,
                data_type=row.DATA_TYPE,
                is_nullable=(row.IS_NULLABLE == 'YES')
            ))
        
        cursor.close()
        return columns
    
    def get_foreign_keys(self, schema: str, table: str) -> List[ForeignKey]:
        """Retorna as chaves estrangeiras de uma tabela"""
        query = """
        SELECT 
            fk.name AS FK_NAME,
            tp.name AS FK_TABLE,
            cp.name AS FK_COLUMN,
            tr.name AS PK_TABLE,
            cr.name AS PK_COLUMN
        FROM sys.foreign_keys fk
        INNER JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
        INNER JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
        INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        INNER JOIN sys.columns cp ON fkc.parent_column_id = cp.column_id 
            AND fkc.parent_object_id = cp.object_id
        INNER JOIN sys.columns cr ON fkc.referenced_column_id = cr.column_id 
            AND fkc.referenced_object_id = cr.object_id
        WHERE SCHEMA_NAME(tp.schema_id) = ? AND tp.name = ?
        """
        cursor = self.conn.cursor()
        cursor.execute(query, (schema, table))
        
        fks = []
        for row in cursor.fetchall():
            fks.append(ForeignKey(
                fk_table=row.FK_TABLE,
                fk_column=row.FK_COLUMN,
                pk_table=row.PK_TABLE,
                pk_column=row.PK_COLUMN,
                constraint_name=row.FK_NAME
            ))
        
        cursor.close()
        return fks

    def get_primary_keys(self, schema: str, table: str) -> List[str]:
        """Retorna lista de colunas que fazem parte da PK da tabela (ordem definida)."""
        query = """
        SELECT k.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        INNER JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE k
            ON tc.CONSTRAINT_NAME = k.CONSTRAINT_NAME
            AND tc.TABLE_SCHEMA = k.TABLE_SCHEMA
        WHERE tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ? AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        ORDER BY k.ORDINAL_POSITION
        """
        cursor = self.conn.cursor()
        cursor.execute(query, (schema, table))
        cols = [r.COLUMN_NAME for r in cursor.fetchall()]
        cursor.close()
        return cols

    def get_table_dependencies(self, schema: str, table: str) -> dict:
        """Retorna dependências da tabela:
        {
            'references': [(fk_schema, fk_table, fk_column, pk_schema, pk_table, pk_column), ...],
            'referenced_by': [(fk_schema, fk_table, fk_column, pk_schema, pk_table, pk_column), ...]
        }
        Onde 'references' são as tabelas que a tabela atual referencia (FKs desta tabela -> outras),
        e 'referenced_by' são tabelas que referenciam a tabela atual.
        """
        query = """
        SELECT 
            SCHEMA_NAME(tp.schema_id) AS FK_SCHEMA,
            tp.name AS FK_TABLE,
            cp.name AS FK_COLUMN,
            SCHEMA_NAME(tr.schema_id) AS PK_SCHEMA,
            tr.name AS PK_TABLE,
            cr.name AS PK_COLUMN
        FROM sys.foreign_keys fk
        INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        INNER JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
        INNER JOIN sys.columns cp ON fkc.parent_column_id = cp.column_id AND fkc.parent_object_id = cp.object_id
        INNER JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
        INNER JOIN sys.columns cr ON fkc.referenced_column_id = cr.column_id AND fkc.referenced_object_id = cr.object_id
        WHERE SCHEMA_NAME(tp.schema_id) = ? AND tp.name = ?
        """
        cursor = self.conn.cursor()
        cursor.execute(query, (schema, table))
        refs = [(r.FK_SCHEMA, r.FK_TABLE, r.FK_COLUMN, r.PK_SCHEMA, r.PK_TABLE, r.PK_COLUMN) for r in cursor.fetchall()]

        # referenced_by: other tables where referenced_table == this table
        query2 = """
        SELECT 
            SCHEMA_NAME(tp.schema_id) AS FK_SCHEMA,
            tp.name AS FK_TABLE,
            cp.name AS FK_COLUMN,
            SCHEMA_NAME(tr.schema_id) AS PK_SCHEMA,
            tr.name AS PK_TABLE,
            cr.name AS PK_COLUMN
        FROM sys.foreign_keys fk
        INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        INNER JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
        INNER JOIN sys.columns cp ON fkc.parent_column_id = cp.column_id AND fkc.parent_object_id = cp.object_id
        INNER JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
        INNER JOIN sys.columns cr ON fkc.referenced_column_id = cr.column_id AND fkc.referenced_object_id = cr.object_id
        WHERE SCHEMA_NAME(tr.schema_id) = ? AND tr.name = ?
        """
        cursor.execute(query2, (schema, table))
        refs_by = [(r.FK_SCHEMA, r.FK_TABLE, r.FK_COLUMN, r.PK_SCHEMA, r.PK_TABLE, r.PK_COLUMN) for r in cursor.fetchall()]
        cursor.close()

        return {'references': refs, 'referenced_by': refs_by}
    
    def find_relationship(self, table1: str, table2: str) -> Optional[ForeignKey]:
        """
        Encontra relacionamento entre duas tabelas.
        Procura em ambas as direções.
        """
        # Carrega relacionamentos se necessário
        if table1 not in self._relationships:
            fks = self.get_foreign_keys('dbo', table1)
            self._relationships[table1] = fks
        
        if table2 not in self._relationships:
            fks = self.get_foreign_keys('dbo', table2)
            self._relationships[table2] = fks
        
        # Procura table1 -> table2
        for fk in self._relationships.get(table1, []):
            if fk.pk_table == table2:
                return fk
        
        # Procura table2 -> table1
        for fk in self._relationships.get(table2, []):
            if fk.pk_table == table1:
                return fk
        
        return None
    
    def build_query(
        self,
        tables: List[Tuple[str, str]],  # [(schema, table), ...]
        columns: List[Tuple[str, str, str]],  # [(schema, table, column), ...]
        joins: Dict[Tuple[str, str], JoinType] = None,  # {(table1, table2): JoinType}
        where_clause: str = None,
        alias_mode: str = 'short'  # 'none' | 'short' | 'descriptive'
    ) -> str:
        """
        Constrói uma query SQL baseada nas tabelas e colunas selecionadas.
        Detecta automaticamente os JOINs se não forem especificados.
        """
        if not tables or not columns:
            raise ValueError("É necessário selecionar ao menos uma tabela e uma coluna")
        
        # Monta SELECT — comportamento depende do alias_mode
        NOLOCK = " WITH (NOLOCK)"

        if alias_mode == 'none':
            # Sem aliases: usa nomes totalmente qualificados
            select_parts = [f"[{s}].[{t}].[{c}]" for (s, t, c) in columns]
            select_clause = "SELECT " + ", ".join(select_parts)
        else:
            # Cria aliases — curto (3 chars) ou descritivo (nome completo limpo)
            aliases: Dict[Tuple[str, str], str] = {}
            used_aliases: Dict[str, int] = {}
            def make_alias_short(table_name: str) -> str:
                base = ''.join([c for c in table_name if c.isalnum()])[:3].lower() or 't'
                if base not in used_aliases:
                    used_aliases[base] = 1
                    return base
                else:
                    used_aliases[base] += 1
                    return f"{base}{used_aliases[base]}"

            def make_alias_desc(table_name: str) -> str:
                # usa o nome da tabela inteiro (limpando caracteres não alfanuméricos)
                base = ''.join([c for c in table_name if c.isalnum()]).lower()[:30] or 't'
                if base not in used_aliases:
                    used_aliases[base] = 1
                    return base
                else:
                    used_aliases[base] += 1
                    return f"{base}{used_aliases[base]}"

            maker = make_alias_short if alias_mode == 'short' else make_alias_desc
            for s, t in tables:
                aliases[(s, t)] = maker(t)

            # Monta SELECT usando aliases
            select_parts = []
            for schema, table, column in columns:
                alias = aliases.get((schema, table), maker(table))
                select_parts.append(f"{alias}.[{column}]")

            select_clause = "SELECT " + ", ".join(select_parts)
        
        # Decide primeira tabela (FROM): prefira a tabela mais referenciada nas colunas
        # Conta ocorrências de cada tabela nas colunas selecionadas
        table_counts = { (schema, table): 0 for (schema, table) in tables }
        for s, t, c in columns:
            key = (s, t)
            if key in table_counts:
                table_counts[key] += 1

        # Escolhe a tabela com maior ocorrência; se empate, mantém a ordem original
        first_schema, first_table = tables[0]
        max_count = -1
        for (s, t), cnt in table_counts.items():
            if cnt > max_count:
                max_count = cnt
                first_schema, first_table = s, t

        # FROM clause
        if alias_mode == 'none':
            from_clause = f"FROM [{first_schema}].[{first_table}]" + NOLOCK
        else:
            first_alias = aliases.get((first_schema, first_table))
            from_clause = f"FROM [{first_schema}].[{first_table}] AS {first_alias}" + NOLOCK
        
        # Monta JOINs
        join_clauses = []
        if len(tables) > 1:
            # Reorder tables: start from the chosen first table, then append the others in the
            # original order (skipping the first one)
            ordered = [(first_schema, first_table)] + [t for t in tables if t != (first_schema, first_table)]
            for i in range(1, len(ordered)):
                schema, table = ordered[i]
                prev_schema, prev_table = ordered[i-1]
                
                # Determina tipo de JOIN
                join_key = (prev_table, table)
                join_type = joins.get(join_key, JoinType.INNER) if joins else JoinType.INNER
                
                # Encontra relacionamento
                fk = self.find_relationship(prev_table, table)
                
                if fk:
                    if alias_mode == 'none':
                        # usa qualificados
                        if fk.fk_table == prev_table:
                            join_clauses.append(
                                f"{join_type.value} [{schema}].[{table}]" + NOLOCK + " "
                                f"ON [{prev_schema}].[{prev_table}].[{fk.fk_column}] = [{schema}].[{table}].[{fk.pk_column}]"
                            )
                        else:
                            join_clauses.append(
                                f"{join_type.value} [{schema}].[{table}]" + NOLOCK + " "
                                f"ON [{schema}].[{table}].[{fk.fk_column}] = [{prev_schema}].[{prev_table}].[{fk.pk_column}]"
                            )
                    else:
                        curr_alias = aliases.get((schema, table))
                        prev_alias = aliases.get((prev_schema, prev_table))
                        if fk.fk_table == prev_table:
                            # prev_table -> table
                            join_clauses.append(
                                f"{join_type.value} [{schema}].[{table}] AS {curr_alias}" + NOLOCK + " "
                                f"ON {prev_alias}.[{fk.fk_column}] = {curr_alias}.[{fk.pk_column}]"
                            )
                        else:
                            # table -> prev_table
                            join_clauses.append(
                                f"{join_type.value} [{schema}].[{table}] AS {curr_alias}" + NOLOCK + " "
                                f"ON {curr_alias}.[{fk.fk_column}] = {prev_alias}.[{fk.pk_column}]"
                            )
                else:
                    # Sem relacionamento encontrado - gera JOIN sem condição (usuário deve corrigir)
                    if alias_mode == 'none':
                        join_clauses.append(
                            f"{join_type.value} [{schema}].[{table}]" + NOLOCK + " "
                            f"ON 1=1 -- AVISO: Relacionamento não encontrado, ajuste manualmente"
                        )
                    else:
                        curr_alias = aliases.get((schema, table))
                        join_clauses.append(
                            f"{join_type.value} [{schema}].[{table}] AS {curr_alias}" + NOLOCK + " "
                            f"ON 1=1 -- AVISO: Relacionamento não encontrado, ajuste manualmente"
                        )
        
        # Ajusta WHERE para usar aliases quando possível
        wc = ""
        if where_clause and where_clause.strip():
            wc = where_clause
            if alias_mode != 'none':
                for (s, t), alias in aliases.items():
                    # substitui formas com colchetes e sem colchetes
                    wc = wc.replace(f"[{s}].[{t}].", f"{alias}.")
                    wc = wc.replace(f"{s}.{t}.", f"{alias}.")

        # Monta WHERE somente se houver filtros reais (não gerar WHERE 1=1 padrão)
        where_part = ""
        if wc and wc.strip():
            where_part = f"WHERE {wc}"
        
        # Query completa
        query = f"{select_clause}\n{from_clause}\n"
        if join_clauses:
            query += "\n".join(join_clauses) + "\n"
        if where_part:
            query += where_part
        
        return query
    
    def execute_query(self, query: str) -> Tuple[List[str], List[Tuple]]:
        """
        Executa uma query e retorna (colunas, dados).
        """
        cursor = self.conn.cursor()
        cursor.execute(query)
        
        # Extrai nomes das colunas
        columns = [column[0] for column in cursor.description]
        
        # Extrai dados
        rows = cursor.fetchall()
        
        cursor.close()
        return columns, rows

__all__ = ['QueryBuilder', 'JoinType', 'TableInfo', 'ColumnInfo', 'ForeignKey']