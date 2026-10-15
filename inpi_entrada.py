"""
Primeira camada: verifica as entradas antes de qualquer consulta ao INPI.

Cada entrada mantém sua linha de origem. Entradas inválidas ou repetidas não são consultadas,
mas continuam na planilha de saída, na mesma posição, com o motivo registrado ao lado.
"""

TAMANHO_PROCESSO = 9          # números de processo de marca do INPI têm 9 dígitos
SEPARADORES = " .-/"          # formatação comum em planilhas (ex.: 932.062.393), removida antes da checagem


def _como_texto(valor):
    """Converte o valor lido (texto colado ou célula do Excel) em texto, sem o '.0' de números do Excel."""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def preparar_entradas(valores_por_linha):
    """
    Recebe pares (linha, valor) na ordem da entrada e devolve uma lista de dicionários:
        linha, entrada (texto original), numero_processo, consultar (bool), observacao, tipo
    tipo: "ok", "invalido" ou "repetido".
    """
    primeira_linha = {}
    saida = []
    for linha, valor in valores_por_linha:
        entrada = _como_texto(valor)
        if not entrada:
            continue
        numero = "".join(ch for ch in entrada if ch not in SEPARADORES)
        item = {"linha": linha, "entrada": entrada, "numero_processo": numero,
                "consultar": False, "observacao": "", "tipo": "ok"}
        if not numero.isdigit():
            item.update(tipo="invalido", numero_processo="",
                        observacao="Erro de preenchimento: contém caracteres não numéricos.")
        elif len(numero) != TAMANHO_PROCESSO:
            item.update(tipo="invalido",
                        observacao=f"Erro de preenchimento: {len(numero)} dígitos (o número de processo tem {TAMANHO_PROCESSO}).")
        elif numero in primeira_linha:
            item.update(tipo="repetido",
                        observacao=f"Repetido: já consultado na linha {primeira_linha[numero]}.")
        else:
            primeira_linha[numero] = linha
            item["consultar"] = True
        saida.append(item)
    return saida


def resumo_entradas(itens):
    """Contagem por tipo, para a mensagem antes da consulta."""
    return {
        "total": len(itens),
        "consultar": sum(i["consultar"] for i in itens),
        "repetidos": sum(i["tipo"] == "repetido" for i in itens),
        "invalidos": sum(i["tipo"] == "invalido" for i in itens),
    }
