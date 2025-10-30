# Agente Trader Preditivo com IA (Binance)

Este projeto implementa um backend em Python (FastAPI) para análise de mercado cripto (Binance), integrando indicadores técnicos, coleta de notícias econômicas e um agente de IA para gerar recomendações de trading apresentadas em um dashboard.

## Visão Geral
- Backend em Python com FastAPI.
- Integração com Binance para klines e preços em tempo real.
- Cálculo de indicadores técnicos (EMA, RSI, VWAP e Bandas de VWAP).
- Coleta de notícias econômicas (web scraping do calendário do MyFxBook).
- Agente de IA (RAG + LLM) que produz recomendações estruturadas ("COMPRAR", "VENDER", "MANTER").
- Estrutura pronta para um frontend web simples (HTML/CSS/JS).

## Principais Módulos
- `api/`: rotas FastAPI (ativos, análise, notícias, saúde do serviço).
- `estrategia/`: cálculo de indicadores e lógica de decisão.
- `agent/`: agente de IA, contexto, RAG (arquivos em `data/`).
- `utils/`: helpers (datas, normalização, tradingview widgets, etc.).
- `config/`: configs, variáveis de ambiente e credenciais (usar `.env`).
- `data/`: bases locais para RAG e artefatos (evitar versionar dados sensíveis).

## Requisitos
- Python 3.10+
- `pip install -r requirements.txt`
- Variáveis `.env` (exemplos):
  - `BINANCE_API_KEY` e `BINANCE_SECRET_KEY`
  - `OPENAI_API_KEY` (ou provedor compatível)
  - `NEWS_REGION` (ex.: BR, US)

## Como Executar
1. Crie e ative seu ambiente virtual (`python -m venv .venv` e ative).
2. Instale dependências: `pip install -r requirements.txt`.
3. Configure `.env` em `backend/` com suas chaves.
4. Rode a API: `uvicorn api.main:app --reload`.
5. Acesse o Swagger: `http://localhost:8000/docs`.

## Fluxo de Análise (Resumo)
1. O usuário seleciona ativo/timeframe e solicita análise.
2. A API busca klines recentes na Binance.
3. Os indicadores são calculados em `estrategia/`.
4. O agente de IA recebe o contexto (indicadores + sentimento + conhecimento em `data/`).
5. A IA retorna JSON com ação, confiança e justificativa.
6. A API consolida e retorna para o frontend renderizar no dashboard.

## Roadmap
- Execução de ordens reais/tempo simulado via Binance (trade engine seguro).
- Backtesting com métricas (CAGR, MDD, Sharpe) e otimização de parâmetros.
- Estratégias adicionais (Breakout, Mean Reversion, Momentum multi-timeframe).
- Melhoria do RAG com embeddings e indexação vetorial (FAISS/Chroma).
- Alertas por e-mail/Telegram e webhooks personalizáveis.
- Cache de dados e filas para scraping/integrações mais robustas.
- Dockerfile e Compose para desenvolvimento e produção.

## Boas Práticas e Segurança
- Nunca exponha chaves de API no repositório; use `.env`.
- Evite operar em contas reais sem limites e proteções.
- Valide inputs e trate exceções nas rotas.
- Faça logs estruturados e centralize erros.

## Estrutura (exemplo)
```
backend/
+- api/
+- agent/
+- estrategia/
+- utils/
+- config/
+- data/
+- logs/
+- main.py
+- requirements.txt
```

## Licença
Defina a licença conforme sua preferência (ex.: MIT). Caso deseje, adiciono um arquivo `LICENSE`.

---
Criado com foco em clareza, extensibilidade e segurança para operações de trading algorítmico.
