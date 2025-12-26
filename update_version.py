from datetime import datetime
import re
import os

VERSION_FILE = "version.py"

def gerar_versao():
    hoje = datetime.now().strftime("%y.%m.%d")
    rev = 1

    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            conteudo = f.read()

        match = re.search(r'(\d{2}\.\d{2}\.\d{2}) rev\. (\d+)', conteudo)
        if match:
            data_antiga, rev_antigo = match.groups()

            if data_antiga == hoje:
                rev = int(rev_antigo) + 1
            else:
                rev = 1

    versao = f'{hoje} rev. {rev}'

    # Se o arquivo existir, substitui apenas a linha VERSION = "..."
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            conteudo = f.read()

        # Substituição segura: captura três grupos (pré, valor atual, pós) e usa uma função
        pattern = re.compile(r'^(VERSION\s*=\s*")([^"]*)("\s*$)', flags=re.MULTILINE)

        def _repl(m):
            return m.group(1) + versao + m.group(3)

        if pattern.search(conteudo):
            novo = pattern.sub(_repl, conteudo)
            with open(VERSION_FILE, "w", encoding="utf-8") as f:
                f.write(novo)
        else:
            # não encontrou a linha VERSION: prefixa o arquivo com a declaração
            with open(VERSION_FILE, "w", encoding="utf-8") as f:
                f.write(f'VERSION = "{versao}"\n' + conteudo)
    else:
        # Arquivo não existe: cria com apenas a linha VERSION
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(f'VERSION = "{versao}"\n')

    print(f"Versão atualizada para: {versao}")

if __name__ == "__main__":
    gerar_versao()
