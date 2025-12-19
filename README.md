# CSData Studio

Sistema de Business Intelligence e Análise de Dados desenvolvido em Python + PyQt5

![Versão](https://img.shields.io/badge/versão-25.01.15%20rev.1-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-Proprietária-red)

## 📋 Características

- **Construtor Visual de Consultas SQL**: Interface intuitiva para criar queries complexas com múltiplas tabelas e JOINs
- **Detecção Automática de Relacionamentos**: Identifica chaves estrangeiras entre tabelas automaticamente
- **Validação de Segurança**: Valida todas as consultas para prevenir SQL injection e comandos perigosos
- **Geração de Gráficos**: Cria gráficos de barras e colunas com agregações (COUNT, SUM, AVG, MIN, MAX)
- **Insights com IA**: Integração com OpenAI para análise inteligente dos dados
- **Relatórios em PDF**: Exportação completa com insights, gráficos e dados em formato profissional
- **Exportação para Power BI**: Gera views SQL compatíveis com Microsoft Power BI
- **Gerenciamento de Consultas**: Salva, carrega e organiza consultas favoritas

## 🎯 Requisitos

### Sistema Operacional
- Windows 10/11 (recomendado)
- Linux (testado em Ubuntu 20.04+)

### Software
- Python 3.8 ou superior
- SQL Server 2016 ou superior
- ODBC Driver 17 for SQL Server

### Permissões de Banco
O usuário deve ter:
- `InativosN = 0`
- `PDVGerenteSN = 1`
- Permissões de SELECT nas tabelas desejadas

## 🚀 Instalação

### 1. Instalar ODBC Driver (Windows)

```bash
# Baixe e instale o ODBC Driver 17 for SQL Server
https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
```

### 2. Clonar o Repositório

```bash
git clone https://github.com/ceosoft/csdatastudio.git
cd csdatastudio
```

### 3. Criar Ambiente Virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 4. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 5. Configurar Banco de Dados

Crie o arquivo `C:\CEOSoftware\CSLogin.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <database>
    <type>MSSQL</type>
    <name>BDCEOSOFTWARE</name>
    <server>CEOSOFT-SERV2</server>
  </database>
</configuration>
```

Ou use o código para criar automaticamente:

```python
from config_manager import ConfigManager
ConfigManager.create_sample_config()
```

## 📖 Uso

### Executar a Aplicação

```bash
python main.py
```

### Fluxo de Trabalho

1. **Login**: Entre com suas credenciais do SQL Server
2. **Construir Consulta**:
   - Selecione tabelas da lista à esquerda
   - Adicione às tabelas selecionadas
   - Escolha as colunas desejadas
   - Configure o tipo de JOIN (INNER, LEFT, RIGHT)
   - Adicione cláusula WHERE (obrigatório)
   - Clique em "Gerar SQL" e depois "Executar Consulta"
3. **Analisar Resultados**:
   - Visualize os dados na aba "Resultados e Análise"
   - Ordene colunas clicando nos cabeçalhos
   - Gere insights com IA (requer chave OpenAI)
   - Crie gráficos personalizados
   - Exporte para PDF

### Salvar Consultas

```python
# Na aba "Construtor de Consultas"
1. Crie sua consulta
2. Clique em "Salvar Consulta"
3. Dê um nome único
4. Adicione uma descrição (opcional)
```

### Exportar para Power BI

```python
# Carregue uma consulta salva
# Clique em "Exportar como VIEW"
# Copie o SQL gerado
# Execute no SQL Server Management Studio
# Use a VIEW no Power BI
```

## 🔒 Segurança

O CSData Studio implementa várias camadas de segurança:

### Validação de SQL
- ✅ Permite apenas comandos SELECT
- ❌ Bloqueia INSERT, UPDATE, DELETE
- ❌ Bloqueia comandos administrativos (EXEC, sp_configure, xp_cmdshell)
- ❌ Bloqueia múltiplas statements
- ✅ Exige cláusula WHERE obrigatória

### Sanitização
- Remove comentários SQL
- Remove strings literais
- Valida com expressões regulares
- Previne SQL Injection

### Autenticação
- Login via stored procedure `csspValidaSenha`
- Validação de permissões no banco
- Controle de acesso por usuário

## 📊 Estrutura de Arquivos

```
csdatastudio/
│
├── main.py                 # Aplicação principal PyQt5
├── authentication.py       # Lógica de autenticação
├── config_manager.py       # Gerenciador de configurações XML
├── consulta_sql.py         # Construtor de queries e metadata
├── saved_queries.py        # Gerenciador de consultas salvas
├── chart_generator.py      # Gerador de gráficos matplotlib
├── ai_insights.py          # Integração com OpenAI
├── report_generator.py     # Gerador de PDF
├── valida_sql.py           # Validador de SQL
├── version.py              # Controle de versão
├── dialogs.py              # Dialogs auxiliares
├── requirements.txt        # Dependências Python
└── README.md               # Este arquivo
```

## ⚙️ Configuração da OpenAI

Para usar a funcionalidade de insights com IA:

1. Obtenha uma chave de API em https://platform.openai.com/api-keys
2. No menu "Ferramentas" → "Configurar API OpenAI"
3. Cole sua chave da API
4. A chave é armazenada apenas durante a sessão

## 📝 Formato de Relatório PDF

### Cabeçalho
- **Esquerda**: Nome da empresa (CEO Software)
- **Direita**: 
  - Nome do aplicativo e versão
  - Nome da pesquisa (obrigatório)

### Corpo
Ordem configurável:
1. Insights da IA (se gerado)
2. Gráfico (se gerado)
3. Tabela de resultados

### Rodapé
- Usuário, data e hora de geração
- Número da página (x/x)
- Aviso LGPD obrigatório

## 🐛 Troubleshooting

### Erro de Conexão com Banco
```
Verifique:
1. Servidor SQL está rodando
2. Nome do servidor está correto no CSLogin.xml
3. Usuário tem permissões adequadas
4. ODBC Driver 17 está instalado
```

### Erro ao Gerar PDF
```
pip install --upgrade reportlab
```

### Erro com OpenAI
```
pip install --upgrade openai
Verifique se a chave da API está válida
```

### Erro com Gráficos
```
pip install --upgrade matplotlib
```

### Logs e proteção por senha

O aplicativo grava um arquivo de log para cada sessão na pasta `Logs/` com o nome no formato:
`log_<NomeUsuario>_YYYYMMDD_HHMMSS.zip`.

- Se o pacote `pyminizip` estiver instalado, o log será empacotado em um ZIP protegido por senha (senha padrão: `PWDCEOSOFTWARE`).
- No Windows, a instalação de `pyminizip` pode precisar do compilador C (Microsoft Visual C++ Build Tools). Se o pip falhar com uma mensagem informando "Microsoft Visual C++ 14.0 or greater is required", instale os Build Tools e tente novamente.

Se `pyminizip` não estiver disponível, o aplicativo criará automaticamente um ZIP sem senha como fallback e escreverá uma nota no próprio arquivo de log informando que a proteção por senha não foi aplicada.

Comandos úteis:

```powershell
# Tentar instalar o pyminizip (pode exigir Build Tools no Windows)
pip install pyminizip

# Se pip reclamar sobre o compilador no Windows, instale os Build Tools:
# https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

## 📄 Licença

© 2025 CEO Software. Todos os direitos reservados.

Este é um software proprietário. O uso, cópia, modificação e distribuição são permitidos apenas com autorização expressa da CEO Software.

## 👥 Suporte

Para suporte técnico, entre em contato:
- Email: suporte@ceosoftware.com.br
- Telefone: (xx) xxxx-xxxx

## 🔄 Changelog

### v25.01.15 rev.1 (15/01/2025)
- Versão inicial
- Construtor visual de consultas
- Geração de gráficos
- Integração com OpenAI
- Exportação de PDF
- Exportação de VIEW para Power BI
- Sistema de segurança e validação

---

**CSData Studio** - Transforme dados em decisões 🚀