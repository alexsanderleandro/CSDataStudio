import json
import sys
p = r"c:\Users\alex\Documents\Python\CSDataStudio\metadados"
try:
    v = json.load(open(p + "\\vendas.json", "r", encoding="utf-8"))
    a = json.load(open(p + "\\vendas_agrupamentos.json", "r", encoding="utf-8"))
    rels = v["tabelas"]["VendasRefPeriodo"].get("relacionamentos", [])
    print("relacionamentos encontrados =", len(rels))
    print("agrupamentos =", len(a.get("agrupamentos", [])))
    campos = v["tabelas"]["VendasRefPeriodo"]["campos"]
    print("campos padrao =", len(campos.get("padrao", [])), "avancado =", len(campos.get("avancado", [])))
    sys.exit(0)
except Exception as e:
    print('ERRO ao validar metadados:', e)
    sys.exit(1)
