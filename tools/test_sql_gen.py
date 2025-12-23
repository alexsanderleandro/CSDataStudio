import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from consulta_sql import QueryBuilder
qb = QueryBuilder(conn=None, pasta_metadados='metadados')
aliases={('dbo','CnsVendasRefPeriodo'):'cns',('dbo','Clientes'):'cli',('dbo','Vendedores'):'ven',('dbo','Produtos'):'pro',('dbo','Empresas'):'emp',('dbo','Regioes'):'reg',('dbo','GrupoEstoque'):'gru'}
sql, params = qb.gerar_sql_por_agrupamento('vendas','default', filtros=["DataMovimento = '12-23-2025'"], aliases=aliases)
print(sql)
print('\nPARAMS:', params)
