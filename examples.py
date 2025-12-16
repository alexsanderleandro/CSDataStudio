"""
Exemplos de uso programático do CSData Studio
Demonstra como usar as classes e funções sem a interface gráfica
"""

# Exemplo 1: Conexão e Autenticação
def exemplo_autenticacao():
    """Exemplo de autenticação no banco"""
    from authentication import verify_user, get_db_connection
    
    print("=== Exemplo 1: Autenticação ===\n")
    
    # Verifica credenciais
    user_data = verify_user("admin", "senha123")
    
    if user_data:
        print(f"✅ Login bem-sucedido!")
        print(f"Código: {user_data['CodUsuario']}")
        print(f"Nome: {user_data['NomeUsuario']}")
        print(f"Gerente: {user_data['PDVGerenteSN']}")
    else:
        print("❌ Falha no login")
    
    # Conexão direta
    try:
        conn = get_db_connection()
        print("\n✅ Conexão estabelecida")
        conn.close()
    except Exception as e:
        print(f"\n❌ Erro na conexão: {e}")

# Exemplo 2: Construção de Query
def exemplo_construir_query():
    """Exemplo de construção de query SQL"""
    from authentication import get_db_connection
    from consulta_sql import QueryBuilder, JoinType
    
    print("\n=== Exemplo 2: Construir Query ===\n")
    
    conn = get_db_connection()
    qb = QueryBuilder(conn)
    
    # Define tabelas
    tables = [
        ('dbo', 'Vendas'),
        ('dbo', 'Clientes')
    ]
    
    # Define colunas
    columns = [
        ('dbo', 'Vendas', 'NumeroVenda'),
        ('dbo', 'Vendas', 'DataVenda'),
        ('dbo', 'Vendas', 'ValorTotal'),
        ('dbo', 'Clientes', 'NomeCliente')
    ]
    
    # Define JOINs
    joins = {
        ('Vendas', 'Clientes'): JoinType.INNER
    }
    
    # WHERE
    where = "DataVenda >= '2024-01-01'"
    
    # Gera SQL
    try:
        sql = qb.build_query(tables, columns, joins, where)
        print("SQL Gerada:")
        print(sql)
    except Exception as e:
        print(f"❌ Erro: {e}")
    finally:
        conn.close()

# Exemplo 3: Executar Consulta
def exemplo_executar_query():
    """Exemplo de execução de consulta"""
    from authentication import get_db_connection
    from consulta_sql import QueryBuilder
    from valida_sql import validar_sql
    
    print("\n=== Exemplo 3: Executar Query ===\n")
    
    sql = """
    SELECT TOP 10
        NomeCliente,
        COUNT(*) as TotalCompras,
        SUM(ValorTotal) as ValorTotal
    FROM dbo.Vendas V
    INNER JOIN dbo.Clientes C ON V.CodCliente = C.CodCliente
    WHERE DataVenda >= '2024-01-01'
    GROUP BY NomeCliente
    ORDER BY ValorTotal DESC
    """
    
    # Valida SQL
    is_valid, error = validar_sql(sql)
    if not is_valid:
        print(f"❌ SQL inválida: {error}")
        return
    
    print("✅ SQL validada")
    
    # Executa
    try:
        conn = get_db_connection()
        qb = QueryBuilder(conn)
        
        columns, data = qb.execute_query(sql)
        
        print(f"\n📊 Resultado: {len(data)} registros\n")
        print("Colunas:", ", ".join(columns))
        print("\nPrimeiras 5 linhas:")
        for i, row in enumerate(data[:5], 1):
            print(f"{i}. {row}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro: {e}")

# Exemplo 4: Salvar e Carregar Consultas
def exemplo_gerenciar_consultas():
    """Exemplo de gerenciamento de consultas salvas"""
    from saved_queries import QueryManager
    
    print("\n=== Exemplo 4: Gerenciar Consultas ===\n")
    
    qm = QueryManager()
    
    # Salva uma consulta
    sql = "SELECT * FROM dbo.Produtos WHERE Ativo = 1"
    
    try:
        qm.add_query(
            name="Produtos Ativos",
            sql=sql,
            description="Lista todos os produtos ativos",
            created_by="Admin",
            tags=["produtos", "estoque"]
        )
        print("✅ Consulta salva: 'Produtos Ativos'")
    except Exception as e:
        print(f"❌ Erro ao salvar: {e}")
    
    # Lista consultas
    print("\n📋 Consultas salvas:")
    for query in qm.list_queries():
        print(f"  - {query.name}: {query.description}")
    
    # Carrega uma consulta
    query = qm.get_query("Produtos Ativos")
    if query:
        print(f"\n📄 Consulta carregada:")
        print(f"Nome: {query.name}")
        print(f"SQL: {query.sql}")
    
    # Busca por tag
    print("\n🔍 Consultas com tag 'produtos':")
    for query in qm.list_queries(tag="produtos"):
        print(f"  - {query.name}")

