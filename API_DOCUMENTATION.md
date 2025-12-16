# 📚 Documentação da API - CSData Studio

Documentação completa das classes e funções do CSData Studio para uso programático.

## 📑 Índice

- [Autenticação](#autenticação)
- [Configuração](#configuração)
- [Construção de Queries](#construção-de-queries)
- [Gerenciamento de Consultas](#gerenciamento-de-consultas)
- [Validação de SQL](#validação-de-sql)
- [Geração de Gráficos](#geração-de-gráficos)
- [Insights com IA](#insights-com-ia)
- [Geração de Relatórios](#geração-de-relatórios)

---

## 🔐 Autenticação

### `authentication.py`

#### `get_db_connection()`
Retorna uma conexão pyodbc usando Windows Authentication.

```python
from authentication import get_db_connection

conn = get_db_connection()
# Use a conexão
conn.close()
```

**Retorna:** `pyodbc.Connection`  
**Exceções:** `pyodbc.Error` se falhar

---

#### `verify_user(username: str, password: str)`
Verifica credenciais contra a tabela Usuarios.

```python
from authentication import verify_user

user_data = verify_user("admin", "senha123")
if user_data:
    print(f"Bem-vindo, {user_data['NomeUsuario']}")
else:
    print("Login falhou")
```

**Parâmetros:**
- `username` (str): Nome do usuário
- `password` (str): Senha do usuário

**Retorna:** `Dict` com dados do usuário ou `None` se falhar

**Estrutura do retorno:**
```python
{
    'CodUsuario': int,
    'NomeUsuario': str,
    'InativosN': int,
    'PDVGerenteSN': int
}
```

**Requisitos:**
- `InativosN = 0`
- `PDVGerenteSN = 1`

---

## ⚙️ Configuração

### `config_manager.py`

#### `ConfigManager.read_config()`
Lê o arquivo CSLogin.xml e retorna configurações do banco.

```python
from config_manager import ConfigManager

config = ConfigManager.read_config()
if config:
    print(f"Servidor: {config.server_name}")
    print(f"Banco: {config.db_name}")
```

**Retorna:** `DatabaseConfig` ou `None`

---

#### `ConfigManager.create_sample_config(path: str = None)`
Cria um arquivo de configuração de exemplo.

```python
from config_manager import ConfigManager

ConfigManager.create_sample_config()
```

**Parâmetros:**
- `path` (str, opcional): Caminho do arquivo. Padrão: `C:\CEOSoftware\CSLogin.xml`

**Retorna:** `bool` - True se criado com sucesso

---

#### Classe `DatabaseConfig`

```python
from config_manager import DatabaseConfig

config = DatabaseConfig(
    db_type="MSSQL",
    db_name="BDCEOSOFTWARE",
    server_name="SERVIDOR"
)

if config.is_valid():
    print("Configuração válida")
```

**Atributos:**
- `db_type` (str): Tipo do banco
- `db_name` (str): Nome do banco
- `server_name` (str): Nome do servidor

**Métodos:**
- `is_valid()` → bool

---

## 🔨 Construção de Queries

### `consulta_sql.py`

#### Classe `QueryBuilder`

```python
from authentication import get_db_connection
from consulta_sql import QueryBuilder, JoinType

conn = get_db_connection()
qb = QueryBuilder(conn)
```

---

#### `get_tables_and_views()`
Retorna todas as tabelas e views do banco.

```python
tables = qb.get_tables_and_views()
for table in tables:
    print(f"{table.schema}.{table.name} ({table.type})")
```

**Retorna:** `List[TableInfo]`

**TableInfo:**
- `schema` (str)
- `name` (str)
- `type` (str): 'TABLE' ou 'VIEW'
- `full_name` (property): Retorna `[schema].[name]`

---

#### `get_table_columns(schema: str, table: str)`
Retorna todas as colunas de uma tabela.

```python
columns = qb.get_table_columns('dbo', 'Produtos')
for col in columns:
    print(f"{col.column_name} ({col.data_type})")
```

**Retorna:** `List[ColumnInfo]`

**ColumnInfo:**
- `table_schema` (str)
- `table_name` (str)
- `column_name` (str)
- `data_type` (str)
- `is_nullable` (bool)
- `full_name` (property)

---

#### `get_foreign_keys(schema: str, table: str)`
Retorna as chaves estrangeiras de uma tabela.

```python
fks = qb.get_foreign_keys('dbo', 'Vendas')
for fk in fks:
    print(f"{fk.fk_table}.{fk.fk_column} → {fk.pk_table}.{fk.pk_column}")
```

**Retorna:** `List[ForeignKey]`

**ForeignKey:**
- `fk_table` (str)
- `fk_column` (str)
- `pk_table` (str)
- `pk_column` (str)
- `constraint_name` (str)

---

#### `build_query(...)`
Constrói uma query SQL baseada nas tabelas e colunas selecionadas.

```python
tables = [('dbo', 'Vendas'), ('dbo', 'Clientes')]
columns = [
    ('dbo', 'Vendas', 'NumeroVenda'),
    ('dbo', 'Clientes', 'NomeCliente')
]
joins = {('Vendas', 'Clientes'): JoinType.INNER}

sql = qb.build_query(tables, columns, joins, "DataVenda >= '2024-01-01'")
print(sql)
```

**Parâmetros:**
- `tables` (List[Tuple[str, str]]): Lista de (schema, table)
- `columns` (List[Tuple[str, str, str]]): Lista de (schema, table, column)
- `joins` (Dict, opcional): Dicionário de JOINs
- `where_clause` (str, opcional): Cláusula WHERE

**Retorna:** `str` - Query SQL gerada

---

#### `execute_query(query: str)`
Executa uma query e retorna dados.

```python
columns, data = qb.execute_query(sql)
print(f"Colunas: {columns}")
print(f"Linhas: {len(data)}")
```

**Retorna:** `Tuple[List[str], List[Tuple]]` - (colunas, dados)

---

### Enumerações

#### `JoinType`
```python
from consulta_sql import JoinType

JoinType.INNER  # "INNER JOIN"
JoinType.LEFT   # "LEFT JOIN"
JoinType.RIGHT  # "RIGHT JOIN"
```

---

## 💾 Gerenciamento de Consultas

### `saved_queries.py`

#### Classe `QueryManager`

```python
from saved_queries import QueryManager

qm = QueryManager()
```

---

#### `add_query(...)`
Adiciona ou atualiza uma consulta salva.

```python
qm.add_query(
    name="Vendas Mensais",
    sql="SELECT * FROM Vendas WHERE MONTH(DataVenda) = MONTH(GETDATE())",
    description="Vendas do mês atual",
    created_by="Admin",
    tags=["vendas", "mensal"],
    overwrite=False
)
```

**Parâmetros:**
- `name` (str): Nome único (obrigatório)
- `sql` (str): Query SQL (obrigatório)
- `description` (str): Descrição
- `created_by` (str): Nome do criador
- `tags` (List[str]): Lista de tags
- `overwrite` (bool): Se True, sobrescreve existente

**Retorna:** `bool`

---

#### `get_query(name: str)`
Retorna uma consulta pelo nome.

```python
query = qm.get_query("Vendas Mensais")
if query:
    print(query.sql)
```

**Retorna:** `SavedQuery` ou `None`

---

#### `list_queries(tag: str = None)`
Lista todas as consultas, opcionalmente por tag.

```python
# Todas
all_queries = qm.list_queries()

# Por tag
vendas_queries = qm.list_queries(tag="vendas")
```

**Retorna:** `List[SavedQuery]`

---

#### `delete_query(name: str)`
Remove uma consulta.

```python
qm.delete_query("Vendas Mensais")
```

**Retorna:** `bool`

---

#### `search_queries(search_term: str)`
Busca consultas por termo.

```python
results = qm.search_queries("cliente")
```

**Retorna:** `List[SavedQuery]`

---

#### `export_query_as_view(name: str, view_name: str = None)`
Exporta consulta como CREATE VIEW.

```python
view_sql = qm.export_query_as_view("Vendas Mensais", "vw_VendasMes")
print(view_sql)
```

**Retorna:** `str` - Script SQL da VIEW

---

## ✅ Validação de SQL

### `valida_sql.py`

#### `validar_sql(query: str)`
Valida uma query SQL para execução.

```python
from valida_sql import validar_sql

sql = "SELECT * FROM Produtos WHERE Ativo = 1"
is_valid, error_msg = validar_sql(sql)

if is_valid:
    print("SQL válida!")
else:
    print(f"Erro: {error_msg}")
```

**Retorna:** `Tuple[bool, str]` - (válido, mensagem)

**Regras:**
- ✅ Permite apenas SELECT e WITH
- ✅ Exige cláusula WHERE
- ❌ Bloqueia INSERT, UPDATE, DELETE
- ❌ Bloqueia EXEC, sp_*, xp_*
- ❌ Bloqueia múltiplas statements (;)
- ✅ Permite UNION ALL
- ❌ Bloqueia UNION simples

---

#### `validar_sql_for_save(query: str)`
Validação mais permissiva para salvamento.

```python
from valida_sql import validar_sql_for_save

sql = "SELECT TOP 100 * FROM Produtos"  # Sem WHERE, mas OK para salvar
is_valid, error_msg = validar_sql_for_save(sql)
```

**Retorna:** `Tuple[bool, str]`

---

## 📊 Geração de Gráficos

### `chart_generator.py`

#### Classe `ChartGenerator`

```python
from chart_generator import ChartGenerator, ChartType, AggregationType

cg = ChartGenerator()
```

---

#### `create_chart(...)`
Cria um gráfico baseado nos dados.

```python
columns = ['Produto', 'Quantidade', 'Valor']
data = [
    ('Notebook', 10, 5000),
    ('Mouse', 50, 150),
    ('Teclado', 30, 300)
]

fig = cg.create_chart(
    data=data,
    columns=columns,
    x_column='Produto',
    y_column='Quantidade',
    aggregation=AggregationType.SUM,
    chart_type=ChartType.COLUMN,
    title='Vendas por Produto',
    color='#3498db'
)
```

**Parâmetros:**
- `data` (List[Tuple]): Dados
- `columns` (List[str]): Nomes das colunas
- `x_column` (str): Coluna para eixo X
- `y_column` (str): Coluna para eixo Y
- `aggregation` (AggregationType): Tipo de agregação
- `chart_type` (ChartType): Tipo de gráfico
- `title` (str): Título
- `x_label` (str, opcional): Rótulo eixo X
- `y_label` (str, opcional): Rótulo eixo Y
- `color` (str): Cor (hex)

**Retorna:** `matplotlib.figure.Figure`

---

#### `save_chart(fig: Figure, output_path: str, dpi: int = 150)`
Salva o gráfico em arquivo.

```python
cg.save_chart(fig, 'grafico.png', dpi=300)
```

**Retorna:** `bool`

---

### Enumerações

#### `ChartType`
```python
ChartType.BAR     # Barras horizontais
ChartType.COLUMN  # Colunas verticais
```

#### `AggregationType`
```python
AggregationType.COUNT  # Contagem
AggregationType.SUM    # Soma
AggregationType.AVG    # Média
AggregationType.MIN    # Mínimo
AggregationType.MAX    # Máximo
```

---

## 🤖 Insights com IA

### `ai_insights.py`

#### Classe `AIInsightsGenerator`

```python
from ai_insights import AIInsightsGenerator

ai = AIInsightsGenerator(api_key="sk-...")
```

---

#### `generate_insights(...)`
Gera insights sobre os dados usando OpenAI.

```python
columns = ['Produto', 'Vendas', 'Receita']
data = [
    ('Produto A', 100, 10000),
    ('Produto B', 200, 15000)
]

insights = ai.generate_insights(
    data=data,
    columns=columns,
    query_description="Análise de vendas por produto",
    max_rows_sample=100
)

print(insights)
```

**Parâmetros:**
- `data` (List[Tuple]): Dados
- `columns` (List[str]): Nomes das colunas
- `query_description` (str, opcional): Contexto
- `max_rows_sample` (int): Máximo de linhas para análise

**Retorna:** `str` - Texto com insights

---

#### `generate_custom_analysis(...)`
Gera análise customizada baseada em pergunta.

```python
insights = ai.generate_custom_analysis(
    data=data,
    columns=columns,
    custom_question="Qual produto tem melhor margem de lucro?"
)
```

**Retorna:** `str`

---

## 📄 Geração de Relatórios

### `report_generator.py`

#### Classe `ReportGenerator`

```python
from report_generator import ReportGenerator

rg = ReportGenerator(
    company_name="CEO Software",
    app_name="CSData Studio",
    app_version="25.01.15 rev.1"
)
```

---

#### `create_report(...)`
Cria um relatório PDF completo.

```python
rg.create_report(
    output_path='relatorio.pdf',
    report_name='Relatório de Vendas',
    user_name='Admin',
    orientation='portrait',
    include_insights=True,
    insights_text=insights_text,
    include_chart=True,
    chart_figure=fig,
    include_table=True,
    columns=columns,
    data=data
)
```

**Parâmetros:**
- `output_path` (str): Caminho do PDF
- `report_name` (str): Nome do relatório (**obrigatório**)
- `user_name` (str): Nome do usuário
- `orientation` (str): 'portrait' ou 'landscape'
- `include_insights` (bool): Incluir insights
- `insights_text` (str): Texto dos insights
- `include_chart` (bool): Incluir gráfico
- `chart_figure` (Figure): Figura matplotlib
- `include_table` (bool): Incluir tabela
- `columns` (List[str]): Colunas da tabela
- `data` (List[Tuple]): Dados da tabela

**Retorna:** `bool`

---

## 📌 Exemplos Completos

### Exemplo 1: Pipeline Completo

```python
from authentication import get_db_connection
from consulta_sql import QueryBuilder
from chart_generator import ChartGenerator, ChartType, AggregationType
from report_generator import ReportGenerator

# 1. Conecta
conn = get_db_connection()
qb = QueryBuilder(conn)

# 2. Executa query
sql = "SELECT Produto, SUM(Quantidade) as Total FROM Vendas WHERE DataVenda >= '2024-01-01' GROUP BY Produto"
columns, data = qb.execute_query(sql)

# 3. Gera gráfico
cg = ChartGenerator()
fig = cg.create_chart(data, columns, 'Produto', 'Total', AggregationType.SUM, ChartType.COLUMN, 'Vendas 2024')

# 4. Gera PDF
rg = ReportGenerator()
rg.create_report(
    'relatorio.pdf',
    'Vendas 2024',
    'Admin',
    include_chart=True,
    chart_figure=fig,
    include_table=True,
    columns=columns,
    data=data
)

conn.close()
```

---

## 🔧 Utilitários

### Versão

```python
from version import Version, APP_NAME, COMPANY_NAME

print(Version.get_version())      # "25.01.15 rev.1"
print(Version.get_full_name())    # "CSData Studio v25.01.15 rev.1"
print(APP_NAME)                   # "CSData Studio"
print(COMPANY_NAME)               # "CEO Software"
```

---

## ⚠️ Tratamento de Erros

Todas as funções podem lançar exceções. Use try-except:

```python
try:
    conn = get_db_connection()
    # ... código ...
except pyodbc.Error as e:
    print(f"Erro de banco: {e}")
except ValueError as e:
    print(f"Erro de validação: {e}")
except Exception as e:
    print(f"Erro: {e}")
finally:
    if conn:
        conn.close()
```

---

**📝 Documentação atualizada em:** 15/01/2025  
**✍️ Versão da API:** 25.01.15 rev.1