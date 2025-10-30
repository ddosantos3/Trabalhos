# -*- coding: utf-8 -*-

"""
Analisador de Mercado de Criptoativos com a API CoinMarketCap.

Este script agora opera em um ciclo de atualização:
1. Lê a lista de ativos do seu próprio arquivo de saída ('ativos_sentimentos.json').
2. Conecta-se à API do CoinMarketCap para ATUALIZAR os dados de mercado.
3. Salva o resultado completo, com um novo cabeçalho de metadados,
   sobrescrevendo o arquivo 'ativos_sentimentos.json'.

O "sentimento" é interpretado a partir da variação de preço nas últimas 24h.

Pré-requisitos:
1. Python 3.6+
2. Bibliotecas 'requests', 'python-dotenv' instaladas
   (`pip install requests python-dotenv`)
3. Um arquivo .env na mesma pasta do script contendo a chave da API:
   COINMARKETCAP_API_KEY="SUA_CHAVE_AQUI"
4. Um arquivo 'ativos_sentimentos.json' pré-existente na mesma pasta.
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from typing import Optional, List, Dict
from pathlib import Path

# --- FUNÇÃO HELPER PARA ENCONTRAR O DIRETÓRIO CORRETO ---
def get_project_backend_dir() -> Path:
    """Encontra o diretório 'backend' do projeto de forma robusta."""
    # Começa do diretório do script atual e sobe na árvore de pastas
    current_path = Path(__file__).resolve()
    while current_path.parent != current_path: # Evita loop infinito na raiz
        if (current_path / 'backend').is_dir():
            return current_path / 'backend'
        current_path = current_path.parent
    raise FileNotFoundError("Não foi possível localizar a pasta 'backend' do projeto.")

BACKEND_DIR = get_project_backend_dir()
DATA_DIR = BACKEND_DIR / "data"

class CoinMarketCapAPI:
    """
    Classe para interagir com a API v2 do CoinMarketCap.
    """
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("A chave da API do CoinMarketCap é obrigatória.")
        
        self.api_key = api_key
        self.base_url = "https://pro-api.coinmarketcap.com"
        self.headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': self.api_key,
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_asset_data(self, symbol: str) -> dict:
        endpoint = "/v2/cryptocurrency/quotes/latest"
        url = self.base_url + endpoint
        params = {"symbol": symbol.upper()}
        
        print(f"INFO: Consultando dados para o ativo: {symbol.upper()}...", file=sys.stderr)
        
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
            return {"error": "Erro HTTP ao acessar a API.", "status_code": http_err.response.status_code, "message": str(http_err)}
        except Exception as e:
            return {"error": "Erro inesperado na conexão.", "message": str(e)}

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

def load_assets() -> List[Dict]:
    """
    Carrega a lista de ativos do arquivo 'ativos.json' original,
    que serve como fonte primária para este script.
    """
    # Para este script inicial, a fonte é o 'ativos.json'
    source_file = DATA_DIR / "ativos.json"
    
    try:
        print(f"INFO: Carregando lista de ativos de '{source_file}'...", file=sys.stderr)
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                print(f"ERRO: Formato de dados inesperado em '{source_file}'. Esperado uma lista.", file=sys.stderr)
                sys.exit(1)

    except FileNotFoundError:
        print(f"ERRO: O arquivo de origem '{source_file}' não foi encontrado.", file=sys.stderr)
        print("Certifique-se de que o arquivo 'ativos.json' existe na pasta 'backend/data/'.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"ERRO: O arquivo '{source_file}' não é um JSON válido.", file=sys.stderr)
        sys.exit(1)

def save_results_to_json(data: List[Dict]):
    """
    Salva os resultados no arquivo 'ativos_sentimentos.json' dentro da pasta 'data'.
    """
    # Garante que o diretório de dados exista
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_path = DATA_DIR / "ativos_sentimentos.json"
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
        print(f"\nSUCESSO: Os resultados foram salvos com sucesso em '{file_path}'.", file=sys.stderr)
    except IOError as e:
        print(f"\nERRO: Não foi possível salvar os resultados no arquivo '{file_path}'. Detalhes: {e}", file=sys.stderr)

def main():
    """
    Função principal para executar o script.
    """
    # Carrega o .env a partir da pasta 'backend'
    dotenv_path = BACKEND_DIR / '.env'
    load_dotenv(dotenv_path=dotenv_path)
    
    api_key = os.getenv("COINMARKETCAP_API_KEY")
    if not api_key:
        print("ERRO: A variável 'COINMARKETCAP_API_KEY' não foi encontrada.", file=sys.stderr)
        print(f"Certifique-se de que o arquivo .env em '{BACKEND_DIR}' existe e contém a chave.", file=sys.stderr)
        sys.exit(1)

    client = CoinMarketCapAPI(api_key=api_key)

    ativos_para_analise = load_assets()
    if not ativos_para_analise:
        print("ERRO: Nenhum ativo para analisar foi encontrado.", file=sys.stderr)
        sys.exit(1)
        
    resultados_finais = []
    
    for ativo in ativos_para_analise:
        symbol = ativo.get("codigo")
        if not symbol:
            print(f"AVISO: Ativo sem 'codigo' encontrado e será ignorado: {ativo}", file=sys.stderr)
            continue
        
        market_data = client.get_asset_data(symbol=symbol)
        resultado_combinado = {**ativo, "analise_mercado": market_data}
        resultados_finais.append(resultado_combinado)
        
        time.sleep(1.1) 

    save_results_to_json(resultados_finais)

if __name__ == "__main__":
    main()

