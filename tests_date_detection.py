import re


def detect_date_filter(sql_text: str, main_schema: str, main_table: str, date_cols: list, aliases_map: dict) -> bool:
    sql_text = sql_text or ''
    def _ident(name: str) -> str:
        return r'(?:\[' + re.escape(name) + r'\]|' + re.escape(name) + r')'

    for dc in date_cols:
        if not dc:
            continue
        col = (dc or '').strip()
        pats = [r'\b' + re.escape(col) + r'\b']
        try:
            t = main_table
            s = main_schema
            if t:
                pats.append(r'\b' + _ident(t) + r"\s*\.\s*" + _ident(col))
            if s and t:
                pats.append(r'\b' + _ident(s) + r"\s*\.\s*" + _ident(t) + r"\s*\.\s*" + _ident(col))
        except Exception:
            pass
        try:
            alias = aliases_map.get((main_schema, main_table))
            if alias:
                pats.append(r'\b' + re.escape(alias) + r"\s*\.\s*" + _ident(col))
        except Exception:
            pass

        for p in pats:
            try:
                if re.search(p, sql_text, flags=re.IGNORECASE):
                    return True
            except Exception:
                continue
    return False


cases = [
    {
        'name': 'unqualified',
        'sql': "SELECT * FROM dbo.Venda WHERE DataVenda >= '2024-01-01'",
        'schema': 'dbo',
        'table': 'Venda',
        'date_cols': ['DataVenda'],
        'aliases': {}
    },
    {
        'name': 'fully_qualified_bracket',
        'sql': "SELECT * FROM [dbo].[Venda] WHERE [dbo].[Venda].[DataVenda] >= '2024-01-01'",
        'schema': 'dbo',
        'table': 'Venda',
        'date_cols': ['DataVenda'],
        'aliases': {}
    },
    {
        'name': 'table_dot_column',
        'sql': "SELECT * FROM dbo.Venda WHERE Venda.DataVenda >= '2024-01-01'",
        'schema': 'dbo',
        'table': 'Venda',
        'date_cols': ['DataVenda'],
        'aliases': {}
    },
    {
        'name': 'alias_dot_column',
        'sql': "SELECT * FROM dbo.Venda v WHERE v.DataVenda >= '2024-01-01'",
        'schema': 'dbo',
        'table': 'Venda',
        'date_cols': ['DataVenda'],
        'aliases': {('dbo','Venda'): 'v'}
    },
    {
        'name': 'negative_no_date',
        'sql': "SELECT * FROM dbo.Venda",
        'schema': 'dbo',
        'table': 'Venda',
        'date_cols': ['DataVenda'],
        'aliases': {}
    }
]

if __name__ == '__main__':
    print('Running date-filter detection tests')
    for c in cases:
        res = detect_date_filter(c['sql'], c['schema'], c['table'], c['date_cols'], c['aliases'])
        print(f"{c['name']:20s}: detected={res}  | sql={c['sql']}")

    # print summary
    ok = True
    expected = {'unqualified': True, 'fully_qualified_bracket': True, 'table_dot_column': True, 'alias_dot_column': True, 'negative_no_date': False}
    for c in cases:
        if res is None:
            pass
    # Evaluate
    all_good = True
    for c in cases:
        res = detect_date_filter(c['sql'], c['schema'], c['table'], c['date_cols'], c['aliases'])
        exp = expected[c['name']]
        if res != exp:
            all_good = False
            print(f"FAIL: case {c['name']} expected {exp} got {res}")
    if all_good:
        print('\nAll detection cases passed ✔')
    else:
        print('\nSome detection cases failed ✖')
