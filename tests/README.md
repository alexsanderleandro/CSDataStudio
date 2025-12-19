CSData Studio — testes
======================

Este diretório contém os testes unitários do projeto.

Rápido guia para executar os testes (Windows / PowerShell)
---------------------------------------------------------

1) Ative/prepare seu ambiente Python (recomendado: virtualenv/venv)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Executar todos os testes (descoberta automática)

```powershell
python -m unittest discover -v
```

3) Executar apenas os testes na pasta `tests/`

```powershell
python -m unittest discover -v tests
```

4) Executar um arquivo de testes específico

```powershell
python -m unittest tests.test_execute_flow -v
# ou
python -m unittest tests.test_csdatastudio -v
```

5) Executar um caso de teste específico (módulo.Classe.metodo)

```powershell
python -m unittest tests.test_execute_flow.TestExecuteFlow.test_execute_without_where_allowed -v
```

6) Usando pytest (opcional)

Se preferir usar pytest (mais recursos e output legível):

```powershell
pip install pytest
pytest -q
```

Notas e dicas
-------------
- Os testes que interagem com widgets PyQt5 (QApplication) criam uma instância de `QApplication` automaticamente.
  Em ambientes headless (ex.: alguns containers Linux) pode ser necessário usar um servidor virtual de display (Xvfb).
- Se algum teste acessar o banco de dados, verifique as configurações em `config_manager` ou use mocks nas dependências.
- Para executar os testes em CI, basta adicionar um passo que execute `python -m pip install -r requirements.txt` seguido de `python -m unittest discover -v`.

Se quiser, eu posso:
- adicionar um `tests/conftest.py` para fixtures comuns (caso migre para pytest);
- criar um workflow GitHub Actions simples para rodar os testes automaticamente em PRs.
