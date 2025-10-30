# /estrategia/logica_sinal.py

import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timezone

from config import settings
from utils.logger import log

# --- Caminho para a pasta de dados ---
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def salvar_indicadores_tecnicos(par: str, indicadores: dict):
    """
    Salva os indicadores técnicos calculados para um ativo em um arquivo JSON.
    """
    # Garante que o diretório de dados exista
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_path = DATA_DIR / "indicadores_tecnicos.json"
    now_utc = datetime.now(timezone.utc)

    output_data = {
        "metadata": {
            "ultima_atualizacao_em": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "par_ativo": par
        },
        "indicadores": indicadores
    }

    try:
        # Substitui valores NaN por None para compatibilidade com JSON
        for key, value in indicadores.items():
            if pd.isna(value):
                indicadores[key] = None

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        log.info(f"Indicadores técnicos para {par} salvos com sucesso em '{file_path}'.")
    except IOError as e:
        log.error(f"Não foi possível salvar os indicadores no arquivo '{file_path}': {e}")


class Estrategia:
    """
    Encapsula a lógica para calcular indicadores técnicos a partir de dados de mercado.
    """
    def __init__(self):
        self.params = {
            "rsi_period": settings.PERIODO_RSI,
            "vwap_period": settings.PERIODO_VWAP,
            "volume_period": settings.PERIODO_MEDIA_VOLUME,
            "vwap_std_mult": settings.VWAP_STD_MULT,
            "ema_period_9": settings.PERIODO_EMA_9,
            "ema_period_21": settings.PERIODO_EMA_21,
            "ema_period_50": settings.PERIODO_EMA_50,
            "ema_period_200": settings.PERIODO_EMA_200,
        }
        log.info("Módulo de cálculo de indicadores técnicos inicializado.")

    def _calcular_indicadores(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return df
        try:
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            df.dropna(subset=['open', 'high', 'low', 'close', 'volume'], inplace=True)
            if df.empty: return df

            df['ema_9'] = df['close'].ewm(span=self.params["ema_period_9"], adjust=False).mean()
            df['ema_21'] = df['close'].ewm(span=self.params["ema_period_21"], adjust=False).mean()
            df['ema_50'] = df['close'].ewm(span=self.params["ema_period_50"], adjust=False).mean()
            df['ema_200'] = df['close'].ewm(span=self.params["ema_period_200"], adjust=False).mean()

            delta: pd.Series = df['close'].diff().astype(float)
            gain = delta.where(delta > 0, 0).rolling(window=self.params["rsi_period"]).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.params["rsi_period"]).mean()
            rs = gain / loss.replace(0, 1e-10)
            df['rsi'] = 100 - (100 / (1 + rs))

            typical_price = (df['high'] + df['low'] + df['close']) / 3
            tp_volume = typical_price * df['volume']
            cumulative_tp_volume = tp_volume.rolling(window=self.params["vwap_period"]).sum()
            cumulative_volume = df['volume'].rolling(window=self.params["vwap_period"]).sum()
            df['vwap'] = cumulative_tp_volume / cumulative_volume.replace(0, 1e-10)
            df['volume_sma'] = df['volume'].rolling(window=self.params["volume_period"]).mean()
            df['vwap_std'] = df['close'].rolling(window=self.params["vwap_period"]).std()
            df['vwap_upper'] = df['vwap'] + (df['vwap_std'] * self.params["vwap_std_mult"])
            df['vwap_lower'] = df['vwap'] - (df['vwap_std'] * self.params["vwap_std_mult"])

        except Exception as e:
            log.error(f"Erro ao calcular indicadores: {e}", exc_info=True)
        return df

    def processar_e_salvar_indicadores(self, df_klines: pd.DataFrame, par_ativo: str) -> dict | None:
        """
        Método principal que calcula os indicadores e salva o resultado mais recente.
        """
        maior_periodo = max(list(self.params.values()))
        if len(df_klines) < maior_periodo:
            log.warning(f"Dados insuficientes para {par_ativo}. Necessário: {maior_periodo}, disponível: {len(df_klines)}.")
            return None

        df_indicadores = self._calcular_indicadores(df_klines.copy())
        
        # Pega a última linha com os indicadores mais recentes
        if df_indicadores.empty:
            log.warning(f"DataFrame de indicadores vazio para {par_ativo} após os cálculos.")
            return None

        ultimo_registro = df_indicadores.iloc[-1]
        
        # Converte a série de dados para um dicionário e arredonda os valores
        indicadores = ultimo_registro.round(6).to_dict()

        # Salva os indicadores no arquivo JSON
        salvar_indicadores_tecnicos(par=par_ativo, indicadores=indicadores)

        return indicadores
