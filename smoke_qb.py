from consulta_sql import QueryBuilder

# instantiate with no DB connection (we only use metadata reading and SQL generation)
qb = QueryBuilder(None, pasta_metadados='metadados')
mod='vendas'
agr_id='default'
try:
    sql, params = qb.gerar_sql_por_agrupamento(mod, agr_id)
    print('SQL gerado:\n')
    print(sql)
    print('\nparams:', params)
except Exception as e:
    print('Erro ao gerar SQL:', e)
