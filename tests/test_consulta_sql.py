import unittest

from consulta_sql import QueryBuilder, ForeignKey


class DummyQB(QueryBuilder):
    """QueryBuilder de teste que não consulta o banco por relacionamentos.
    find_relationship sempre retorna None para forçar a geração de JOINs com ON 1=1
    e permitir verificar a ordem dos JOINs gerados.
    """
    def __init__(self):
        # não precisa de conexão real para estes testes
        super().__init__(connection=None)

    def find_relationship(self, table1: str, table2: str):
        return None


class TestQueryBuilderJoinOrder(unittest.TestCase):

    def test_join_order_preserved_no_alias(self):
        qb = DummyQB()
        tables = [('dbo', 'A'), ('dbo', 'B'), ('dbo', 'C')]
        columns = [('dbo', 'A', 'id'), ('dbo', 'B', 'id'), ('dbo', 'C', 'id')]

        sql = qb.build_query(tables=tables, columns=columns, joins=None, where_clause=None, alias_mode='none')

        # FROM deve ser a primeira tabela
        self.assertIn('FROM [dbo].[A]', sql)

        # JOINs devem aparecer na ordem B then C
        pos_b = sql.find('JOIN [dbo].[B]')
        pos_c = sql.find('JOIN [dbo].[C]')
        self.assertTrue(pos_b != -1 and pos_c != -1 and pos_b < pos_c,
                        msg=f'ordem incorreta dos JOINs: pos_b={pos_b}, pos_c={pos_c}\nSQL=\n{sql}')

    def test_join_order_preserved_with_alias(self):
        qb = DummyQB()
        tables = [('dbo', 'Cliente'), ('dbo', 'Pedido'), ('dbo', 'Item')]
        columns = [('dbo', 'Cliente', 'id'), ('dbo', 'Pedido', 'id'), ('dbo', 'Item', 'id')]

        sql = qb.build_query(tables=tables, columns=columns, joins=None, where_clause=None, alias_mode='short')

        # Deve conter FROM com alias para a primeira tabela
        self.assertIn('FROM [dbo].[Cliente] AS', sql)

        # Verifica ordem dos JOINs com aliases (expectativa: cliente -> pedido -> item)
        pos_pedido = sql.find('JOIN [dbo].[Pedido] AS')
        pos_item = sql.find('JOIN [dbo].[Item] AS')
        self.assertTrue(pos_pedido != -1 and pos_item != -1 and pos_pedido < pos_item,
                        msg=f'ordem incorreta dos JOINs com alias: pos_pedido={pos_pedido}, pos_item={pos_item}\nSQL=\n{sql}')

    def test_join_with_relationship_generates_on_using_columns_preserves_order(self):
        """Cenário: tabela B tem FK para A (B.a_id -> A.id).
        Verifica que o JOIN gerado entre A (FROM) e B contém a expressão
        [dbo].[B].[a_id] = [dbo].[A].[id] e que a ordem (A then B) é preservada.
        """
        class RelationshipQB(QueryBuilder):
            def __init__(self):
                super().__init__(connection=None)

            def find_relationship(self, table1: str, table2: str):
                # Simula FK: B -> A (B.a_id references A.id)
                # Quando build_query chamar find_relationship(prev_table, table)
                # com prev_table='A' and table='B', retornamos o FK adequado.
                if table1 == 'A' and table2 == 'B':
                    return ForeignKey(fk_table='B', fk_column='a_id', pk_table='A', pk_column='id', constraint_name='FK_B_A')
                return None

        qb = RelationshipQB()
        tables = [('dbo', 'A'), ('dbo', 'B')]
        columns = [('dbo', 'A', 'id'), ('dbo', 'B', 'a_id')]

        sql = qb.build_query(tables=tables, columns=columns, joins=None, where_clause=None, alias_mode='none')

        # FROM deve ser A
        self.assertIn('FROM [dbo].[A]', sql)

        # JOIN B deve aparecer em seguida
        pos_b = sql.find('JOIN [dbo].[B]')
        self.assertTrue(pos_b != -1, msg=f'JOIN para B não encontrado\nSQL=\n{sql}')

        # ON deve usar as colunas a_id e id na ordem correta
        self.assertIn('[dbo].[B].[a_id] = [dbo].[A].[id]', sql,
                      msg=f'ON gerado incorreto para relacionamento:\n{sql}')


if __name__ == '__main__':
    unittest.main()
