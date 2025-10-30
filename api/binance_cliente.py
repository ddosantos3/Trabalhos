# /api/binance_cliente.py

from binance.client import Client
from binance import ThreadedWebsocketManager
from binance.exceptions import BinanceAPIException
import pandas as pd
from config import settings
from utils.logger import log
import time
import math

class ClienteBinance:
    """
    Classe para encapsular todas as interações com a API da Binance.
    Agora com validações robustas de saldo e filtros (NOTIONAL / MIN_NOTIONAL).
    """
    def __init__(self):
        self.testnet = settings.USAR_TESTNET
        self.twm = None
        try:
            self.cliente = Client(
                api_key=settings.API_KEY,
                api_secret=settings.API_SECRET,
                tld='com',
                testnet=self.testnet
            )
            self.cliente.ping()
            log.info(f"Conexão com a API da Binance estabelecida com sucesso. Usando Testnet: {self.testnet}")
        except BinanceAPIException as e:
            log.error(f"Erro ao conectar com a API da Binance: {e}")
            raise
        except Exception as e:
            log.error(f"Um erro inesperado ocorreu na inicialização do ClienteBinance: {e}")
            raise

    # -------------------------
    # Histórico (sem alterações relevantes)
    # -------------------------
    def obter_klines_historicos(self, par: str, intervalo: str, limite: int) -> pd.DataFrame:
        """
        Busca dados históricos de klines, garantindo a correta formatação e tipos de dados.
        """
        try:
            log.info(f"Buscando {limite} klines históricos para {par} com intervalo {intervalo}...")
            klines = self.cliente.get_historical_klines(symbol=par, interval=intervalo, limit=limite)
            
            colunas = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 
                       'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 
                       'taker_buy_quote_asset_volume', 'ignore']
            
            df = pd.DataFrame(klines, columns=colunas)

            df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')

            # Força a conversão das colunas para o tipo numérico (float)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df.dropna(inplace=True) 
            df.set_index('open_time', inplace=True)
            df.sort_index(inplace=True)
            
            return df
        
        except Exception as e:
            log.error(f"Erro inesperado ao buscar klines históricos para {par}: {e}")
            return pd.DataFrame()

    # -------------------------
    # Saldo
    # -------------------------
    def obter_saldo_ativo(self, ativo: str) -> float:
        """
        Consulta a API para obter o saldo livre de um ativo específico.
        :param ativo: A sigla do ativo (ex: 'USDT', 'BTC').
        :return: O saldo livre como um float.
        """
        try:
            log.info(f"Verificando saldo para o ativo: {ativo}")
            saldo = self.cliente.get_asset_balance(asset=ativo)
            if saldo and 'free' in saldo:
                try:
                    valor = float(saldo['free'])
                except Exception:
                    valor = 0.0
                log.info(f"Saldo disponível para {ativo}: {valor:.8f}")
                return valor
            log.warning(f"Não foi possível obter o saldo para {ativo}. Retornando 0.")
            return 0.0
        except BinanceAPIException as e:
            log.error(f"Erro de API ao obter saldo para {ativo}: {e}")
            return 0.0
        except Exception as e:
            log.error(f"Erro inesperado ao obter saldo para {ativo}: {e}")
            return 0.0

    # -------------------------
    # Helpers relacionados a filtros do símbolo
    # -------------------------
    def _obter_info_simbolo(self, par: str) -> dict | None:
        try:
            info = self.cliente.get_symbol_info(par)
            if not info:
                log.warning(f"Informações do símbolo {par} não retornaram nada.")
                return None
            return info
        except BinanceAPIException as e:
            log.error(f"Erro de API ao obter info do símbolo {par}: {e}")
            return None
        except Exception as e:
            log.error(f"Erro inesperado ao obter info do símbolo {par}: {e}")
            return None

    def _obter_min_notional(self, info_simbolo: dict) -> float:
        """
        Retorna o minNotional (em quote asset, ex: USDT) do símbolo se existir.
        Suporta ambos: filterType 'MIN_NOTIONAL' ou 'NOTIONAL' (variações de API).
        """
        try:
            for f in info_simbolo.get('filters', []):
                if f.get('filterType') in ('MIN_NOTIONAL', 'NOTIONAL'):
                    # Alguns filtros usam 'minNotional', outros 'minNotional' como string
                    min_notional = f.get('minNotional') or f.get('minNotional', None)
                    if min_notional is None:
                        # Em alguns mercados a chave pode ser 'notional' ou 'minNotional' dentro do filtro
                        min_notional = f.get('minNotional') or f.get('minNotional')
                    if min_notional is None:
                        # tentativa por chaves alternativas
                        min_notional = f.get('minNotional') or f.get('minNotional')
                    try:
                        return float(f.get('minNotional') or f.get('minNotional') or f.get('minNotional', 0.0))
                    except Exception:
                        # se não conseguir parse, continua (tratamento abaixo)
                        pass

            # fallback: procurar por 'minNotional' direto (algumas exchanges / versões)
            for f in info_simbolo.get('filters', []):
                if 'minNotional' in f:
                    try:
                        return float(f['minNotional'])
                    except Exception:
                        continue
            return 0.0
        except Exception:
            return 0.0

    # -------------------------
    # Websocket (sem alterações significativas)
    # -------------------------
    def iniciar_websocket_klines(self, pares: list, intervalo: str, callback_mensagem):
        self.twm = ThreadedWebsocketManager(api_key=settings.API_KEY, api_secret=settings.API_SECRET, tld='com', testnet=self.testnet)
        self.twm.start()
        for par in pares:
            self.twm.start_kline_socket(callback=callback_mensagem, symbol=par, interval=intervalo)
        log.info(f"Streams de WebSocket iniciados para: {pares}")

    # -------------------------
    # Ordem de compra com validações completas
    # -------------------------
    def criar_ordem_compra_mercado(self, par: str, quantidade_usdt: float) -> dict | None:
        """
        Tenta criar uma ordem de compra do tipo MARKET usando quoteOrderQty (USDT).
        Valida:
          - saldo disponível do asset base (ex: USDT)
          - minNotional / NOTIONAL do símbolo (aumenta quoteOrderQty para min, se possível)
        """
        try:
            log.info(f"Tentativa de compra: {par} com {quantidade_usdt} (quoteOrderQty).")

            # determina asset de quote: normalmente símbolos terminam com 'USDT' ou 'BUSD' etc.
            if par.endswith("USDT"):
                quote_asset = "USDT"
            elif par.endswith("BUSD"):
                quote_asset = "BUSD"
            else:
                # fallback: assume últimos 3 ou 4 chars (tenta USDT ou a parte final)
                quote_asset = par[-4:] if par[-4:] in ("USDT",) else par[-3:]

            saldo_disponivel = self.obter_saldo_ativo(quote_asset)
            if saldo_disponivel <= 0:
                log.error(f"Saldo do ativo de quote ({quote_asset}) é zero. Abortando compra para {par}.")
                return None

            # recupera informações do símbolo para checar minNotional
            info_simbolo = self._obter_info_simbolo(par)
            if not info_simbolo:
                log.error(f"Não foi possível obter info do símbolo {par}. Abortando ordem de compra.")
                return None

            min_notional = self._obter_min_notional(info_simbolo)
            # Alguns mercados apresentam min_notional em formatos diferentes; garantimos float
            try:
                min_notional = float(min_notional)
            except Exception:
                min_notional = 0.0

            # Se declarado min_notional, garantimos quote >= min_notional.
            # Se pedido < min_notional, tentamos ajustar para min_notional se houver saldo.
            if min_notional > 0 and quantidade_usdt < min_notional:
                log.info(f"Quote solicitado ({quantidade_usdt}) está abaixo do min_notional ({min_notional}). Tentando ajustar para o mínimo.")
                if saldo_disponivel >= min_notional:
                    log.info(f"Ajustando quoteOrderQty para min_notional {min_notional} {quote_asset} (possui saldo).")
                    quantidade_usdt = float(min_notional)
                else:
                    log.error(
                        f"Saldo insuficiente para atingir o min_notional. "
                        f"Necessário: {min_notional} {quote_asset}, Disponível: {saldo_disponivel:.8f} {quote_asset}. Abortando."
                    )
                    return None

            # Se saldo disponível menor que a quantidade desejada após ajuste: aborta.
            if saldo_disponivel < quantidade_usdt:
                log.error(
                    f"Saldo insuficiente para comprar {par}. Necessário: {quantidade_usdt:.8f} {quote_asset}, "
                    f"Disponível: {saldo_disponivel:.8f} {quote_asset}."
                )
                return None

            # Finalmente, realiza a ordem. Usamos quoteOrderQty já ajustado.
            log.info(f"Tentando criar ordem de COMPRA a mercado para {par} com quoteOrderQty={quantidade_usdt:.8f} {quote_asset}.")
            ordem = self.cliente.order_market_buy(symbol=par, quoteOrderQty=round(quantidade_usdt, 8))
            log.info(f"Ordem de COMPRA criada com sucesso: {ordem}")
            return ordem

        except BinanceAPIException as e:
            # Mensagens de API retornam erros específicos (NOTIONAL, INSUFFICIENT_BALANCE, etc)
            log.error(f"Erro de API ao criar ordem de compra para {par}: {e}")
            return None
        except Exception as e:
            log.error(f"Erro inesperado ao criar ordem de compra para {par}: {e}")
            return None

    # -------------------------
    # Ordem OCO / Venda / Cancelamento
    # -------------------------
    def criar_ordem_venda_oco(self, par: str, quantidade: float, preco_compra: float) -> dict | None:
        try:
            info_simbolo = self._obter_info_simbolo(par)
            if not info_simbolo: return None
            
            filtro_preco = next((f for f in info_simbolo['filters'] if f['filterType'] == 'PRICE_FILTER'), None)
            filtro_lote = next((f for f in info_simbolo['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            if not filtro_preco or not filtro_lote: return None

            tick_size = float(filtro_preco['tickSize'])
            step_size = float(filtro_lote['stepSize'])

            def ajustar_valor(valor, step):
                if step == 0: return valor
                # determina casas decimais do step (ex: 0.001 -> 3)
                try:
                    precisao = abs(int(round(math.log10(step))))
                except Exception:
                    # fallback para string parsing
                    s = str(step)
                    if '.' in s:
                        precisao = len(s.split('.')[1])
                    else:
                        precisao = 0
                # ajustar para o múltiplo do step
                multiplo = math.floor(valor / step)
                return round(multiplo * step, precisao)

            preco_take_profit = ajustar_valor(preco_compra * settings.FATOR_TAKE_PROFIT, tick_size)
            preco_stop_loss = ajustar_valor(preco_compra * (1 - settings.PERCENTUAL_STOP_LOSS), tick_size)
            preco_stop_limit = ajustar_valor(preco_stop_loss * 0.998, tick_size)
            quantidade_ajustada = ajustar_valor(quantidade, step_size)

            log.info(f"Criando ordem OCO para {par} | Qtd: {quantidade_ajustada} | TP: {preco_take_profit} | SL: {preco_stop_loss}")
            
            ordem_oco = self.cliente.create_oco_order(
                symbol=par, side=Client.SIDE_SELL,
                quantity=f"{quantidade_ajustada:.8f}".rstrip('0').rstrip('.'),
                price=f"{preco_take_profit:.8f}".rstrip('0').rstrip('.'),
                stopPrice=f"{preco_stop_loss:.8f}".rstrip('0').rstrip('.'),
                stopLimitPrice=f"{preco_stop_limit:.8f}".rstrip('0').rstrip('.'),
                stopLimitTimeInForce=Client.TIME_IN_FORCE_GTC
            )
            return ordem_oco
        except BinanceAPIException as e:
            log.error(f"Erro de API ao criar ordem OCO para {par}: {e}")
            return None
        except Exception as e:
            log.error(f"Erro inesperado ao criar ordem OCO para {par}: {e}")
            return None

    def criar_ordem_venda_mercado(self, par: str, quantidade: float) -> dict | None:
        try:
            info_simbolo = self._obter_info_simbolo(par)
            if not info_simbolo: return None
            filtro_lote = next((f for f in info_simbolo['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            if not filtro_lote: return None
            step_size = float(filtro_lote['stepSize'])
            
            def ajustar_valor(valor, step):
                if step == 0: return valor
                try:
                    precisao = abs(int(round(math.log10(step))))
                except Exception:
                    s = str(step)
                    if '.' in s:
                        precisao = len(s.split('.')[1])
                    else:
                        precisao = 0
                multiplo = math.floor(valor / step)
                return round(multiplo * step, precisao)

            quantidade_ajustada = ajustar_valor(quantidade, step_size)
            ordem = self.cliente.order_market_sell(symbol=par, quantity=quantidade_ajustada)
            return ordem
        except BinanceAPIException as e:
            log.error(f"Erro de API ao criar ordem de venda para {par}: {e}")
            return None
        except Exception as e:
            log.error(f"Erro inesperado ao criar ordem de venda para {par}: {e}")
            return None

    def cancelar_ordem_por_id(self, par: str, order_list_id: int) -> bool:
        try:
            log.info(f"Tentando cancelar a lista de ordens OCO ID {order_list_id} para o par {par}.")
            self.cliente.cancel_oco_order(symbol=par, orderListId=order_list_id) # type: ignore
            log.info(f"Ordem OCO ID {order_list_id} cancelada com sucesso.")
            return True
        except BinanceAPIException as e:
            log.error(f"Erro de API ao cancelar ordem OCO ID {order_list_id}: {e}")
            return False
        except Exception as e:
            log.error(f"Erro inesperado ao cancelar OCO ID {order_list_id}: {e}")
            return False
            
    def parar_websocket(self):
        if self.twm:
            log.info("Encerrando a conexão do WebSocket...")
            self.twm.stop()
            self.twm = None
            log.info("WebSocket encerrado.")
