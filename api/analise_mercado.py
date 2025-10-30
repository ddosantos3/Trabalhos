# backend/api/analise_mercado.py
### MOVIDO E REATORADO ###

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional, List, Dict

# Importando configurações centralizadas e o logger
from config import settings
from utils.logger import log

class AnalisadorMercadoCMC:
    """
    Classe para interagir com a API v2 do CoinMarketCap.
    Refatorada para ser um módulo de serviço dentro do agente.
    """
    def __init__(self):
        # --- CORREÇÃO APLICADA AQUI ---
        # Usamos getattr para uma verificação mais segura, evitando AttributeError
        api_key = getattr(settings, "COINMARKETCAP_API_KEY", None)
        if not api_key:
            log.critical("A chave da API do CoinMarketCap não foi encontrada nas configurações (config/settings.py).")
            raise ValueError("COINMARKETCAP_API_KEY não configurada.")
        
        self.base_url = "https://pro-api.coinmarketcap.com"
        self.headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': api_key,
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        log.info("Analisador de Mercado (CoinMarketCap) inicializado.")

    def get_asset_data(self, symbol: str) -> dict:
        """Busca os dados de mercado para um ativo específico."""
        endpoint = "/v2/cryptocurrency/quotes/latest"
        url = self.base_url + endpoint
        params = {"symbol": symbol.upper()}
        
        log.info(f"Consultando dados de mercado para o ativo: {symbol.upper()}...")
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if 'data' in data and symbol.upper() in data['data']:
                asset_list = data['data'][symbol.upper()]
                if asset_list:
                    return self._format_output(asset_list[0])
                else:
                    return {"error": f"O símbolo '{symbol.upper()}' foi consultado, mas a API não retornou dados."}
            else:
                return {"error": "Ativo não encontrado na resposta da API.", "raw_response": data}
        except requests.exceptions.HTTPError as http_err:
            log.error(f"Erro HTTP ao acessar a API do CMC para {symbol}: {http_err}")
            return {"error": "Erro HTTP.", "status_code": http_err.response.status_code}
        except Exception as e:
            log.error(f"Erro inesperado na API do CMC para {symbol}: {e}", exc_info=True)
            return {"error": "Erro inesperado na conexão."}

    def _format_output(self, data: dict) -> dict:
        quote_data = data.get('quote', {}).get('USD', {})
        return {
            "asset_info": {
                "symbol": data.get("symbol"), "name": data.get("name"),
                "circulating_supply": data.get("circulating_supply"),
                "total_supply": data.get("total_supply"), "max_supply": data.get("max_supply"),
            },
            "market_metrics": {
                "price_usd": quote_data.get("price"), "volume_24h": quote_data.get("volume_24h"),
                "market_cap": quote_data.get("market_cap"),
                "fully_diluted_market_cap": quote_data.get("fully_diluted_market_cap"),
            },
            "market_sentiment": {
                "percent_change_1h": quote_data.get("percent_change_1h"),
                "percent_change_24h": quote_data.get("percent_change_24h"),
                "percent_change_7d": quote_data.get("percent_change_7d"),
                "descricao_sentimento_24h": self._interpret_sentiment_from_change(quote_data.get("percent_change_24h"))
            },
            "fonte_dados": "CoinMarketCap API v2"
        }
        
    def _interpret_sentiment_from_change(self, change: Optional[float]) -> str:
        if change is None: return "Indefinido"
        if change > 5: return "Forte Sentimento de Alta (Bullish)"
        elif change > 1: return "Sentimento de Alta (Bullish)"
        elif change > -1: return "Sentimento Neutro"
        elif change > -5: return "Sentimento de Baixa (Bearish)"
        else: return "Forte Sentimento de Baixa (Bearish)"

def _get_data_filepath() -> str:
    """Retorna o caminho absoluto para o arquivo de dados na pasta /data."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, '..', 'data', 'ativos_sentimentos.json')

def load_assets_from_file() -> List[Dict]:
    """Carrega a lista de ativos do arquivo de sentimentos."""
    source_file = _get_data_filepath()
    try:
        log.info(f"Carregando lista de ativos de '{source_file}'...")
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get("ativos", [])
            elif isinstance(data, list):
                log.warning(f"Arquivo '{source_file}' está em formato antigo. Será atualizado.")
                return data
            else:
                log.error(f"Formato de dados inesperado em '{source_file}'.")
                return []
    except FileNotFoundError:
        log.error(f"ERRO CRÍTICO: O arquivo de origem '{source_file}' não foi encontrado.")
        return []
    except json.JSONDecodeError:
        log.error(f"ERRO CRÍTICO: O arquivo '{source_file}' não é um JSON válido.")
        return []

def save_results_to_json(data: List[Dict]):
    """Salva os resultados no arquivo JSON com metadados."""
    file_path = _get_data_filepath()
    now_utc = datetime.now(timezone.utc)
    output_data = {
        "metadata": {
            "data_atualizacao": now_utc.strftime("%Y-%m-%d"),
            "hora_atualizacao": now_utc.strftime("%H:%M:%S UTC"),
            "conteudo": "Análise detalhada dos ativos, incluindo métricas de mercado e sentimento.",
            "formato": "JSON"
        },
        "ativos": data
    }
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        log.info(f"Resultados de análise de mercado salvos com sucesso em '{file_path}'.")
    except IOError as e:
        log.error(f"Não foi possível salvar os resultados no arquivo '{file_path}': {e}")

def executar_analise_e_salvar():
    """Função orquestradora para ser chamada pelo FastAPI."""
    log.info("="*50)
    log.info("INICIANDO ROTINA DE ATUALIZAÇÃO DE ANÁLISE DE MERCADO")
    log.info("="*50)
    
    client = AnalisadorMercadoCMC()
    ativos_para_analise = load_assets_from_file()
    
    if not ativos_para_analise:
        log.error("Nenhum ativo para analisar foi encontrado. Rotina encerrada.")
        return

    resultados_finais = []
    for ativo in ativos_para_analise:
        ativo_base = {k: v for k, v in ativo.items() if k != 'analise_mercado'}
        symbol = ativo_base.get("codigo")
        if not symbol:
            log.warning(f"Ativo sem 'codigo' encontrado e será ignorado: {ativo}")
            continue
        
        market_data = client.get_asset_data(symbol=symbol)
        resultado_combinado = {**ativo_base, "analise_mercado": market_data}
        resultados_finais.append(resultado_combinado)
        time.sleep(1.1)  # Pausa para respeitar os limites da API

    save_results_to_json(resultados_finais)
    log.info("="*50)
    log.info("ROTINA DE ATUALIZAÇÃO DE ANÁLISE DE MERCADO CONCLUÍDA")
    log.info("="*50)
