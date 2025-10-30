# /backend/estrategia/analista.py
import os
import json
import re
from openai import OpenAI
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from config import settings
from utils.logger import log


# --- Caminho para a pasta de dados ---
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def salvar_analise_ia(par: str, analise: dict) -> None:
    """
    Formata e salva a análise da IA em um arquivo JSON.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_path = DATA_DIR / f"analise_ia_{par.lower()}.json"
    now_utc = datetime.now(timezone.utc)

    output_data = {
        "metadata": {
            "ultima_analise_em": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "par_ativo": par,
            "modelo_ia": settings.OPENAI_MODEL
        },
        "analise": analise
    }

    # --- CORREÇÃO: Tenta buscar por 'acao' ou 'recomendacao' ---
    acao = analise.get('acao') or analise.get('recomendacao', 'N/A')
    confianca = analise.get('confianca', 'N/A')
    justificativa = analise.get('justificativa', 'Sem detalhes.')

    texto_formatado = (
        f"## Análise Preditiva para {par} ({now_utc.strftime('%d/%m/%Y %H:%M')})\n\n"
        f"**Ação Recomendada:** {acao} "
        f"(Confiança: {confianca})\n\n"
        "**Justificativa da IA:**\n"
        f"> {justificativa}\n"
    )

    output_data["texto_formatado_dashboard"] = texto_formatado

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        log.info(f"Análise da IA para {par} salva com sucesso em '{file_path}'.")
    except IOError as e:
        log.error(f"Não foi possível salvar a análise da IA para {par}: {e}")


class AnalistaFinanceiro:
    """
    Classe que utiliza um LLM (modelo de linguagem) para analisar dados técnicos
    e de sentimento de mercado, fornecendo uma recomendação de trading.
    """

    def __init__(self) -> None:
        try:
            if not settings.OPENAI_API_KEY:
                raise ValueError("A variável de ambiente OPENAI_API_KEY não foi definida.")
            
            self.cliente = OpenAI(api_key=settings.OPENAI_API_KEY)
            log.info(f"Analista Financeiro (IA) inicializado com o modelo: {settings.OPENAI_MODEL}")
        except Exception as e:
            log.critical(f"Falha ao inicializar o Analista Financeiro: {e}", exc_info=True)
            self.cliente = None

    def obter_analise(self, dados_tecnicos: Dict[str, Any], info_ativo: Dict[str, Any]) -> Dict[str, Any]:
        if not self.cliente:
            return self._gerar_resposta_fallback("Cliente OpenAI indisponível.")

        prompt_usuario = self._construir_prompt_usuario(dados_tecnicos, info_ativo)

        try:
            log.info(f"Enviando dados do par {info_ativo.get('par', 'N/A')} para análise completa...")

            resposta = self.cliente.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": settings.PROMPT_ANALISTA_SISTEMA},
                    {"role": "user", "content": prompt_usuario}
                ],
                response_format={"type": "json_object"},
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=2048,
            )

            conteudo_resposta = resposta.choices[0].message.content
            if not conteudo_resposta:
                raise ValueError("A resposta do LLM estava vazia.")
            
            try:
                start_index = conteudo_resposta.find('{')
                end_index = conteudo_resposta.rfind('}')
                if start_index != -1 and end_index != -1 and end_index > start_index:
                    json_str = conteudo_resposta[start_index:end_index+1]
                    analise_json = json.loads(json_str)
                else:
                    raise ValueError("Nenhum objeto JSON válido encontrado na resposta.")
            except (json.JSONDecodeError, ValueError) as e:
                log.error(f"Falha ao decodificar o JSON da resposta da IA. Erro: {e}")
                log.debug(f"Resposta recebida da IA:\n---\n{conteudo_resposta}\n---")
                raise

            salvar_analise_ia(par=info_ativo.get("par", "desconhecido"), analise=analise_json)

            acao_log = analise_json.get('acao') or analise_json.get('recomendacao', 'N/A')
            confianca_log = analise_json.get('confianca', 'N/A')

            log.info(
                f"Análise da IA concluída para {info_ativo.get('par')}: "
                f"Ação={acao_log}, Confiança={confianca_log}"
            )

            return analise_json

        except Exception as e:
            log.error(f"Erro ao obter análise da IA: {e}", exc_info=True)
            return self._gerar_resposta_fallback(str(e))
    
    # =================================================================================
    # CORREÇÃO APLICADA AQUI
    # O prompt foi ajustado para instruir explicitamente o uso de 'acao' e 'confianca'.
    # =================================================================================
    def _construir_prompt_usuario(self, dados_tecnicos: Dict[str, Any], info_completa_ativo: Dict[str, Any]) -> str:
        dados_tecnicos_str = json.dumps(dados_tecnicos, indent=2, ensure_ascii=False)
        analise_mercado = info_completa_ativo.get("analise_mercado", {})
        analise_mercado_str = json.dumps(analise_mercado, indent=2, ensure_ascii=False)
        info_base_ativo = {k: v for k, v in info_completa_ativo.items() if k != "analise_mercado"}
        info_base_str = json.dumps(info_base_ativo, indent=2, ensure_ascii=False)

        return f"""
Por favor, analise os seguintes dados para o ativo descrito e forneça uma recomendação de trading.

## Informações do Ativo
```json
{info_base_str}
```

## Análise de Mercado e Sentimento
```json
{analise_mercado_str}
```

## Dados Técnicos (Candlesticks)
```json
{dados_tecnicos_str}
```

Sua resposta DEVE ser um único objeto JSON contendo as seguintes chaves: 'acao' (com os valores "COMPRAR", "VENDER" ou "MANTER"), 'confianca' (um número de 0 a 1 representando a confiança na ação) e 'justificativa' (uma explicação detalhada). Não adicione nenhum texto ou explicação fora do objeto JSON.
"""

    def _gerar_resposta_fallback(self, erro: Optional[str] = None) -> Dict[str, Any]:
        log.warning(f"Gerando resposta fallback. Erro: {erro}")
        return {
            "acao": "indefinida",
            "confianca": 0,
            "justificativa": (
                "Não foi possível obter a análise automática neste momento. "
                "Verifique a conexão com a API ou tente novamente mais tarde."
            ),
            "erro": erro or "Falha desconhecida",
        }
