"""
Testes para fluxo de execução de consultas (migrado para tests/)
"""
import unittest
from PyQt5.QtWidgets import QApplication

class TestExecuteFlow(unittest.TestCase):
    """Testa execução da consulta quando não há WHERE e não existem colunas impeditivas."""

    @classmethod
    def setUpClass(cls):
        # garante QApplication para widgets
        if QApplication.instance() is None:
            cls._app = QApplication([])

    def test_execute_without_where_allowed(self):
        from unittest.mock import MagicMock, patch
        from PyQt5.QtWidgets import QListWidgetItem, QMessageBox
        from PyQt5.QtCore import Qt
        from consulta_sql import ColumnInfo

        # Mock do QueryBuilder
        mock_qb = MagicMock()
        mock_qb.get_tables_and_views.return_value = []

        # Retorna colunas sem nenhuma coluna impeditiva (por exemplo: AtivaSN, CodContab)
        mock_qb.get_table_columns.return_value = [
            ColumnInfo(table_schema='dbo', table_name='ClasseFinanceira', column_name='AtivaSN', data_type='bit', is_nullable=False),
            ColumnInfo(table_schema='dbo', table_name='ClasseFinanceira', column_name='CodContab', data_type='int', is_nullable=False),
            ColumnInfo(table_schema='dbo', table_name='ClasseFinanceira', column_name='NomeClasse', data_type='varchar', is_nullable=True),
        ]

        # execute_query do qb deve ser chamado e retornar algo
        mock_qb.execute_query.return_value = (['AtivaSN', 'CodContab', 'NomeClasse'], [(1, 10, 'A'), (0, 20, 'B')])

        mock_qm = MagicMock()

        # Instancia a aba do QueryBuilder (widgets são criados em setup_ui)
        from main import QueryBuilderTab
        tab = QueryBuilderTab(mock_qb, mock_qm)

        # Preenche o preview SQL sem WHERE
        sql = "SELECT cla.[AtivaSN], cla.[CodContab], cla.[NomeClasse]\nFROM [dbo].[ClasseFinanceira] AS cla WITH (NOLOCK)\n\n-- Sem filtros aplicados"
        tab.sql_preview.setPlainText(sql)

    # Adiciona a tabela selecionada (usa UserRole raw text)
    item = QListWidgetItem("[dbo].ClasseFinanceira")
    item.setData(Qt.UserRole, "[dbo].ClasseFinanceira")
        tab.selected_tables_list.addItem(item)

        # Patcher para QMessageBox para interceptar mensagens
        with patch.object(QMessageBox, 'information') as mock_info, \
             patch.object(QMessageBox, 'critical') as mock_critical:
            tab.execute_query()

            # verify execute_query called on qb e information dialog shown
            mock_qb.execute_query.assert_called()
            mock_info.assert_called()

    def test_execute_without_where_blocked_when_impeding_columns_present(self):
        """Quando a tabela contém coluna impeditiva (ex: DataMovimento), a execução sem WHERE deve ser bloqueada."""
        from unittest.mock import MagicMock, patch
        from PyQt5.QtWidgets import QListWidgetItem, QMessageBox
        from PyQt5.QtCore import Qt
        from consulta_sql import ColumnInfo

        mock_qb = MagicMock()
        # Retorna colunas incluindo uma coluna impeditiva (DataMovimento)
        mock_qb.get_table_columns.return_value = [
            ColumnInfo(table_schema='dbo', table_name='ClasseFinanceira', column_name='DataMovimento', data_type='datetime', is_nullable=False),
            ColumnInfo(table_schema='dbo', table_name='ClasseFinanceira', column_name='NomeClasse', data_type='varchar', is_nullable=True),
        ]

        mock_qb.execute_query.return_value = (['DataMovimento', 'NomeClasse'], [(None, 'A')])
        mock_qm = MagicMock()

        from main import QueryBuilderTab
        tab = QueryBuilderTab(mock_qb, mock_qm)

        sql = "SELECT cla.[DataMovimento], cla.[NomeClasse]\nFROM [dbo].[ClasseFinanceira] AS cla WITH (NOLOCK)\n\n-- Sem filtros aplicados"
        tab.sql_preview.setPlainText(sql)

    item = QListWidgetItem("[dbo].ClasseFinanceira")
    item.setData(Qt.UserRole, "[dbo].ClasseFinanceira")
        tab.selected_tables_list.addItem(item)

        with patch.object(QMessageBox, 'information') as mock_info, \
             patch.object(QMessageBox, 'critical') as mock_critical:
            tab.execute_query()

            # execute_query do qb não deve ter sido chamado devido ao bloqueio
            mock_qb.execute_query.assert_not_called()
            mock_critical.assert_called()