# Exemplo 5: Gerar Gráfico
def exemplo_gerar_grafico():
    """Exemplo de geração de gráfico"""
    from chart_generator import ChartGenerator, ChartType, AggregationType
    import matplotlib.pyplot as plt
    
    print("\n=== Exemplo 5: Gerar Gráfico ===\n")
    
    # Dados de exemplo
    columns = ['Produto', 'Quantidade', 'Valor']
    data = [
        ('Notebook', 10, 5000),
        ('Mouse', 50, 150),
        ('Teclado', 30, 300),
        ('Monitor', 20, 2000),
        ('Headset', 25, 250)
    ]
    
    cg = ChartGenerator()
    
    try:
        fig = cg.create_chart(
            data=data,
            columns=columns,
            x_column='Produto',
            y_column='Quantidade',
            aggregation=AggregationType.SUM,
            chart_type=ChartType.COLUMN,
            title='Quantidade Vendida por Produto',
            color='#3498db'
        )
        
        print("✅ Gráfico gerado")
        
        # Salva
        output_path = 'grafico_exemplo.png'
        cg.save_chart(fig, output_path)
        print(f"💾 Gráfico salvo em: {output_path}")
        
        # Exibe (opcional)
        # plt.show()
        
    except Exception as e:
        print(f"❌ Erro: {e}")

# Exemplo 6: Gerar Insights com IA
def exemplo_gerar_insights():
    """Exemplo de geração de insights com OpenAI"""
    from ai_insights import AIInsightsGenerator
    
    print("\n=== Exemplo 6: Gerar Insights com IA ===\n")
    
    # Dados de exemplo
    columns = ['Produto', 'Categoria', 'Vendas', 'Receita']
    data = [
        ('Notebook', 'Eletrônicos', 150, 450000),
        ('Mouse', 'Acessórios', 500, 25000),
        ('Teclado', 'Acessórios', 300, 30000),
        ('Monitor', 'Eletrônicos', 200, 200000),
        ('Headset', 'Acessórios', 250, 37500)
    ]
    
    # IMPORTANTE: Substitua pela sua chave real
    api_key = "sua-chave-openai-aqui"
    
    if api_key == "sua-chave-openai-aqui":
        print("⚠️  Configure sua chave da API OpenAI no código")
        print("   Obtenha em: https://platform.openai.com/api-keys")
        return
    
    try:
        ai = AIInsightsGenerator(api_key)
        
        print("🤖 Gerando insights...")
        insights = ai.generate_insights(
            data=data,
            columns=columns,
            query_description="Análise de vendas por produto"
        )
        
        print("\n" + "="*60)
        print(insights)
        print("="*60)
        
    except Exception as e:
        print(f"❌ Erro: {e}")

# Exemplo 7: Gerar Relatório PDF
def exemplo_gerar_pdf():
    """Exemplo de geração de relatório PDF"""
    from report_generator import ReportGenerator
    from chart_generator import ChartGenerator, ChartType, AggregationType
    
    print("\n=== Exemplo 7: Gerar Relatório PDF ===\n")
    
    # Dados
    columns = ['Produto', 'Quantidade', 'Valor']
    data = [
        ('Notebook', 10, 5000),
        ('Mouse', 50, 150),
        ('Teclado', 30, 300),
        ('Monitor', 20, 2000),
        ('Headset', 25, 250)
    ]
    
    # Gera gráfico
    cg = ChartGenerator()
    fig = cg.create_chart(
        data, columns, 'Produto', 'Quantidade',
        AggregationType.SUM, ChartType.COLUMN,
        'Vendas por Produto'
    )
    
    # Insights simulados
    insights = """
Análise de Vendas

1. Principais Observações:
   - Maior volume: Mouse (50 unidades)
   - Maior receita: Notebook (R$ 50.000)
   - Ticket médio mais alto: Notebook

2. Recomendações:
   - Aumentar estoque de mouses devido alta demanda
   - Promover notebooks para maximizar receita
   - Considerar combos (notebook + acessórios)
    """
    
    # Gera PDF
    rg = ReportGenerator()
    
    try:
        output_path = 'relatorio_exemplo.pdf'
        
        success = rg.create_report(
            output_path=output_path,
            report_name="Relatório de Vendas - Janeiro 2024",
            user_name="Admin",
            orientation='portrait',
            include_insights=True,
            insights_text=insights,
            include_chart=True,
            chart_figure=fig,
            include_table=True,
            columns=columns,
            data=data
        )
        
        if success:
            print(f"✅ PDF gerado: {output_path}")
        else:
            print("❌ Erro ao gerar PDF")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

