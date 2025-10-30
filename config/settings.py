# /backend/config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

# --- Configurações da API da Binance ---
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
USAR_TESTNET = os.getenv("USAR_TESTNET", "False").lower() in ('true', '1', 't')

# --- CoinMarketCap API (CORREÇÃO) ---
COINMARKETCAP_API_KEY = os.getenv("COINMARKETCAP_API_KEY")

# --- IA (Opcional) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4-turbo-preview"
PROMPT_ANALISTA_SISTEMA = "Você é um analista financeiro de criptoativos."
OPENAI_RESPONSE_FORMAT = {"type": "json_object"}
OPENAI_TEMPERATURE = 0.3


# --- Modo de Operação ---
MODO_ANALISE = True  # Se True, o bot apenas analisa e não executa trades.

# --- Configurações de Operação ---
INTERVALO_TEMPO = '1m'
QUANTIDADE_POR_OPERACAO = 11.0 # USDT

# (Resto das suas configurações...)
PERIODO_RSI = 14
PERIODO_EMA_9 = 9
PERIODO_EMA_21 = 21
PERIODO_EMA_50 = 50
PERIODO_EMA_200 = 200
PERIODO_VWAP = 14
PERIODO_MEDIA_VOLUME = 20
VWAP_STD_MULT = 2.0
LIMITE_RSI_SOBREVENDA = 30
LIMITE_RSI_SOBRECOMPRA = 70
FATOR_VOLUME_CONFIRMACAO = 1.5
FATOR_TAKE_PROFIT = 1.05 
PERCENTUAL_STOP_LOSS = 0.02

if not API_KEY or not API_SECRET:
    raise ValueError("As variáveis de ambiente BINANCE_API_KEY e BINANCE_API_SECRET não foram definidas.")
