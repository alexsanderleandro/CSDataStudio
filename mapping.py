"""
Arquivo de mapeamento de nomes de campos para labels amigáveis (genérico por coluna).

Este arquivo define `FIELD_LABEL_OVERRIDES` como um dicionário simples onde
as chaves são nomes técnicos de coluna (sem schema/table, em lower-case)
e os valores são os rótulos que devem ser exibidos ao usuário.

Vantagem: o mapeamento é aplicado a qualquer módulo — se um novo módulo
contiver um campo `CodProduto`, a entrada `codproduto` aqui será aplicada.
"""

FIELD_LABEL_OVERRIDES = {
    'numero': 'Número',
    'datamovimento': 'Data Movimento',
    'codcliente': 'Código Cliente',
    'nomeempresa': 'Empresa',
    'codvendedor': 'Código Vendedor',
    'nomevendedor': 'Vendedor',
    'descricaoproduto': 'Produto',
    'codproduto': 'Código Produto',
    'precounitario': 'Preço Unitário',
    'quantidade': 'Quantidade',
    'totalproduto': 'Total Produto',
    'totaldesconto': 'Total Desconto',
    'codgrupo': 'Código Grupo',
    'nomegrupo': 'Nome Grupo',
    'cidade': 'Cidade',
    'estado': 'Estado',
    'tiporegistro': 'Tipo Registro',
    'tipoorigem': 'Tipo Origem',
    'serieorigem': 'Série Origem',
    'codempresa': 'Código Empresa',
    'numregistro': 'Num Registro',
    'codfiscal': 'Código Fiscal',
    'pesoliquido': 'Peso Líquido',
    'pesobruto': 'Peso Bruto',
    'totalprodutosemst': 'Total Produto Sem ST',
    'valorfcp_substituicao': 'Valor FCP Substituição',
    'codregiao': 'Código Região',
    'razaosocial': 'Razão Social',
    'codgrupoempresa': 'Código Grupo Empresa',
    'codtipoproduto': 'Código Tipo Produto',
    'nometipoproduto': 'Nome Tipo Produto',
    'localizacao': 'Localização',
    'codcondicao': 'Código Condição',
    'numpedido': 'Número Pedido',
    'transmitidasn': 'Transmitida (S/N)',
    'codmotivodevolucao': 'Código Motivo Devolução',
    'nomemotivodevolucao': 'Motivo Devolução',
    'tipodocumento': 'Tipo Documento',
    'codtipovendedor': 'Código Tipo Vendedor',
    'codvendedorresp': 'Vendedor Responsável',
    'quantidadebase': 'Quantidade Base',
    'custaatual': 'Custo Atual',
    'customedio': 'Custo Médio',
    'customediocontabil': 'Custo Médio Contábil',
    'custocontabil': 'Custo Contábil',
    'custoreposicao': 'Custo Reposição',
    'custodashboard': 'Custo Dashboard',
    'percmarkupnf': 'Perc Markup NF',
    'percmarkup': 'Perc Markup',
    'tipodevolucao': 'Tipo Devolução',
    'unidade': 'Unidade',
    'numdecimais': 'Número Decimais',
    'pesovariavel': 'Peso Variável',
    'percentualreducao': 'Percentual Redução',
    'ordemitem': 'Ordem Item'
}


def get_field_label(module: str | None, field_name: str | None) -> str | None:
    """Retorna um label amigável para o nome da coluna (lookup genérico).

    A API mantém o parâmetro `module` por compatibilidade, mas o mapeamento
    é aplicado independentemente do módulo: apenas a parte final do nome da
    coluna é normalizada e usada como chave (case-insensitive).
    """
    try:
        if not field_name:
            return None
        import re
        parts = re.split(r"\.|\[|\]", str(field_name))
        parts = [p for p in parts if p]
        col = parts[-1].lower() if parts else str(field_name).lower()
        return FIELD_LABEL_OVERRIDES.get(col)
    except Exception:
        return None
