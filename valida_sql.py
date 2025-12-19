"""Validador de SQL - implementação simplificada para desenvolvimento.

Fornece `validar_sql` e `validar_sql_for_save` que aplicam checagens
conservadoras: permitem apenas SELECT e rejeitam comandos potencialmente
modificadores (INSERT/UPDATE/DELETE/DROP) ou múltiplas statements.
"""
from typing import Tuple
import re


def _normalize(sql: str) -> str:
    return (sql or "").strip()


def validar_sql(sql: str) -> Tuple[bool, str]:
    s = _normalize(sql)
    if not s:
        return False, "SQL vazia"

    low = s.lower()

    # Bloqueia múltiplas statements (presença de ';' indicando múltiplas)
    if ";" in s:
        return False, "Múltiplas statements não permitidas; use apenas uma SELECT"

    # Bloqueia EXEC
    if re.search(r"\bexec\b", low):
        return False, "EXEC não permitido"

    # Bloqueia comandos de escrita/DDL
    for kw in ["insert", "update", "delete", "drop", "alter", "truncate"]:
        if re.search(r"\b" + kw + r"\b", low):
            return False, f"{kw.upper()} não permitido"

    # UNION simples é proibido; UNION ALL é permitido
    if re.search(r"\bunion\b(?!\s+all)", low):
        return False, "UNION simples não permitido; use UNION ALL se necessário"

    # Deve começar com SELECT ou WITH (CTE)
    if not (low.startswith("select") or low.startswith("with")):
        return False, "Somente SELECT é permitido"

    # Requer cláusula WHERE em cada SELECT/CTE final (checagem simplificada)
    # Procura por WHERE usando borda de palavra para cobrir quebras de linha/formatacoes
    if not re.search(r"\bwhere\b", low):
        return False, "Falta cláusula WHERE"

    return True, ""


def validar_sql_for_save(sql: str) -> Tuple[bool, str]:
    # Mesmas regras para salvar
    return validar_sql(sql)
