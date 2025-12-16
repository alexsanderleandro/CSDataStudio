"""
Testes unitários para CSData Studio
Execute com: python -m pytest test_csdatastudio.py -v
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import tempfile

# Testes de Validação SQL
class TestValidacaoSQL(unittest.TestCase):
    """Testes para validação de SQL"""
    
    def setUp(self):
        from valida_sql import validar_sql, validar_sql_for_save
        self.validar_sql = validar_sql
        self.validar_sql_for_save = validar_sql_for_save
    
    def test_select_valido(self):
        """Testa SELECT válido"""
        sql = "SELECT * FROM Produtos WHERE Ativo = 1"
        is_valid, msg = self.validar_sql(sql)
        self.assertTrue(is_valid)
    
    def test_select_sem_where(self):
        """Testa SELECT sem WHERE (deve falhar)"""
        sql = "SELECT * FROM Produtos"
        is_valid, msg = self.validar_sql(sql)
        self.assertFalse(is_valid)
        self.assertIn("WHERE", msg)
    
    def test_insert_bloqueado(self):
        """Testa que INSERT é bloqueado"""
        sql = "INSERT INTO Produtos VALUES (1, 'Teste') WHERE 1=1"
        is_valid, msg = self.validar_sql(sql)
        self.assertFalse(is_valid)
        self.assertIn("INSERT", msg)
    
    def test_update_bloqueado(self):
        """Testa que UPDATE é bloqueado"""
        sql = "UPDATE Produtos SET Nome = 'Teste' WHERE Id = 1"
        is_valid, msg = self.validar_sql(sql)
        self.assertFalse(is_valid)
        self.assertIn("UPDATE", msg)
    
    def test_delete_bloqueado(self):
        """Testa que DELETE é bloqueado"""
        sql = "DELETE FROM Produtos WHERE Id = 1"
        is_valid, msg = self.validar_sql(sql)
        self.assertFalse(is_valid)
        self.assertIn("DELETE", msg)
    
    def test_exec_bloqueado(self):
        """Testa que EXEC é bloqueado"""
        sql = "EXEC sp_configure WHERE 1=1"
        is_valid, msg = self.validar_sql(sql)
        self.assertFalse(is_valid)
        self.assertIn("EXEC", msg)
    
    def test_multiplas_statements(self):
        """Testa que múltiplas statements são bloqueadas"""
        sql = "SELECT * FROM Produtos WHERE 1=1; DROP TABLE Produtos"
        is_valid, msg = self.validar_sql(sql)
        self.assertFalse(is_valid)
        self.assertIn(";", msg.lower())
    
    def test_select_com_join(self):
        """Testa SELECT com JOIN"""
        sql = """
        SELECT P.Nome, C.Categoria
        FROM Produtos P
        INNER JOIN Categorias C ON P.CodCategoria = C.CodCategoria
        WHERE P.Ativo = 1
        """
        is_valid, msg = self.validar_sql(sql)
        self.assertTrue(is_valid)
    
    def test_select_com_cte(self):
        """Testa SELECT com CTE (WITH)"""
        sql = """
        WITH VendasRecentes AS (
            SELECT * FROM Vendas WHERE DataVenda >= '2024-01-01'
        )
        SELECT * FROM VendasRecentes WHERE ValorTotal > 1000
        """
        is_valid, msg = self.validar_sql(sql)
        self.assertTrue(is_valid)
    
    def test_union_all_permitido(self):
        """Testa que UNION ALL é permitido"""
        sql = """
        SELECT Nome FROM ProdutosA WHERE Ativo = 1
        UNION ALL
        SELECT Nome FROM ProdutosB WHERE Ativo = 1
        """
        is_valid, msg = self.validar_sql(sql)
        self.assertTrue(is_valid)
    
    def test_union_simples_bloqueado(self):
        """Testa que UNION simples é bloqueado"""
        sql = """
        SELECT Nome FROM ProdutosA WHERE Ativo = 1
        UNION
        SELECT Nome FROM ProdutosB WHERE Ativo = 1
        """
        is_valid, msg = self.validar_sql(sql)
        self.assertFalse(is_valid)
        self.assertIn("UNION", msg)

# Testes de Gerenciador de Consultas
class TestQueryManager(unittest.TestCase):
    """Testes para gerenciador de consultas salvas"""
    
    def setUp(self):
        from saved_queries import QueryManager
        # Usa arquivo temporário
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.qm = QueryManager(self.temp_file.name)
    
    def tearDown(self):
        # Remove arquivo temporário
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_adicionar_consulta(self):
        """Testa adicionar consulta"""
        result = self.qm.add_query(
            name="Teste",
            sql="SELECT * FROM Produtos WHERE Ativo = 1",
            description="Consulta de teste",
            created_by="Admin"
        )
        self.assertTrue(result)
    
    def test_recuperar_consulta(self):
        """Testa recuperar consulta"""
        self.qm.add_query(
            name="Teste",
            sql="SELECT * FROM Produtos WHERE Ativo = 1",
            created_by="Admin"
        )
        
        query = self.qm.get_query("Teste")
        self.assertIsNotNone(query)
        self.assertEqual(query.name, "Teste")
    
    def test_listar_consultas(self):
        """Testa listar consultas"""
        self.qm.add_query("Query1", "SELECT 1 WHERE 1=1", created_by="Admin")
        self.qm.add_query("Query2", "SELECT 2 WHERE 1=1", created_by="Admin")
        
        queries = self.qm.list_queries()
        self.assertEqual(len(queries), 2)
    
    def test_deletar_consulta(self):
        """Testa deletar consulta"""
        self.qm.add_query("Teste", "SELECT 1 WHERE 1=1", created_by="Admin")
        result = self.qm.delete_query("Teste")
        self.assertTrue(result)
        
        query = self.qm.get_query("Teste")
        self.assertIsNone(query)
    
    def test_buscar_consultas(self):
        """Testa buscar consultas"""
        self.qm.add_query(
            "Produtos Ativos",
            "SELECT * FROM Produtos WHERE Ativo = 1",
            created_by="Admin"
        )
        self.qm.add_query(
            "Clientes",
            "SELECT * FROM Clientes WHERE 1=1",
            created_by="Admin"
        )
        
        results = self.qm.search_queries("produtos")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Produtos Ativos")
    
    def test_renomear_consulta(self):
        """Testa renomear consulta"""
        self.qm.add_query("Antigo", "SELECT 1 WHERE 1=1", created_by="Admin")
        result = self.qm.rename_query("Antigo", "Novo")
        self.assertTrue(result)
        
        query = self.qm.get_query("Novo")
        self.assertIsNotNone(query)

# Testes de Configuração
class TestConfigManager(unittest.TestCase):
    """Testes para gerenciador de configurações"""
    
    def setUp(self):
        from config_manager import ConfigManager
        self.temp_file = tempfile.NamedTemporaryFile(
            delete=False, 
            suffix='.xml',
            mode='w',
            encoding='utf-8'
        )
        self.temp_file.write("""<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <database>
    <type>MSSQL</type>
    <n>TestDB</n>
    <server>TestServer</server>
  </database>