# Exemplo 8: Exportar VIEW para Power BI
def exemplo_exportar_view():
    """Exemplo de exportação de VIEW SQL"""
    from saved_queries import QueryManager
    
    print("\n=== Exemplo 8: Exportar VIEW para Power BI ===\n")
    
    qm = QueryManager()
    
    # Cria consulta de exemplo
    sql = """
    SELECT 
        V.DataVenda,
        C.NomeCliente,
        P.NomeProduto,
        V.Quantidade,
        V.ValorUnitario,
        V.Quantidade * V.ValorUnitario as ValorTotal
    FROM dbo.Vendas V
    INNER JOIN dbo.Clientes C ON V.CodCliente = C.CodCliente
    INNER JOIN dbo.Produtos P ON V.CodProduto = P.CodProduto
    WHERE V.DataVenda >= DATEADD(MONTH, -6, GETDATE())
    """
    
    qm.add_query(
        name="Vendas Últimos 6 Meses",
        sql=sql,
        description="Dados detalhados de vendas dos últimos 6 meses",
        created_by="Admin",
        overwrite=True
    )
    
    # Exporta como VIEW
    try:
        view_sql = qm.export_query_as_view(
            "Vendas Últimos 6 Meses",
            "vw_Vendas_6Meses"
        )
        
        print("✅ VIEW SQL gerada:")
        print("\n" + "="*60)
        print(view_sql)
        print("="*60)
        
        # Salva em arquivo
        output_path = 'view_powerbi.sql'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(view_sql)
        
        print(f"\n💾 Salvo em: {output_path}")
        print("\nPara usar no Power BI:")
        print("1. Execute este script no SQL Server")
        print("2. No Power BI, conecte ao SQL Server")
        print("3. Importe a view 'vw_Vendas_6Meses'")
        
    except Exception as e:
        print(f"❌ Erro: {e}")

# Menu principal
def main():
    """Menu de exemplos"""
    print("\n" + "="*60)
    print("  CSData Studio - Exemplos de Uso Programático")
    print("="*60)
    
    exemplos = [
        ("Autenticação", exemplo_autenticacao),
        ("Construir Query", exemplo_construir_query),
        ("Executar Query", exemplo_executar_query),
        ("Gerenciar Consultas", exemplo_gerenciar_consultas),
        ("Gerar Gráfico", exemplo_gerar_grafico),
        ("Gerar Insights com IA", exemplo_gerar_insights),
        ("Gerar Relatório PDF", exemplo_gerar_pdf),
        ("Exportar VIEW para Power BI", exemplo_exportar_view),
    ]
    
    while True:
        print("\n📚 Selecione um exemplo:")
        for i, (nome, _) in enumerate(exemplos, 1):
            print(f"  {i}. {nome}")
        print("  0. Executar todos")
        print("  Q. Sair")
        
        escolha = input("\nOpção: ").strip().upper()
        
        if escolha == 'Q':
            break
        
        if escolha == '0':
            for nome, func in exemplos:
                print(f"\n{'='*60}")
                print(f"Executando: {nome}")
                print('='*60)
                try:
                    func()
                except Exception as e:
                    print(f"❌ Erro: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            try:
                idx = int(escolha) - 1
                if 0 <= idx < len(exemplos):
                    nome, func = exemplos[idx]
                    func()
                else:
                    print("❌ Opção inválida")
            except ValueError:
                print("❌ Opção inválida")
    
    print("\n👋 Até logo!")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Até logo!")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()