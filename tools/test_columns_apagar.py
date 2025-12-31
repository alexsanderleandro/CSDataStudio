from config_manager import ConfigManager
from authentication import get_db_connection
from consulta_sql import QueryBuilder

cfg = ConfigManager.read_config()
if not cfg:
    print('ConfigManager.read_config() returned None or no config')
else:
    print('Using DB config:', cfg.server_name, cfg.db_name)
    conn = get_db_connection(cfg)
    qb = QueryBuilder(conn)
    cols = qb.get_table_columns('dbo', 'aPagar')
    if not cols:
        print('No columns returned for dbo.aPagar')
    else:
        for c in cols:
            print(f"{c.column_name} -> data_type={c.data_type} nullable={c.is_nullable}")
    conn.close()
