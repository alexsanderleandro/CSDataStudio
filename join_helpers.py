from typing import List, Tuple


def build_on_expression_from_conditions(prior_tables: List[Tuple[str, str]], current_table: Tuple[str, str], conditions: list) -> str:
    """
    Helper puro para montar a expressão ON a partir de condições (sem UI).

    Retorna ' AND '-joined expression ou None se inválido.
    """
    try:
        if not conditions:
            return None
        parts = []
        for c in conditions:
            idx = int(c.get('prior_table_idx', -1))
            if idx < 0 or idx >= len(prior_tables):
                return None
            ps, pt = prior_tables[idx]
            pc = str(c.get('prior_col') or '').strip()
            op = str(c.get('op') or '=').strip()
            cc = str(c.get('curr_col') or '').strip()
            if not pc or not cc:
                return None
            parts.append(f"[{ps}].[{pt}].[{pc}] {op} [{current_table[0]}].[{current_table[1]}].[{cc}]")
        return ' AND '.join(parts)
    except Exception:
        return None
