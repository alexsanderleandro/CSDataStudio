import pytest
from join_helpers import build_on_expression_from_conditions


def test_build_on_expression_multiple_conditions():
    # Simular prior_tables e current_table
    prior_tables = [("dbo", "clientes"), ("dbo", "pedidos")]
    current_table = ("dbo", "itens")

    conditions = [
        {"prior_table_idx": 0, "prior_col": "id_cliente", "op": "=", "curr_col": "cliente_id"},
        {"prior_table_idx": 1, "prior_col": "id_pedido", "op": "=", "curr_col": "pedido_id"},
    ]

    expr = build_on_expression_from_conditions(prior_tables, current_table, conditions)

    expected = (
        "[dbo].[clientes].[id_cliente] = [dbo].[itens].[cliente_id] AND "
        "[dbo].[pedidos].[id_pedido] = [dbo].[itens].[pedido_id]"
    )
    assert expr == expected


if __name__ == '__main__':
    pytest.main([__file__])
