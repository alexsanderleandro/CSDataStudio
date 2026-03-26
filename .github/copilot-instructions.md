## Objetivo rápido
Fornecer contexto essencial para agentes de IA contribuírem com correções e features no repositório CSDataStudio.

Mantenha as edições pequenas e focadas: priorize correções de lógica, testes e documentação em vez de alterações amplas na UI ou reescritas de arquitetura.

## Visão geral do projeto
- Aplicação desktop em Python com UI em PyQt5 (entrada: `main.py`).
- Componentes principais:
  - `main.py` — UI principal e dialogs (LoginDialog, QueryBuilderTab, etc.).
  - `authentication.py` — funções de autenticação e `get_db_connection`.
  - `config_manager.py` — leitura/escrita de `C:\\CEOSoftware\\CSLogin.xml` e múltiplas configs.
  - `consulta_sql.py` — construtor de queries e lógica de relacionamento/joins (QueryBuilder).
  - `valida_sql.py` — regras de segurança SQL: aceita apenas SELECT, exige WHERE, bloqueia statements múltiplos e comandos administrativos.
  - `ai_insights.py` — integração com OpenAI (chave configurada via menu da aplicação).
  - `chart_generator.py` / `report_generator.py` — criação de gráficos (matplotlib) e PDFs (reportlab).
  - `saved_queries.py` — persistência de consultas salvas.

## Fluxo de dados essencial
1. Usuário faz login (LoginDialog) → `verify_user` em `authentication.py`.
2. Usuário constrói query na aba Query Builder (`consulta_sql.QueryBuilder` / `QueryBuilderTab` em `main.py`).
3. SQL gerado é validado por `valida_sql.validar_sql[_for_save]` antes de executar ou salvar.
4. Execução usa `get_db_connection` (pyodbc / ODBC Driver 17+). Resultados alimentam `chart_generator` e `report_generator`.
5. Consultas salvas via `QueryManager` (arquivo local / APPDATA). Logs em `Logs/`.

## Convenções e padrões do repositório
- Plataforma alvo: Windows (paths absolutos como `C:\\CEOSoftware` são usados em vários scripts). Preserve-os em mudanças que afetem setup/instalação.
- Segurança SQL: o projeto emprega validações estritas. Nunca contorne `valida_sql.py` — adicione regras explícitas se necessário.
- Mapeamentos de rótulos amigáveis: `mapping.py` pode ser sobrescrito para personalizar labels (import opcional no `main.py`).
- Preferência por mudanças não intrusivas na UI: se uma correção exigir alteração visual, proponha alternativa mínima e documente o impacto.

## Comandos e workflows dev/test
- Instalação e setup rápido (Windows PowerShell):
  - Criar venv e instalar: `python -m venv .venv ; .\\.venv\\Scripts\\Activate.ps1 ; pip install -r requirements.txt`
  - Executar setup interativo: `python setup.py` (cria `C:\\CEOSoftware\\CSLogin.xml`, pastas em `%APPDATA%` e testa ODBC).
  - Executar app: `python main.py`.
- Testes unitários (unittest): `python -m unittest discover -v` ou para a pasta `tests`: `python -m unittest discover -v tests`.

## Integrações e dependências importantes
- Banco: SQL Server via `pyodbc`. Requer ODBC Driver 17/18 no host.
- IA: `openai` (configurada via menu; chave não é persistida em repositório).
- Geração de PDFs: `reportlab`; logs podem ser compactados com `pyminizip` (opcional — fallback sem senha se ausente).

## Padrões de contribuição do agente (diretrizes práticas)
- Entregas pequenas: cada PR/patch de agente deve ter no máximo 1-2 arquivos alterados, com testes novos/atualizados quando aplicável.
- Testes: prefira adicionar testes em `tests/` usando `unittest` (modelo já presente). Para mudanças em validação SQL, inclua casos que cubram regras negativas (bloqueio de INSERT/DELETE, múltiplas statements, ausência de WHERE).
- Preservar strings de interface e caminhos Windows: traduções ou mudanças de strings na UI devem ser evitadas a menos que sejam correções de bug.
- Evitar commit de segredos: não inclua chaves OpenAI, credenciais ou `CSLogin.xml` reais no repositório.

## Exemplos rápidos (onde procurar)
- Para entender a validação SQL: abra `valida_sql.py` e veja como `validar_sql` e `validar_sql_for_save` são usados em `main.py`.
- Para fluxo de login/conexão: leia `LoginDialog` em `main.py` e `authentication.py` (`get_db_connection`, `verify_user`).
- Para salvar/recuperar consultas: `saved_queries.py` e `QueryManager`.

## Restrições legais / licenciamento
- Software proprietário (ver `README.md`). Não adicionar dependências que contravenham licença comercial sem autorização.

---
Se quiser, posso ajustar este arquivo com exemplos de comandos de debug adicionais (ex.: como simular conexões sem SQL Server) ou adicionar snippets de teste para `valida_sql.py` — diga qual prefere.
