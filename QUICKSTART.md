# 🚀 Guia Rápido - CSData Studio

## Instalação em 5 Minutos

### 1️⃣ Pré-requisitos
```bash
# Verifique se tem Python 3.8+
python --version

# Instale ODBC Driver 17 for SQL Server
# Download: https://aka.ms/downloadmsodbcsql
```

### 2️⃣ Clone e Configure
```bash
# Clone o repositório
git clone https://github.com/ceosoft/csdatastudio.git
cd csdatastudio

# Crie ambiente virtual
python -m venv venv

# Ative o ambiente
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Execute o setup automático
python setup.py
```

### 3️⃣ Configure o Banco
Edite `C:\CEOSoftware\CSLogin.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <database>
    <type>MSSQL</type>
    <name>BDCEOSOFTWARE</name>
    <server>SEU-SERVIDOR</server>
  </database>
</configuration>
```

### 4️⃣ Execute
```bash
python main.py
```

## 🎯 Primeiro Uso

### Login
1. Digite seu **usuário** do SQL Server
2. Digite sua **senha**
3. Clique em **OK**

> ⚠️ Seu usuário precisa ter `InativosN = 0` e `PDVGerenteSN = 1`

### Criar sua Primeira Consulta

#### Passo 1: Selecionar Tabelas
1. Na aba **"Construtor de Consultas"**
2. Selecione tabelas da lista à esquerda
3. Clique em **"Adicionar Tabelas Selecionadas"**

#### Passo 2: Selecionar Colunas
1. Escolha colunas na lista central
2. Clique em **"Adicionar Colunas"**

#### Passo 3: Configurar JOIN
1. Escolha o tipo: **INNER**, **LEFT** ou **RIGHT**
2. O sistema detecta automaticamente os relacionamentos!

#### Passo 4: Adicionar Filtros
1. Digite sua cláusula WHERE
2. Exemplo: `DataVenda >= '2024-01-01'`

#### Passo 5: Executar
1. Clique em **"Gerar SQL"**
2. Revise a SQL gerada
3. Clique em **"Executar Consulta"**

### Ver Resultados
1. Vá para aba **"Resultados e Análise"**
2. Veja seus dados em formato tabela
3. Clique nos cabeçalhos para ordenar

## 🎨 Recursos Avançados

### Gerar Gráfico
```
1. Clique em "Gerar Gráfico"
2. Escolha coluna para eixo X
3. Escolha coluna para eixo Y
4. Selecione agregação (COUNT, SUM, etc)
5. Escolha tipo (Barras ou Colunas)
6. Clique OK
```

### Insights com IA
```
1. Configure chave OpenAI em "Ferramentas" → "Configurar API OpenAI"
2. Clique em "Gerar Insights com IA"
3. Aguarde a análise
4. Leia os insights gerados
```

### Exportar PDF
```
1. Clique em "Exportar PDF"
2. Preencha nome do relatório
3. Escolha orientação (Retrato/Paisagem)
4. Marque o que incluir:
   ☑ Insights da IA
   ☑ Gráfico
   ☑ Tabela de Resultados
5. Escolha onde salvar
6. Clique OK
```

### Salvar Consulta
```
1. Crie sua query
2. Clique "Salvar Consulta"
3. Dê um nome único
4. Adicione descrição (opcional)
5. Clique OK
```

### Carregar Consulta Salva
```
1. Clique "Carregar Consulta"
2. Selecione da lista
3. Clique OK
4. A SQL será carregada automaticamente
```

## 💡 Dicas Rápidas

### Atalhos Úteis
- `Enter` no campo de senha = Login
- Clique duplo em coluna da tabela = Adiciona automaticamente
- Ctrl+C na SQL gerada = Copia para área de transferência

### Boas Práticas
1. ✅ **Sempre use WHERE**: Evita consultas que retornam milhões de linhas
2. ✅ **Teste com LIMIT**: Adicione `TOP 100` nas suas queries iniciais
3. ✅ **Salve consultas úteis**: Use nomes descritivos
4. ✅ **Use tags**: Organize consultas por categoria

### Erros Comuns

#### "Usuário ou senha inválidos"
- Verifique se o usuário existe na tabela `Usuarios`
- Verifique se `InativosN = 0` e `PDVGerenteSN = 1`

#### "Erro ao conectar ao banco"
- Verifique se o SQL Server está rodando
- Verifique o nome do servidor em `CSLogin.xml`
- Teste conexão com SSMS primeiro

#### "SQL inválida"
- Certifique-se de incluir cláusula WHERE
- Não use comandos como INSERT, UPDATE, DELETE
- Não use ponto-e-vírgula (;)

#### "Erro ao gerar gráfico"
- Verifique se há dados no resultado
- Escolha colunas com valores numéricos para eixo Y
- Use agregações adequadas (SUM para valores, COUNT para contagens)

## 📊 Exemplos Prontos

### Exemplo 1: Vendas do Mês
```sql
SELECT 
    CONVERT(DATE, DataVenda) as Data,
    COUNT(*) as TotalVendas,
    SUM(ValorTotal) as Faturamento
FROM dbo.Vendas
WHERE DataVenda >= DATEADD(MONTH, -1, GETDATE())
GROUP BY CONVERT(DATE, DataVenda)
ORDER BY Data
```

### Exemplo 2: Top 10 Clientes
```sql
SELECT TOP 10
    C.NomeCliente,
    COUNT(V.NumeroVenda) as TotalCompras,
    SUM(V.ValorTotal) as ValorTotal
FROM dbo.Vendas V
INNER JOIN dbo.Clientes C ON V.CodCliente = C.CodCliente
WHERE V.DataVenda >= '2024-01-01'
GROUP BY C.NomeCliente
ORDER BY ValorTotal DESC
```

### Exemplo 3: Produtos Mais Vendidos
```sql
SELECT 
    P.NomeProduto,
    SUM(VI.Quantidade) as Quantidade,
    SUM(VI.Quantidade * VI.PrecoUnitario) as Receita
FROM dbo.VendasItens VI
INNER JOIN dbo.Produtos P ON VI.CodProduto = P.CodProduto
INNER JOIN dbo.Vendas V ON VI.NumeroVenda = V.NumeroVenda
WHERE V.DataVenda >= DATEADD(MONTH, -3, GETDATE())
GROUP BY P.NomeProduto
ORDER BY Quantidade DESC
```

## 🔧 Troubleshooting Rápido

### Reset Completo
```bash
# Para apagar todas as consultas salvas
# Windows:
del %APPDATA%\CSDataStudio\saved_queries.json

# Linux:
rm ~/.config/CSDataStudio/saved_queries.json
```

### Atualizar Dependências
```bash
pip install -r requirements.txt --upgrade
```

### Logs
```bash
# Verifique erros em:
# Windows: %APPDATA%\CSDataStudio\logs\
# Linux: ~/.config/CSDataStudio/logs/
```

## 📞 Precisa de Ajuda?

1. 📖 Leia o [README.md](README.md) completo
2. 💻 Veja os [exemplos.py](examples.py) de uso programático
3. 📧 Entre em contato: suporte@ceosoftware.com.br

---

**🎉 Pronto! Você já está usando o CSData Studio!**

Para recursos avançados, consulte a documentação completa no README.md