</configuration>""")
        self.temp_file.close()
        
        # Sobrescreve o caminho de configuração temporariamente
        ConfigManager.CONFIG_PATH = self.temp_file.name
    
    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_ler_config(self):
        """Testa leitura de configuração"""
        from config_manager import ConfigManager
        
        config = ConfigManager.read_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.db_type, "MSSQL")
        self.assertEqual(config.db_name, "TestDB")
        self.assertEqual(config.server_name, "TestServer")
    
    def test_config_valida(self):
        """Testa validação de configuração"""
        from config_manager import DatabaseConfig
        
        config = DatabaseConfig(
            db_type="MSSQL",
            db_name="TestDB",
            server_name="TestServer"
        )
        self.assertTrue(config.is_valid())
    
    def test_config_invalida(self):
        """Testa configuração inválida"""
        from config_manager import DatabaseConfig
        
        config = DatabaseConfig(
            db_type="",
            db_name="",
            server_name=""
        )
        self.assertFalse(config.is_valid())

# Testes de Versão
class TestVersion(unittest.TestCase):
    """Testes para controle de versão"""
    
    def test_get_version(self):
        """Testa obtenção de versão"""
        from version import Version
        
        version = Version.get_version()
        self.assertIsInstance(version, str)
        self.assertRegex(version, r'\d{2}\.\d{2}\.\d{2} rev\.\d+')
    
    def test_get_full_name(self):
        """Testa nome completo"""
        from version import Version, APP_NAME
        
        full_name = Version.get_full_name()
        self.assertIn(APP_NAME, full_name)
        self.assertIn("v", full_name)

# Testes de Chart Generator
class TestChartGenerator(unittest.TestCase):
    """Testes para gerador de gráficos"""
    
    def setUp(self):
        from chart_generator import ChartGenerator
        self.cg = ChartGenerator()
    
    def test_create_chart(self):
        """Testa criação de gráfico"""
        from chart_generator import ChartType, AggregationType
        
        columns = ['Produto', 'Quantidade']
        data = [
            ('Produto A', 10),
            ('Produto B', 20),
            ('Produto C', 15)
        ]
        
        fig = self.cg.create_chart(
            data=data,
            columns=columns,
            x_column='Produto',
            y_column='Quantidade',
            aggregation=AggregationType.SUM,
            chart_type=ChartType.COLUMN,
            title='Teste'
        )
        
        self.assertIsNotNone(fig)

# Runner
def run_tests():
    """Executa todos os testes"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Adiciona todos os testes
    suite.addTests(loader.loadTestsFromTestCase(TestValidacaoSQL))
    suite.addTests(loader.loadTestsFromTestCase(TestQueryManager))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigManager))
    suite.addTests(loader.loadTestsFromTestCase(TestVersion))
    suite.addTests(loader.loadTestsFromTestCase(TestChartGenerator))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)